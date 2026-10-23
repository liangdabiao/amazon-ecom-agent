"""领星 OpenAPI 传输层（只读）。

平移自 IvyeaOps `lingxing_openapi.py`——签名算法、token 生命周期、读写路由
分类全部原样保留；凭证改从 .env 读。新增一道硬闸：`call_read` 强制只放行
读路由（classify_route != "read" 直接拒绝），本系统对领星永远只读。
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from cryptography.hazmat.primitives import padding as _pad
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ..config import config

_TOKEN_PATH_GET = "/api/auth-server/oauth/access-token"
_TOKEN_PATH_REFRESH = "/api/auth-server/oauth/refresh"
_REQUEST_TIMEOUT_S = 60.0
_TOKEN_SKEW_S = 120


class LingXingOpenAPIError(RuntimeError):
    pass


# --- 读写路由分类：看最后一段的动词，全词比对（避免 /manage/list 误判写、
# archiveNegatives 漏判写 这两个历史上真实翻过的车）-------------------------
_WRITE_VERBS = frozenset({
    "put", "post", "create", "add", "update", "modify", "edit", "save", "set",
    "delete", "del", "remove", "archive", "cancel", "confirm", "submit",
    "approve", "reject", "operate", "adjust", "enable", "disable", "bind",
    "unbind", "push", "sync", "import", "upload", "batch",
})
_WRITE_SEGMENTS = frozenset({
    "put", "create", "add", "update", "modify", "edit", "save", "delete",
    "remove", "archive", "cancel", "operate", "adjust", "import", "upload",
})
_LEADING_LOWER = re.compile(r"^[a-z]+")


def _norm(route: str) -> str:
    return "/" + (route or "").strip().strip("/")


def classify_route(route: str) -> str:
    r = (route or "").strip()
    if not r:
        return "unknown"
    segments = [s for s in r.split("/") if s]
    if not segments:
        return "unknown"
    if any(s.lower() in _WRITE_SEGMENTS for s in segments):
        return "write"
    head = _LEADING_LOWER.match(segments[-1])
    if head and head.group(0) in _WRITE_VERBS:
        return "write"
    return "read"


# --- 签名（复刻领星 SignService）--------------------------------------------
def _filter_array(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: _filter_array(x) for k, x in v.items() if x is not None}
    if isinstance(v, list):
        return [_filter_array(x) for x in v if x is not None]
    return v


def _php_json(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def make_sign(params: Dict[str, Any], app_id: str) -> str:
    parts = []
    for k in sorted(params.keys()):
        v = params[k]
        if isinstance(v, (dict, list)):
            parts.append(f"{k}=" + _php_json(_filter_array(v)))
        elif v == "":
            continue
        else:
            if isinstance(v, bool):
                v = "true" if v else "false"
            elif v is None:
                v = "null"
            parts.append(f"{k}={v}")
    canonical = "&".join(parts)
    md5_upper = hashlib.md5(canonical.encode("utf-8")).hexdigest().upper()
    padder = _pad.PKCS7(128).padder()
    data = padder.update(md5_upper.encode("utf-8")) + padder.finalize()
    enc = Cipher(algorithms.AES(app_id.encode("utf-8")), modes.ECB()).encryptor()
    ct = enc.update(data) + enc.finalize()
    return base64.b64encode(ct).decode("ascii")


# --- 凭证 / token 缓存 -------------------------------------------------------
def is_configured() -> bool:
    return config.lingxing_ready()


def _token_path() -> Path:
    return config.data_dir / "lingxing_token.json"


def _load_token() -> Dict[str, Any]:
    try:
        return json.loads(_token_path().read_text("utf-8"))
    except Exception:
        return {}


def _save_token(tok: Dict[str, Any]) -> None:
    p = _token_path()
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(tok, ensure_ascii=False), "utf-8")
    tmp.replace(p)


_token_lock = asyncio.Lock()


async def _fetch_token(client: httpx.AsyncClient) -> Dict[str, Any]:
    r = await client.post(f"{config.lingxing_host}{_TOKEN_PATH_GET}",
                          params={"appId": config.lingxing_app_id,
                                  "appSecret": config.lingxing_app_secret})
    return _unwrap_token(r)


async def _refresh_token(client: httpx.AsyncClient, refresh_token: str) -> Dict[str, Any]:
    r = await client.post(f"{config.lingxing_host}{_TOKEN_PATH_REFRESH}",
                          params={"appId": config.lingxing_app_id,
                                  "refreshToken": refresh_token})
    return _unwrap_token(r)


def _unwrap_token(r: httpx.Response) -> Dict[str, Any]:
    if r.status_code >= 400:
        raise LingXingOpenAPIError(f"令牌接口 HTTP {r.status_code}: {r.text[:200]}")
    try:
        body = r.json()
    except Exception as e:
        raise LingXingOpenAPIError(f"令牌响应非 JSON: {r.text[:200]}") from e
    if str(body.get("code")) not in ("200", "0"):
        raise LingXingOpenAPIError(
            f"令牌接口错误 {body.get('code')}: {body.get('msg') or body.get('message')}")
    data = body.get("data") or {}
    at = data.get("access_token")
    if not at:
        raise LingXingOpenAPIError("令牌响应缺少 access_token")
    return {
        "access_token": at,
        "refresh_token": data.get("refresh_token", ""),
        "expire_at": time.time() + float(data.get("expires_in") or 0),
    }


async def _ensure_token(client: httpx.AsyncClient) -> str:
    if not is_configured():
        raise LingXingOpenAPIError("未配置领星凭证（.env: LINGXING_HOST/APP_ID/APP_SECRET）")
    async with _token_lock:
        tok = _load_token()
        now = time.time()
        if tok.get("access_token") and float(tok.get("expire_at", 0)) - _TOKEN_SKEW_S > now:
            return tok["access_token"]
        new: Optional[Dict[str, Any]] = None
        if tok.get("refresh_token"):
            try:
                new = await _refresh_token(client, tok["refresh_token"])
            except LingXingOpenAPIError:
                new = None
        if new is None:
            new = await _fetch_token(client)
        _save_token(new)
        return new["access_token"]


# --- 请求 --------------------------------------------------------------------
async def call(route: str, params: Optional[Dict[str, Any]] = None, *,
               method: str = "POST") -> Dict[str, Any]:
    """签名 OpenAPI 调用。route 如 `/erp/sc/data/seller/lists`。"""
    params = dict(params or {})
    method = method.upper()
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_S, verify=True) as client:
        access_token = await _ensure_token(client)
        common = {"access_token": access_token, "timestamp": int(time.time()),
                  "app_key": config.lingxing_app_id}
        full = {**params, **common}
        sign = make_sign(full, config.lingxing_app_id)
        if method == "GET":
            query = {**full, "sign": sign}
            body = None
        else:
            query = {**common, "sign": sign}
            body = _php_json(full)
        url = f"{config.lingxing_host}/{route.strip('/')}"
        headers = {"Content-Type": "application/json"}
        try:
            if method == "GET":
                r = await client.get(url, params=query, headers=headers)
            else:
                r = await client.request(method, url, params=query, content=body, headers=headers)
        except httpx.HTTPError as e:
            raise LingXingOpenAPIError(f"领星 OpenAPI 连接失败: {e}") from e
    if r.status_code >= 400:
        raise LingXingOpenAPIError(f"领星 OpenAPI HTTP {r.status_code}: {r.text[:300]}")
    try:
        body_json = r.json()
    except Exception as e:
        raise LingXingOpenAPIError(f"领星 OpenAPI 响应非 JSON: {r.text[:300]}") from e
    code = str(body_json.get("code"))
    if code not in ("200", "0", "1"):
        if body_json.get("success") is not True and code not in ("200", "0"):
            raise LingXingOpenAPIError(
                f"领星 OpenAPI 业务错误 code={code} msg={body_json.get('message') or body_json.get('msg')}")
    return body_json


async def call_read(route: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """只读闸内的调用：写路由一律拒绝。本系统对领星只有这一条入口。"""
    if classify_route(route) != "read":
        raise LingXingOpenAPIError(f"拒绝调用写路由（本系统对领星只读）: {route}")
    return await call(route, params, method="GET")
