"""卖家精灵 MCP 客户端 + 管线。

平移自 IvyeaOps `sellersprite_service.py`，只保留市场调研用到的部分
（keyword/asin 管线），Key 改从 .env 读。响应形态与 Sorftime 同构：
POST JSON-RPC → SSE `data: {...}`，工具载荷是 {"code":"OK","data":...}。
"""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
from typing import Any, Awaitable, Callable, Tuple

import httpx

from ..config import config

logger = logging.getLogger("ecom.legacy.sellersprite")

_BASE = "https://mcp.sellersprite.com/mcp"
_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
_TOOL_TIMEOUT = 40.0
_CONN_TIMEOUT = 10.0


def _key() -> str:
    return config.sellersprite_key


def _url() -> str:
    return f"{_BASE}?secret-key={_key()}"


def recent_month() -> str:
    """最近一个完整月 yyyyMM（卖家精灵数据滞后约 1 个月）。"""
    return (datetime.date.today().replace(day=1) - datetime.timedelta(days=1)).strftime("%Y%m")


def parse_sse(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            raw = line[5:].strip()
            if raw:
                try:
                    return json.loads(raw)
                except Exception:
                    logger.debug("json 解析失败（旁路）", exc_info=True)
    try:
        return json.loads(text)
    except Exception:
        return {}


async def _initialize(client: httpx.AsyncClient) -> None:
    try:
        await client.post(_url(), headers=_HEADERS, json={
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "ecom-agent", "version": "1.0"}},
        })
    except Exception:
        logger.debug("initialize 失败（旁路）", exc_info=True)


async def _call_tool(client: httpx.AsyncClient, name: str, args: dict, call_id: int = 1) -> Any:
    if not _key():
        raise RuntimeError("SELLERSPRITE_KEY 未配置（.env），卖家精灵工具不可用")
    r = await client.post(_url(), headers=_HEADERS, json={
        "jsonrpc": "2.0", "id": call_id, "method": "tools/call",
        "params": {"name": name, "arguments": args},
    })
    body = parse_sse(r.text)
    if body.get("error"):
        raise RuntimeError(f"{name}: {body['error']}")
    result = body.get("result") or {}
    content = result.get("content") or []
    text = content[0].get("text", "") if content and isinstance(content[0], dict) else ""
    if result.get("isError"):
        raise RuntimeError(f"{name}: {(text or '工具返回错误')[:200]}")
    try:
        parsed = json.loads(text) if text else {}
    except Exception:
        return {"_raw": text[:4000]}
    code = str(parsed.get("code") or "")
    if code and code != "OK":
        raise RuntimeError(f"{name} {code}: {parsed.get('message', '')}")
    return parsed.get("data", parsed)


async def _run_steps(steps: list[tuple[str, str, dict]]) -> Tuple[dict, list[str]]:
    data: dict[str, Any] = {}
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(_TOOL_TIMEOUT, connect=_CONN_TIMEOUT)) as client:
        await _initialize(client)
        for i, (label, name, args) in enumerate(steps):
            try:
                data[label] = await _call_tool(client, name, args, i + 1)
            except Exception as exc:  # 单步失败不中断整条管线
                errors.append(f"{label}: {exc}")
    return data, errors


async def keyword_pipeline(query: str, marketplace: str) -> Tuple[dict, list[str]]:
    month = recent_month()
    return await _run_steps([
        ("关键词搜索/购买趋势", "keyword_research_trends",
         {"marketplace": marketplace, "keyword": query, "month": month}),
        ("ABA 排名趋势", "aba_research_trend",
         {"marketplace": marketplace, "keyword": query, "timeGranularity": "month"}),
    ])


async def asin_pipeline(asin: str, marketplace: str) -> Tuple[dict, list[str]]:
    month = recent_month()
    return await _run_steps([
        ("商品详情", "asin_detail", {"marketplace": marketplace, "asin": asin}),
        ("销量趋势", "asin_sales_trend", {"marketplace": marketplace, "asin": asin}),
        ("流量关键词概览", "traffic_keyword_stat",
         {"marketplace": marketplace, "asin": asin, "month": month}),
    ])
