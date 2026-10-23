"""集中配置：全部来自 .env，一读即用，没有第二层。

对比原 IvyeaOps 的两层配置（.env + hub_settings.json 150 个键）——这里故意
只有一层。所有键见 .env.example。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _s(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or "").strip()


class Config:
    # LLM
    llm_base_url: str = _s("LLM_BASE_URL", "https://api.deepseek.com/v1")
    llm_api_key: str = _s("LLM_API_KEY")
    llm_model: str = _s("LLM_MODEL", "deepseek-chat")
    llm_vision_model: str = _s("LLM_VISION_MODEL")

    # 生图（gpt-image 中转）
    image_base_url: str = _s("IMAGE_BASE_URL")
    image_api_key: str = _s("IMAGE_API_KEY")

    # 市场数据源
    sorftime_key: str = _s("SORFTIME_KEY")
    sellersprite_key: str = _s("SELLERSPRITE_KEY")

    # 领星（只读）
    lingxing_host: str = _s("LINGXING_HOST").rstrip("/")
    lingxing_app_id: str = _s("LINGXING_APP_ID")
    lingxing_app_secret: str = _s("LINGXING_APP_SECRET")

    # 服务
    host: str = _s("HOST", "127.0.0.1")
    port: int = int(_s("PORT", "8100") or 8100)

    # 目录
    data_dir: Path = ROOT / "data"
    images_dir: Path = data_dir / "images"
    reports_dir: Path = data_dir / "reports"
    knowledge_dir: Path = ROOT / "knowledge"
    chat_db: Path = data_dir / "chat.db"

    def image_ready(self) -> bool:
        return bool(self.image_base_url and self.image_api_key)

    def lingxing_ready(self) -> bool:
        return bool(self.lingxing_host and self.lingxing_app_id and self.lingxing_app_secret)


config = Config()

for d in (config.data_dir, config.images_dir, config.reports_dir):
    d.mkdir(parents=True, exist_ok=True)
