"""领星 ERP 工具（严格只读）。"""
from __future__ import annotations

import json

from agents import function_tool

from ..legacy import lingxing_openapi as lx

_NOT_CONFIGURED = "领星未配置：请在 .env 填 LINGXING_HOST / LINGXING_APP_ID / LINGXING_APP_SECRET"

# 常用只读路由，写进工具描述让模型不用猜
_COMMON_ROUTES = """常用路由（method 全部 GET）：
- /erp/sc/data/seller/lists —— 店铺列表
- /erp/sc/data/mws/orderV2 —— 订单列表（参数 sdate/edate: yyyy-MM-dd）
- /erp/sc/data/sales/report —— 销量报表（参数 sdate/edate, sid 店铺id）
- /erp/sc/statistics/ads —— 广告报表（参数 sdate/edate, sid）
具体参数以领星官方 OpenAPI 文档为准；不确定时先用 lingxing_sellers 拿店铺 sid。"""


@function_tool
async def lingxing_sellers() -> str:
    """列出领星里授权的亚马逊店铺（返回的 sid 是后续店铺级查询的参数）。"""
    if not lx.is_configured():
        return _NOT_CONFIGURED
    try:
        result = await lx.call_read("/erp/sc/data/seller/lists", {})
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as exc:
        return f"领星查询失败: {exc}"


@function_tool
async def lingxing_query(route: str, params_json: str = "{}") -> str:
    """查询领星 ERP 真实经营数据（严格只读，写路由会被直接拒绝）。
    返回领星原始 JSON。路由参考：
    /erp/sc/data/seller/lists（店铺）、/erp/sc/data/sales/report（销量，需 sid + sdate/edate）、
    /erp/sc/statistics/ads（广告）、/erp/sc/data/storage/list（FBA库存）、
    /erp/sc/data/mws/orderV2（订单，需 sdate/edate）。

    Args:
        route: 领星 OpenAPI 路由，如 /erp/sc/data/sales/report
        params_json: 查询参数 JSON 字符串，如 {"sdate":"2026-10-01","edate":"2026-10-20","sid":"123"}
    """
    if not lx.is_configured():
        return _NOT_CONFIGURED
    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return f"params_json 不是合法 JSON: {e}"
    try:
        result = await lx.call_read(route, params)
    except Exception as exc:
        return f"领星查询失败: {exc}"
    body = json.dumps(result, ensure_ascii=False, indent=2)
    if len(body) > 40000:
        body = body[:40000] + "\n…(截断)"
    return body
