"""Sorftime MCP 客户端 + 两阶段数据管线。

平移自 IvyeaOps `server/app/services/sorftime_service.py`，改动只有一处：
Key 从 .env 读（原 hub_settings）。其余——SSE 解析、非数据文本识别、
行裁剪、按预算压缩、两阶段编排——原样保留，这些是踩坑换来的。

Keyword pipeline (10 次调用, 2 阶段):
  Phase 1 (并发 6): keyword_detail, keyword_trend, keyword_extends,
                    keyword_search_results, category_search_from_product_name,
                    similar_product_feature
  Phase 2 (依赖 P1): product_detail×2, potential_product, category_report(top100)

ASIN pipeline (9 次调用, 2 阶段):
  Phase 1 (并发 5): product_detail, product_trend, product_traffic_terms,
                    product_reviews, product_variations
  Phase 2: keyword_detail, keyword_search_results,
           competitor_product_keywords, category_report
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ..config import config

logger = logging.getLogger("ecom.legacy.sorftime")

_SORFTIME_BASE = "https://mcp.sorftime.com"
_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
_TOOL_TIMEOUT = 30.0
_CONN_TIMEOUT = 10.0


def _url() -> str:
    key = config.sorftime_key
    if not key:
        raise RuntimeError("SORFTIME_KEY 未配置（.env），市场调研工具不可用")
    return f"{_SORFTIME_BASE}?key={key}"


_CAMEL_RE = re.compile(r"(?<!^)(?=[A-Z])")


def normalize_args(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """参数键统一转 lower_snake_case。Sorftime 的 MCP schema 全 snake_case，
    camelCase 键不会被拒绝而是被静默忽略——返回"成功"但内容是提示文本。"""
    return {_CAMEL_RE.sub("_", k).lower(): v for k, v in (arguments or {}).items()}


async def _call_tool(client: httpx.AsyncClient, tool_name: str,
                     arguments: Dict[str, Any], call_id: int = 1) -> Any:
    payload = {
        "jsonrpc": "2.0", "id": call_id, "method": "tools/call",
        "params": {"name": tool_name, "arguments": normalize_args(arguments)},
    }
    resp = await client.post(_url(), json=payload, headers=_HEADERS)
    resp.raise_for_status()

    body = None
    for line in resp.text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            raw = line[5:].strip()
            if raw:
                try:
                    body = json.loads(raw)
                    break
                except Exception:
                    logger.debug("json 解析失败（旁路）", exc_info=True)
    if body is None:
        raise RuntimeError(f"sorftime/{tool_name}: SSE 响应解析失败")

    if "error" in body:
        raise RuntimeError(f"sorftime/{tool_name} error: {body['error']}")

    result = body.get("result", {})
    if result.get("isError"):
        content_list = result.get("content", [])
        msg = next((c.get("text", "") for c in content_list
                    if isinstance(c, dict) and c.get("type") == "text"), "unknown error")
        raise RuntimeError(f"sorftime/{tool_name}: {msg}")

    content = result.get("content", [])
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict) and first.get("type") == "text":
            text = first.get("text", "")
            try:
                return json.loads(text)
            except Exception:
                # Sorftime 会把某些失败包在"成功"信封里返回散文——显式拒绝，
                # 否则下游会把报错文本当数据分析。
                if _is_non_data_text(text):
                    raise RuntimeError(f"sorftime/{tool_name}: {str(text).strip()[:300]}")
                return text
    return result


_NON_DATA_MARKERS = (
    "please specify the site",
    "parameter description in the method signature",
    "authentication required",
    "call the following tools to combine their data",
)


def _is_non_data_text(text: Any) -> bool:
    low = str(text).strip().lower()
    return any(marker in low for marker in _NON_DATA_MARKERS)


def unwrap(payload: Any) -> Any:
    """Sorftime 把答案包成 {"doc": {字段说明}, "data": <真实内容>}，取 data。"""
    if isinstance(payload, dict) and "data" in payload and isinstance(payload.get("doc"), dict):
        return payload["data"]
    return payload


_ROW_KEYS = ("data", "items", "results", "list", "top100_products", "analysis_results")


def rows(payload: Any) -> List[Dict[str, Any]]:
    node = unwrap(payload)
    if isinstance(node, list):
        return [r for r in node if isinstance(r, dict)]
    if isinstance(node, dict):
        for key in _ROW_KEYS:
            arr = node.get(key)
            if isinstance(arr, list):
                return [r for r in arr if isinstance(r, dict)]
    return []


def record(payload: Any) -> Dict[str, Any]:
    node = unwrap(payload)
    if isinstance(node, dict):
        return node
    if isinstance(node, list) and node and isinstance(node[0], dict):
        return node[0]
    return {}


def compact(payload: Any, limit: int = 30) -> Any:
    """每个行列表截到 limit 行——聚合统计块（dict）原样保留。"""
    node = unwrap(payload)
    trimmed: Any = node
    if isinstance(node, list) and len(node) > limit:
        trimmed = node[:limit]
    elif isinstance(node, dict):
        for key in _ROW_KEYS:
            arr = node.get(key)
            if isinstance(arr, list) and len(arr) > limit:
                if trimmed is node:
                    trimmed = dict(node)
                trimmed[key] = arr[:limit]
    if trimmed is node:
        return payload
    if isinstance(payload, dict) and "data" in payload and isinstance(payload.get("doc"), dict):
        return {**payload, "data": trimmed}
    return trimmed


def compact_all(data: Dict[str, Any], limit: int = 30) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, value in (data or {}).items():
        if name.endswith("_list") and isinstance(value, list):
            out[name] = [compact(item, limit) for item in value]
        else:
            out[name] = compact(value, limit)
    return out


def summarize_for_prompt(data: Dict[str, Any], budget: int = 45000) -> str:
    """把整条管线的结果压进 budget 字符，且保证每个来源都在场。

    完整关键词管线 ~148KB，直接转 JSON 再砍尾巴会把排后面的来源整个砍掉
    （类目报告、潜力商品恰好在最后）。这里给每个来源均分预算、按行稀释到
    放得下为止。"""
    sources = list((data or {}).items())
    if not sources:
        return "{}"
    share = max(budget // len(sources), 800)
    parts: List[str] = []
    for name, value in sources:
        limit = 30
        text = json.dumps(value, ensure_ascii=False, indent=2)
        while len(text) > share and limit > 1:
            limit = max(1, limit // 2)
            trimmed = ([compact(v, limit) for v in value]
                       if name.endswith("_list") and isinstance(value, list)
                       else compact(value, limit))
            text = json.dumps(trimmed, ensure_ascii=False, indent=2)
        if len(text) > share:
            text = text[:share] + "\n…(本项已截断)"
        parts.append(f'  "{name}": {text}')
    return "{\n" + ",\n".join(parts) + "\n}"


def first_field(payload: Any, *names: str) -> str:
    for src in (record(payload), *rows(payload)[:1]):
        for name in names:
            val = src.get(name)
            if val not in (None, "", []):
                return str(val)
    return ""


async def _safe_call(client: httpx.AsyncClient, tool_name: str,
                     arguments: Dict[str, Any], call_id: int = 1
                     ) -> Tuple[str, Any, Optional[str]]:
    """返回 (tool_name, result|None, error|None)——单工具失败不拖垮整条管线。"""
    try:
        data = await asyncio.wait_for(
            _call_tool(client, tool_name, arguments, call_id), timeout=_TOOL_TIMEOUT)
        return tool_name, data, None
    except asyncio.TimeoutError:
        logger.warning("sorftime/%s 超时", tool_name)
        return tool_name, None, f"{tool_name} 超时"
    except Exception as exc:
        logger.warning("sorftime/%s 失败: %s", tool_name, exc)
        return tool_name, None, f"{tool_name}: {exc}"


@asynccontextmanager
async def _make_client():
    """httpx 客户端 + MCP initialize 握手（Sorftime 要求先握手再 tools/call）。"""
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(_TOOL_TIMEOUT, connect=_CONN_TIMEOUT),
        limits=httpx.Limits(max_connections=20),
    ) as client:
        try:
            init_payload = {
                "jsonrpc": "2.0", "id": 0, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "ecom-agent", "version": "1.0"},
                },
            }
            resp = await asyncio.wait_for(
                client.post(_url(), json=init_payload, headers=_HEADERS),
                timeout=_CONN_TIMEOUT)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("sorftime initialize 失败: %s", exc)
        yield client


async def keyword_pipeline(keyword: str, marketplace: str) -> Tuple[Dict[str, Any], List[str]]:
    """关键词调研全管线。返回 (data, errors)。"""
    errors: List[str] = []
    data: Dict[str, Any] = {}

    async with _make_client() as client:
        phase1_tasks = [
            _safe_call(client, "keyword_detail",
                       {"keyword": keyword, "keyword_support_site": marketplace}, 1),
            _safe_call(client, "keyword_trend",
                       {"keyword": keyword, "keyword_support_site": marketplace}, 2),
            _safe_call(client, "keyword_extends",
                       {"keyword": keyword, "keyword_support_site": marketplace}, 3),
            _safe_call(client, "keyword_search_results",
                       {"keyword": keyword, "keyword_support_site": marketplace}, 4),
            _safe_call(client, "category_search_from_product_name",
                       {"product_name": keyword, "amz_site": marketplace}, 5),
            _safe_call(client, "similar_product_feature",
                       {"product_name": keyword, "amz_site": marketplace}, 6),
        ]
        for name, val, err in await asyncio.gather(*phase1_tasks):
            if err:
                errors.append(err)
            else:
                data[name] = val

        top_asins = [str(row["asin"]) for row in rows(data.get("keyword_search_results"))[:2]
                     if row.get("asin")]
        node_id = first_field(data.get("category_search_from_product_name"), "node_id")

        phase2_tasks = []
        for i, asin in enumerate(top_asins[:2]):
            phase2_tasks.append(
                _safe_call(client, "product_detail", {"asin": asin, "amz_site": marketplace}, 10 + i))
        phase2_tasks.append(
            _safe_call(client, "potential_product", {"search_name": keyword, "amz_site": marketplace}, 12))
        if node_id:
            phase2_tasks.append(
                _safe_call(client, "category_report", {"node_id": node_id, "amz_site": marketplace}, 13))

        for name, val, err in await asyncio.gather(*phase2_tasks):
            if err:
                errors.append(err)
            elif name == "product_detail":
                data.setdefault("product_detail_list", []).append(val)
            else:
                data[name] = val

    return data, errors


async def asin_pipeline(asin: str, marketplace: str) -> Tuple[Dict[str, Any], List[str]]:
    """ASIN 调研全管线。返回 (data, errors)。"""
    errors: List[str] = []
    data: Dict[str, Any] = {}

    async with _make_client() as client:
        # product_report 是"说明书工具"——对任何 ASIN 都只回"请组合以下工具"。
        # 核心指标在 product_detail 里。
        phase1_tasks = [
            _safe_call(client, "product_detail", {"asin": asin, "amz_site": marketplace}, 1),
            _safe_call(client, "product_trend", {"asin": asin, "amz_site": marketplace}, 2),
            _safe_call(client, "product_traffic_terms", {"asin": asin, "amz_site": marketplace}, 3),
            _safe_call(client, "product_reviews", {"asin": asin, "amz_site": marketplace}, 4),
            _safe_call(client, "product_variations", {"asin": asin, "amz_site": marketplace}, 5),
        ]
        for name, val, err in await asyncio.gather(*phase1_tasks):
            if err:
                errors.append(err)
            else:
                data[name] = val

        main_kw = first_field(data.get("product_traffic_terms"), "keyword", "term", "search_term")
        node_id = first_field(data.get("product_detail"), "node_id")

        phase2_tasks = []
        if main_kw:
            phase2_tasks += [
                _safe_call(client, "keyword_detail",
                           {"keyword": main_kw, "keyword_support_site": marketplace}, 10),
                _safe_call(client, "keyword_search_results",
                           {"keyword": main_kw, "keyword_support_site": marketplace}, 11),
            ]
        phase2_tasks.append(
            _safe_call(client, "competitor_product_keywords",
                       {"asin": asin, "keyword_support_site": marketplace}, 12))
        if node_id:
            phase2_tasks.append(
                _safe_call(client, "category_report", {"node_id": node_id, "amz_site": marketplace}, 13))

        for name, val, err in await asyncio.gather(*phase2_tasks):
            if err:
                errors.append(err)
            else:
                data[name] = val

    return data, errors


async def quick_calls(calls: List[Tuple[str, Dict[str, Any]]]) -> Tuple[Dict[str, Any], List[str]]:
    """一组并发工具调用（给竞品反查/流量诊断等轻量组合用）。"""
    errors: List[str] = []
    data: Dict[str, Any] = {}
    async with _make_client() as client:
        tasks = [_safe_call(client, name, args, i + 1) for i, (name, args) in enumerate(calls)]
        for name, val, err in await asyncio.gather(*tasks):
            if err:
                errors.append(err)
            else:
                data[name] = val
    return data, errors
