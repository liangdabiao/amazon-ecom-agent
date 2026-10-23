"""Listing 工具：商品采集、生图、图片翻译。

文案生成不需要工具——规则在系统提示词里，agent 直接产出。
"""
from __future__ import annotations

import json

from agents import function_tool

from ..config import config
from ..legacy import amazon_scrape, image_gen


@function_tool
async def scrape_product(asin: str, marketplace: str = "US") -> str:
    """采集 Amazon 商品页：标题、五点描述、全套主图（自动下载到本地供生图参考）。
    采集链：本机 curl 直连 → 本机浏览器渲染兜底 → Sorftime 数据兜底。

    Args:
        asin: 10 位 ASIN
        marketplace: 站点代码，默认 US
    """
    data = await amazon_scrape.scrape_product(asin, marketplace)
    local_paths: list[str] = []
    if data.get("imageUrls"):
        local_paths = await amazon_scrape.download_images(data["imageUrls"], asin)
    out = {
        "asin": asin,
        "marketplace": marketplace,
        "title": data.get("title", ""),
        "bullets": data.get("bullets", []),
        "image_urls": data.get("imageUrls", []),
        "local_images": local_paths,
        "scrape_source": data.get("scrape_source", "none"),
        "hint": ("图片已下载到本地，生成主图时把 local_images[0] 作为 reference_image 传入"
                 if local_paths else "未获取到图片"),
    }
    return json.dumps(out, ensure_ascii=False, indent=2)


@function_tool
async def generate_image(prompt: str, size: str = "1024x1024",
                         reference_image: str = "",
                         presence: str = "supporting") -> str:
    """AI 生成电商图片（主图/A+图/场景图）。有参考图时严格保持产品一致。

    Args:
        prompt: 画面描述（英文效果更好）：场景、构图、光线、图上要出现的文字
        size: 目标尺寸 "宽x高"，如 1024x1024（主图）、1600x1600（画廊图）
        reference_image: 参考图本地路径（如采集到的产品白底图），可选
        presence: 产品出场方式 supporting=产品为主角 / environmental=产品小、场景为主
    """
    result = await image_gen.generate_image(prompt, size, reference_image, presence)
    return json.dumps(result, ensure_ascii=False, indent=2)


@function_tool
async def generate_image_set(shots_json: str, default_reference: str = "") -> str:
    """整套图顺序生成（Listing 7 图 / A+）。传入分镜 JSON 数组，逐张生成、单张失败不中断。

    Args:
        shots_json: 分镜数组 JSON，每项 {"name":"卖点图","prompt":"英文画面描述",
                    "size":"1600x1600","presence":"supporting","reference_image":"可选，默认用 default_reference"}
        default_reference: 全套共用的产品白底参考图路径（保证产品一致），可选
    """
    try:
        shots = json.loads(shots_json)
    except json.JSONDecodeError as e:
        return f"shots_json 不是合法 JSON: {e}"
    if not isinstance(shots, list) or not shots:
        return "shots_json 必须是非空数组"
    results = await image_gen.generate_image_set(shots[:9], default_reference)
    ok = sum(1 for r in results if r["ok"])
    return json.dumps({"summary": f"{ok}/{len(results)} 张成功", "images": results},
                      ensure_ascii=False, indent=2)


@function_tool
async def translate_image(image_path: str, target_language: str) -> str:
    """图片翻译：把图上文字译成目标语言，版式/产品/配色完全不变。
    用于一套图铺多站点。image_path 支持本地路径或 scrape_product 返回的图片路径。

    Args:
        image_path: 源图路径
        target_language: 目标语言，如 German / French / Japanese / Spanish
    """
    result = await image_gen.translate_image(image_path, target_language)
    return json.dumps(result, ensure_ascii=False, indent=2)


@function_tool
def list_generated_images() -> str:
    """列出已生成的所有图片文件（供用户回看）。"""
    files = sorted(config.images_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = [{"file": str(p), "url": f"/images/{p.name}"} for p in files[:30]]
    return json.dumps(out, ensure_ascii=False, indent=2)
