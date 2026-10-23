"""市场调研工具：关键词/ASIN 调研、竞品反查、流量诊断。

每个工具 = 一条从 IvyeaOps 平移的采集管线 + 预算内压缩，直接把数据交给
agent 自己分析（不再需要独立的"AI 合成"步骤——agent 本身就是分析者）。
"""
from __future__ import annotations

import json

from agents import function_tool

from ..config import config as _cfg
from ..legacy import sorftime, sellersprite


def _render(data: dict, errors: list[str], budget: int = 42000) -> str:
    parts = [sorftime.summarize_for_prompt(sorftime.compact_all(data), budget=budget)]
    if errors:
        parts.append("\n\n[以下数据源本次获取失败，分析时请如实说明数据缺口]\n- " + "\n- ".join(errors))
    return "\n".join(parts)


def _pick_source() -> str:
    """sorftime 没配 key 时自动降级到卖家精灵。"""
    if _cfg.sorftime_key:
        return "sorftime"
    if _cfg.sellersprite_key:
        return "sellersprite"
    raise RuntimeError("市场数据源未配置：请在 .env 填 SORFTIME_KEY 或 SELLERSPRITE_KEY 至少一个")


@function_tool
async def research_keyword(keyword: str, marketplace: str = "US") -> str:
    """关键词市场调研：搜索量、趋势、拓展词、竞品、类目报告（10 项数据一次采集）。
    产出写报告所需的全部原始数据。适合"帮我调研 XX 关键词/市场"类请求。

    Args:
        keyword: 调研的关键词（如 "yoga mat"）
        marketplace: 站点代码，US/UK/DE/JP/FR/IT/ES/CA 等，默认 US
    """
    source = _pick_source()
    if source == "sellersprite":
        data, errors = await sellersprite.keyword_pipeline(keyword, marketplace)
        body = json.dumps(data, ensure_ascii=False, indent=2)
        if len(body) > 30000:
            body = body[:30000] + "\n…(截断)"
    else:
        data, errors = await sorftime.keyword_pipeline(keyword, marketplace)
        body = _render(data, errors)
    return f"# 关键词调研原始数据：{keyword}（{marketplace}，来源 {source}）\n\n{body}"


@function_tool
async def research_asin(asin: str, marketplace: str = "US") -> str:
    """ASIN 深度调研：商品详情、销量趋势、流量词、评论、变体、竞品关键词、类目 top100。
    适合"帮我分析这个 ASIN / 这个竞品"类请求。

    Args:
        asin: 10 位亚马逊 ASIN（如 B08N5WRWNW）
        marketplace: 站点代码，默认 US
    """
    source = _pick_source()
    if source == "sellersprite":
        data, errors = await sellersprite.asin_pipeline(asin, marketplace)
        body = json.dumps(data, ensure_ascii=False, indent=2)
        if len(body) > 30000:
            body = body[:30000] + "\n…(截断)"
    else:
        data, errors = await sorftime.asin_pipeline(asin, marketplace)
        body = _render(data, errors)
    return f"# ASIN 调研原始数据：{asin}（{marketplace}，来源 {source}）\n\n{body}"


@function_tool
async def keyword_competition(keyword: str, marketplace: str = "US") -> str:
    """关键词竞争分析（轻量 4 项）：关键词详情、12 个月趋势、拓展词、搜索结果页。
    比 research_keyword 快，适合快速判断一个词能不能做。

    Args:
        keyword: 关键词
        marketplace: 站点代码，默认 US
    """
    mk = marketplace.upper()
    data, errors = await sorftime.quick_calls([
        ("keyword_detail", {"keyword": keyword, "keyword_support_site": mk}),
        ("keyword_trend", {"keyword": keyword, "keyword_support_site": mk}),
        ("keyword_extends", {"keyword": keyword, "keyword_support_site": mk}),
        ("keyword_search_results", {"keyword": keyword, "keyword_support_site": mk}),
    ])
    return f"# 关键词竞争数据：{keyword}（{marketplace}）\n\n{_render(data, errors, budget=20000)}"


@function_tool
async def competitor_reverse(asin: str, marketplace: str = "US") -> str:
    """竞品反查：一个 ASIN 的流量关键词 + 竞品共用词 + 商品详情。
    回答"这个竞品的流量词是怎么构成的"。

    Args:
        asin: 竞品 ASIN
        marketplace: 站点代码，默认 US
    """
    mk = marketplace.upper()
    data, errors = await sorftime.quick_calls([
        ("product_traffic_terms", {"asin": asin, "amz_site": mk}),
        ("competitor_product_keywords", {"asin": asin, "keyword_support_site": mk}),
        ("product_detail", {"asin": asin, "amz_site": mk}),
    ])
    return f"# 竞品反查数据：{asin}（{marketplace}）\n\n{_render(data, errors, budget=20000)}"


@function_tool
async def traffic_diagnosis(asin: str, marketplace: str = "US") -> str:
    """流量异动诊断：流量词 + 销量/流量趋势 + 商品详情。
    回答"这个 ASIN 最近流量为什么涨/跌"。

    Args:
        asin: ASIN
        marketplace: 站点代码，默认 US
    """
    mk = marketplace.upper()
    data, errors = await sorftime.quick_calls([
        ("product_traffic_terms", {"asin": asin, "amz_site": mk}),
        ("product_trend", {"asin": asin, "amz_site": mk}),
        ("product_detail", {"asin": asin, "amz_site": mk}),
    ])
    return f"# 流量诊断数据：{asin}（{marketplace}）\n\n{_render(data, errors, budget=20000)}"
