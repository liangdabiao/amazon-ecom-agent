"""Amazon 商品页采集：本机 curl 直连 → 本机无头浏览器兜底 → Sorftime 兜底。

平移自 IvyeaOps `routers/listing/scrape.py`，去掉路由/job/项目库，保留全部
采集智慧：cookie jar 过反爬、Windows 安全的 subprocess 模式、原图 URL 还原、
DOM 轮播图挖掘。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

import httpx

from ..config import config
from . import sorftime as _sft

logger = logging.getLogger("ecom.legacy.scrape")

_REAL_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

_MKT_DOMAIN = {
    "US": "amazon.com", "UK": "amazon.co.uk", "DE": "amazon.de", "JP": "amazon.co.jp",
    "FR": "amazon.fr", "IT": "amazon.it", "ES": "amazon.es", "CA": "amazon.ca",
    "AU": "amazon.com.au", "MX": "amazon.com.mx", "IN": "amazon.in", "NL": "amazon.nl",
    "SE": "amazon.se", "PL": "amazon.pl", "AE": "amazon.ae", "SG": "amazon.sg",
}


def _amazon_domain(marketplace: str) -> str:
    return _MKT_DOMAIN.get((marketplace or "US").upper(), "amazon.com")


def _no_window_kwargs() -> dict:
    """Windows 下 subprocess 不弹黑窗。"""
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {"startupinfo": si, "creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


# 同一张照片在 Amazon 页面里以多个尺寸出现，media id 相同：
#   .../images/I/71abc._AC_SX679_.jpg  ← 缩略图
#   .../images/I/71abc.jpg             ← 原图（全分辨率）
# 按 media id 去重，并去掉尺寸修饰符把缩略图还原成原图。
_MEDIA_RE = re.compile(
    r"^(https?://.+/images/I/)([A-Za-z0-9_+%-]+?)(?:\._[^./]*)?\.(jpg|jpeg|png)$", re.I)


def _media_key(url: str) -> str:
    m = _MEDIA_RE.match(url.split("?")[0])
    return m.group(2) if m else url


def _hires_url(url: str) -> str:
    m = _MEDIA_RE.match(url.split("?")[0])
    return f"{m.group(1)}{m.group(2)}.{m.group(3)}" if m else url


def parse_amazon_html(html_text: str) -> dict:
    """从原始 HTML 抽 title / bullets / 全套主图（hiRes→large→轮播图三级来源）。"""
    import html as _html
    images: list[str] = []
    seen: set[str] = set()
    for pat in (r'"hiRes"\s*:\s*"(https?://[^"\\]+)"', r'"large"\s*:\s*"(https?://[^"\\]+)"'):
        if images:
            break
        for m in re.finditer(pat, html_text):
            u = m.group(1)
            key = _media_key(u)
            if key not in seen:
                seen.add(key)
                images.append(u)
            if len(images) >= 7:
                break

    # 无头浏览器渲染后的 DOM：轮播缩略图把全套主图带在 data-a-dynamic-image 里
    if not images:
        for m in re.finditer(r'data-a-dynamic-image="([^"]*)"', html_text):
            blob = _html.unescape(m.group(1))
            for um in re.finditer(r'"(https?://[^"]+)"\s*:\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]', blob):
                if min(int(um.group(2)), int(um.group(3))) < 500:
                    continue  # 图标/色块，不是主图
                full = _hires_url(um.group(1))
                key = _media_key(full)
                if key not in seen:
                    seen.add(key)
                    images.append(full)
                if len(images) >= 7:
                    break
            if len(images) >= 7:
                break

    if not images:
        m = (re.search(r'id="landingImage"[^>]*data-old-hires="(https?://[^"]+)"', html_text)
             or re.search(r'id="landingImage"[^>]*src="(https?://[^"]+)"', html_text))
        if m:
            images.append(m.group(1))

    tm = re.search(r'id="productTitle"[^>]*>(.*?)</', html_text, re.S)
    title = _html.unescape(re.sub(r"\s+", " ", tm.group(1)).strip()) if tm else ""

    bullets: list[str] = []
    fb = re.search(r'id="feature-bullets"(.*?)</ul>', html_text, re.S)
    if fb:
        for bm in re.finditer(r'class="a-list-item[^"]*"[^>]*>(.*?)</span>', fb.group(1), re.S):
            t = _html.unescape(re.sub(r"<[^>]+>", "", bm.group(1)))
            t = re.sub(r"\s+", " ", t).strip()
            if t and t not in bullets:
                bullets.append(t)

    return {"title": title, "bullets": bullets[:5], "description": "", "imageUrls": images}


def _is_blocked(html_text: str) -> bool:
    return (len(html_text) < 50_000
            or bool(re.search(r"Type the characters you see in this image", html_text, re.I))
            or bool(re.search(r"we just need to make sure you're not a robot", html_text, re.I)))


async def _scrape_native(asin: str, marketplace: str, attempts: int = 5,
                         on_attempt: Optional[Callable[[int, int], None]] = None) -> Optional[dict]:
    """curl 直连 + cookie jar 过反爬。关键经验（别"改进"）：
    - 请求保持最小化（只有 UA）——更丰富的浏览器头反而更容易被拦；
    - cookie jar 跨重试携带——挑战页会种下会话 cookie，之后就容易过；
    - subprocess.run 在线程里跑（Windows 下 asyncio 子进程在 uvicorn 的事件循环上
      会 NotImplementedError，这是踩过坑换来的写法）。"""
    curl = shutil.which("curl")
    if not curl:
        logger.warning("curl 不在 PATH 上 — 无法本机直连采集 (asin=%s)", asin)
        return None
    url = f"https://www.{_amazon_domain(marketplace)}/dp/{asin}"
    fd, jar = tempfile.mkstemp(prefix="ecom_ck_", suffix=".txt")
    os.close(fd)
    args = [curl, "-sS", "-L", "--max-time", "25", "--compressed",
            "-A", _REAL_UA, "-c", jar, "-b", jar, url]
    try:
        for i in range(attempts):
            if on_attempt:
                on_attempt(i + 1, attempts)
            try:
                cp = await asyncio.to_thread(
                    subprocess.run, args,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30,
                    **_no_window_kwargs())
                out = cp.stdout or b""
            except Exception:
                out = b""
            html_text = (out or b"").decode("utf-8", "replace")
            if not _is_blocked(html_text):
                parsed = parse_amazon_html(html_text)
                if parsed.get("imageUrls"):
                    logger.info("[native] %s 第%d次成功: %d图", asin, i + 1, len(parsed["imageUrls"]))
                    return parsed
            logger.info("[native] %s 第%d次被拦/无图", asin, i + 1)
            if i < attempts - 1:
                await asyncio.sleep(2.0)
        return None
    finally:
        try:
            os.remove(jar)
        except OSError:
            pass


def browser_bin() -> Optional[str]:
    """找本机 Chromium 系浏览器（Windows 自带 Edge，等于零安装）。"""
    for name in ("google-chrome", "google-chrome-stable", "chromium",
                 "chromium-browser", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    candidates: list[Path] = []
    if os.name == "nt":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        for root in (pf, pf86, local):
            if not root:
                continue
            candidates += [Path(root) / "Google/Chrome/Application/chrome.exe",
                           Path(root) / "Microsoft/Edge/Application/msedge.exe"]
    elif sys.platform == "darwin":
        candidates += [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                       Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                       Path("/Applications/Chromium.app/Contents/MacOS/Chromium")]
    for c in candidates:
        try:
            if c.is_file():
                return str(c)
        except OSError:
            continue
    return None


async def _scrape_browser(asin: str, marketplace: str) -> Optional[dict]:
    """本机浏览器 --dump-dom 渲染兜底。一次性 profile，绝不碰用户真实会话。"""
    browser = browser_bin()
    if not browser:
        return None
    url = f"https://www.{_amazon_domain(marketplace)}/dp/{asin}"
    profile = tempfile.mkdtemp(prefix="ecom_cdp_")
    args = [browser, "--headless=new", "--disable-gpu", "--disable-extensions",
            "--disable-background-networking", "--no-first-run",
            "--no-default-browser-check", "--mute-audio",
            f"--user-data-dir={profile}", "--window-size=1280,2400",
            "--virtual-time-budget=15000", f"--user-agent={_REAL_UA}",
            "--dump-dom", url]
    if os.name != "nt":
        args.insert(1, "--no-sandbox")
    try:
        cp = await asyncio.to_thread(
            subprocess.run, args,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=90,
            **_no_window_kwargs())
        dom = (cp.stdout or b"").decode("utf-8", "replace")
    except Exception as exc:
        logger.info("[browser] %s 启动失败: %s", asin, exc)
        return None
    finally:
        shutil.rmtree(profile, ignore_errors=True)

    blocked = (bool(re.search(r"Type the characters you see in this image", dom, re.I))
               or bool(re.search(r"we just need to make sure you're not a robot", dom, re.I)))
    parsed = parse_amazon_html(dom) if not blocked else {}
    return parsed if parsed.get("imageUrls") else None


async def _scrape_sorftime_fallback(asin: str, marketplace: str) -> dict:
    """最后兜底：Sorftime product_detail。只有 1 张白底主图，拿不到全套。"""
    data: dict = {}
    try:
        async with _sft._make_client() as client:
            _, raw, err = await _sft._safe_call(
                client, "product_detail", {"asin": asin, "amz_site": marketplace}, 1)
            rec = _sft.record(raw) if (raw and not err) else {}
            if rec.get("title"):
                data["title"] = str(rec["title"]).strip()
            if rec.get("main_image"):
                data["imageUrls"] = [str(rec["main_image"]).strip()]
            desc_text = str(rec.get("description") or "").strip()
            if desc_text:
                parts = [p.strip() for p in re.split(r"<br>|\n", desc_text) if p.strip()]
                if parts:
                    data["bullets"] = parts[:5]
                    data["description"] = desc_text
    except Exception:
        logger.debug("sorftime 兜底失败（旁路）", exc_info=True)
    return data


async def scrape_product(asin: str, marketplace: str = "US") -> dict:
    """采集一条龙：curl → 本机浏览器 → Sorftime。返回
    {title, bullets, description, imageUrls, scrape_source, full_images_available}。"""
    data: dict = {}
    native_ok = browser_ok = False

    nd = await _scrape_native(asin, marketplace)
    if nd and nd.get("imageUrls"):
        data, native_ok = nd, True

    if not native_ok:
        bd = await _scrape_browser(asin, marketplace)
        if bd and bd.get("imageUrls"):
            data, browser_ok = bd, True

    if not data.get("title") and not data.get("bullets"):
        fb = await _scrape_sorftime_fallback(asin, marketplace)
        if fb:
            data = {**fb, **{k: v for k, v in data.items() if v}}

    image_urls = data.get("imageUrls") or []
    data["scrape_source"] = ("native" if native_ok else "browser" if browser_ok
                             else "sorftime" if image_urls else "none")
    data["full_images_available"] = native_ok or browser_ok
    return data


async def download_images(urls: list[str], asin: str) -> list[str]:
    """把采集到的图下载到 data/images/<asin>/，返回本地路径列表（供生图做参考图）。"""
    out: list[str] = []
    target = config.images_dir / (asin or "misc")
    target.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=30) as client:
        for i, url in enumerate(urls[:7]):
            try:
                r = await client.get(url, headers={"User-Agent": _REAL_UA})
                r.raise_for_status()
                ext = ".jpg" if ".png" not in url.lower() else ".png"
                p = target / f"img_{i}{ext}"
                p.write_bytes(r.content)
                out.append(str(p))
            except Exception as exc:
                logger.warning("下载图失败 %s: %s", url, exc)
    return out
