"""生图链路（gpt-image 中转：提交 → 轮询 → 画布规范化）+ 图片翻译。

平移自 IvyeaOps `routers/listing/images.py` 与 `routers/image_translate.py` 的
核心，去掉 job/工作区/质检复核，落图改存本地 `data/images/`。
保真前言、裁剪安全区提示、input_fidelity 降级重试这些实战细节原样保留。
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Callable, Optional

import httpx
from PIL import Image, ImageOps

from ..config import config

logger = logging.getLogger("ecom.legacy.image_gen")

_SIZE_RE = re.compile(r"^\s*(\d{3,4})\s*[xX×]\s*(\d{3,4})\s*$")


def parse_size(value: str, fallback: tuple[int, int] = (1024, 1024)) -> tuple[int, int]:
    m = _SIZE_RE.match(str(value or "").strip().lower())
    if not m:
        return fallback
    w, h = int(m.group(1)), int(m.group(2))
    if not (320 <= w <= 4096 and 320 <= h <= 4096):
        return fallback
    return w, h


def normalise_canvas(raw: bytes, size: str, mode: str = "cover") -> bytes:
    """精确尺寸画布且不拉伸：cover（生成图，充满画布） / contain（实物图，留白）。"""
    target = parse_size(size)
    image = Image.open(io.BytesIO(raw)).convert("RGBA")
    if mode == "contain":
        fitted = ImageOps.contain(image, target, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", target, "#FFFFFF")
        canvas.alpha_composite(
            fitted, ((target[0] - fitted.width) // 2, (target[1] - fitted.height) // 2))
    else:
        canvas = ImageOps.fit(image, target, Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    out = io.BytesIO()
    canvas.convert("RGB").save(out, "PNG", compress_level=6)
    return out.getvalue()


def _save_image(raw: bytes, prefix: str = "gen") -> Path:
    p = config.images_dir / f"{prefix}_{uuid.uuid4().hex[:8]}.png"
    p.write_bytes(raw)
    return p


# ── 保真前言：按产品出场分级锁定参考图里的产品本体 ─────────────────────────────
def _fidelity_preamble(prompt: str, ref_count: int, presence: str = "supporting",
                       product_scale: float = 0.32) -> str:
    if not ref_count:
        return prompt
    accessory_rule = ("Reproduce ONLY the primary product unit. If the reference photo is a "
                      "bundle shot, IGNORE the loose extras (memory cards, cables, straps, manuals, "
                      "packaging) — do NOT carry them into this scene. ")
    scale_rule = ""
    if presence == "environmental":
        scale_rule = (f"In this composition the product intentionally appears SMALL — roughly "
                      f"{max(5, int(product_scale * 100))}% of the frame, naturally placed in a "
                      "believable real scene. ")
    elif presence == "supporting":
        scale_rule = (f"The product shares the stage, occupying roughly {int(product_scale * 100)}% "
                      "of the frame as one element of a designed composition — not a full-frame "
                      "hero close-up. ")
    return (
        "CRITICAL — IMMUTABLE PRODUCT TRUTH: REFERENCE IMAGE 1 shows the EXACT sellable product. "
        "Reproduce it identically: same silhouette, geometry, proportions, colors, materials, "
        "controls, ports, logos and printed markings. "
        f"{accessory_rule}{scale_rule}"
        "Change ONLY the environment, camera, composition, lighting and the exact artwork copy "
        "explicitly requested by the prompt. Do NOT redesign, recolor, relabel or simplify the "
        "product.\n\n"
    ) + prompt


def _crop_safe_zone_note(target_size: str, provider_size: str) -> str:
    """成图会被中心裁剪时，提示模型把关键内容画进会保留的安全区。"""
    tw, th = parse_size(target_size)
    pw, ph = parse_size(provider_size)
    scale = max(tw / pw, th / ph)
    disp_w, disp_h = pw * scale, ph * scale
    crop_v = (disp_h - th) / disp_h if disp_h else 0.0
    crop_h = (disp_w - tw) / disp_w if disp_w else 0.0
    if max(crop_v, crop_h) <= 0.10:
        return ""
    if crop_v >= crop_h:
        each = round(crop_v * 100 / 2)
        keep = 100 - each * 2
        band = "central horizontal band"
    else:
        each = round(crop_h * 100 / 2)
        keep = 100 - each * 2
        band = "central vertical band"
    return (
        f"CANVAS CROP NOTICE: you are painting on a {pw}×{ph} canvas, but the delivered image is "
        f"{tw}×{th} after CENTER-CROPPING — the outer ~{each}% on each side WILL BE CUT OFF. Compose "
        f"everything essential (headline, product, key elements) inside the {band} (~{keep}% surviving). "
        "Background must extend fully to all edges of the final image."
    )


def _image_cfg_ready() -> bool:
    if not config.image_ready():
        raise RuntimeError(
            "生图未配置：请在 .env 填 IMAGE_BASE_URL / IMAGE_API_KEY（需有 gpt-image 权限的中转）")
    return True


def _provider_size_for(target: str) -> str:
    tw, th = parse_size(target)
    ratio = tw / th if th else 1.0
    if abs(ratio - 1) < .12:
        return "1024x1024"
    if ratio >= 1.9:
        # 宽幅（如 A+ 1464×600）直接按目标比例下单——供应商能原生渲染宽幅，
        # 硬套 1536×1024 再裁会切掉标题（踩过坑）。
        return f"{tw}x{th}"
    if ratio > 1:
        return "1536x1024"
    return "1024x1536"


def _parse_task_payload(payload: dict) -> dict:
    task_data = payload.get("data") if isinstance(payload, dict) else {}
    task_data = task_data if isinstance(task_data, dict) else {}
    status = str(task_data.get("status") or "processing").strip().lower()
    if status == "completed":
        result = task_data.get("result") if isinstance(task_data.get("result"), dict) else {}
        images = result.get("images") if isinstance(result.get("images"), list) else []
        url = images[0].get("url") if images and isinstance(images[0], dict) else ""
        if isinstance(url, list):
            url = url[0] if url else ""
        if url:
            return {"status": "completed", "provider_url": str(url)}
        return {"status": "failed", "error": "任务完成但未返回图片 URL"}
    if status == "failed":
        detail = (task_data.get("error") or task_data.get("message")
                  or task_data.get("result") or "上游生图任务失败")
        return {"status": "failed", "error": str(detail)[:500]}
    return {"status": status or "processing"}


async def _submit(prompt: str, size: str, ref_data_uris: list[str]) -> str:
    _image_cfg_ready()
    provider_size = _provider_size_for(size)
    note = _crop_safe_zone_note(size, provider_size)
    if note:
        prompt = f"{note}\n\n{prompt}"
    base_body = {"model": "gpt-image-2", "prompt": prompt, "n": 1, "size": provider_size}
    if ref_data_uris:
        base_body["image_urls"] = ref_data_uris[:2]

    # input_fidelity:"high" 保住参考图的产品细节；中转可能不认这个字段，降级重试。
    attempts = ([{**base_body, "input_fidelity": "high"}, base_body]
                if ref_data_uris else [base_body])

    async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=20)) as client:
        resp = None
        for idx, attempt in enumerate(attempts):
            resp = await client.post(
                f"{config.image_base_url}/images/generations",
                headers={"Authorization": f"Bearer {config.image_api_key}",
                         "Content-Type": "application/json"},
                json=attempt)
            if resp.status_code == 200:
                break
            if not (idx == 0 and resp.status_code in {400, 422}):
                break
        if resp is None or resp.status_code != 200:
            raise RuntimeError(f"生图提交失败: {resp.text[:300] if resp is not None else '无响应'}")
        task_id = resp.json().get("data", [{}])[0].get("task_id")
        if not task_id:
            raise RuntimeError(f"生图未返回 task_id: {resp.text[:300]}")
        return str(task_id)


async def _poll(task_id: str, size: str, on_tick: Optional[Callable[[int], None]] = None,
                deadline_seconds: int = 8 * 60) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,160}", task_id):
        raise RuntimeError("无效的生图任务 ID")
    loop = asyncio.get_event_loop()
    deadline = loop.time() + deadline_seconds
    async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=20)) as client:
        while loop.time() < deadline:
            await asyncio.sleep(5)
            if on_tick:
                on_tick(0)
            try:
                poll = await client.get(
                    f"{config.image_base_url}/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {config.image_api_key}"})
            except Exception:
                continue  # 瞬时网络错误——任务已付费，继续等
            if poll.status_code in (429,) or poll.status_code >= 500:
                continue
            if poll.status_code != 200:
                raise RuntimeError(f"生图任务查询失败 HTTP {poll.status_code}: {poll.text[:240]}")
            state = _parse_task_payload(poll.json())
            if state["status"] == "failed":
                raise RuntimeError(state.get("error") or "上游生图任务失败")
            if state["status"] != "completed":
                continue
            async with httpx.AsyncClient(timeout=60) as dl:
                r = await dl.get(state["provider_url"])
                r.raise_for_status()
                return r.content
    raise RuntimeError("生图等待超过 8 分钟（任务未重复提交，可稍后重试）")


async def _to_data_uri(source: str) -> str:
    """本地路径或 URL → data URI（外部生图服务够不着本地文件）。"""
    if source.startswith(("http://", "https://")):
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(source)
            r.raise_for_status()
            raw = r.content
        mime = mimetypes.guess_type(source.split("?", 1)[0])[0] or "image/png"
    else:
        p = Path(source)
        if not p.is_absolute():
            p = config.data_dir / source
        if not p.is_file():
            raise RuntimeError(f"参考图不存在: {source}")
        raw = p.read_bytes()
        mime = mimetypes.guess_type(str(p))[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


async def generate_image(prompt: str, size: str = "1024x1024",
                         reference_image: str = "",
                         presence: str = "supporting") -> dict:
    """一次完整生成：可选参考图 → 保真前言 → 提交 → 轮询 → 规范化 → 落盘。

    presence: hero/supporting（锁产品本体）/ environmental（产品小、场景为主）。
    返回 {file, url}。"""
    refs = [await _to_data_uri(reference_image)] if reference_image else []
    full_prompt = _fidelity_preamble(prompt, len(refs), presence)
    task_id = await _submit(full_prompt, size, refs)
    raw = await _poll(task_id, size, on_tick=lambda t: None)
    final = normalise_canvas(raw, size, mode="cover")
    p = _save_image(final, "gen")
    return {"file": str(p), "url": f"/images/{p.name}", "size": size}


async def translate_image(image_path: str, target_language: str) -> dict:
    """图片翻译：逐像素复现原图，唯一改动是图上文字换成目标语言。

    多站点卖家一套图铺多站点的核心工具。"""
    _image_cfg_ready()
    src_uri = await _to_data_uri(image_path)
    provider_size = _provider_size_for("1024x1024")  # 先占位，实际按原图比例
    try:
        with Image.open(io.BytesIO(base64.b64decode(src_uri.split(",", 1)[1]))) as im:
            w, h = im.size
        ratio = w / h if h else 1.0
        if abs(ratio - 1) < .12:
            provider_size = "1024x1024"
        elif ratio >= 1.9:
            provider_size = "1536x1024"
        elif ratio > 1:
            provider_size = "1536x1024"
        else:
            provider_size = "1024x1536"
    except Exception:
        pass

    prompt = (
        f"Reproduce this image pixel-perfectly. The ONLY change: translate all visible text "
        f"(headlines, callouts, labels, feature text) into {target_language}. Keep the exact same "
        "layout, product, colors, fonts style and composition. Do not add, remove or redesign any "
        "element. Do not change the product. The translation must be natural, native-sounding "
        "e-commerce copy — not literal word-by-word translation."
    )
    body = {"model": "gpt-image-2", "prompt": prompt, "n": 1, "size": provider_size,
            "image_urls": [src_uri]}
    async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=20)) as client:
        resp = await client.post(
            f"{config.image_base_url}/images/generations",
            headers={"Authorization": f"Bearer {config.image_api_key}",
                     "Content-Type": "application/json"},
            json={**body, "input_fidelity": "high"})
        if resp.status_code != 200:
            resp = await client.post(
                f"{config.image_base_url}/images/generations",
                headers={"Authorization": f"Bearer {config.image_api_key}",
                         "Content-Type": "application/json"},
                json=body)
        if resp.status_code != 200:
            raise RuntimeError(f"翻译图提交失败: {resp.text[:300]}")
        task_id = resp.json().get("data", [{}])[0].get("task_id")
        if not task_id:
            raise RuntimeError(f"翻译图未返回 task_id: {resp.text[:300]}")

    raw = await _poll(str(task_id), provider_size)
    final = normalise_canvas(raw, f"{provider_size.split('x')[0]}x{provider_size.split('x')[1]}",
                             mode="cover")
    p = _save_image(final, "trans")
    return {"file": str(p), "url": f"/images/{p.name}",
            "source": image_path, "language": target_language}
