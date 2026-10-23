"""Agent 定义：系统提示词 + 工具总表 + 任意 OpenAI 兼容模型。

对比原 IvyeaAgent：没有桥接令牌、没有审批流、没有降级链编排——
就是一个 Agent 实例，直来直去。
"""
from __future__ import annotations

from pathlib import Path

from agents import Agent, set_default_openai_client, set_tracing_disabled
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from .config import config
from .tools import ALL_TOOLS

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system.md"

MAX_TURNS = 30  # 单轮最多工具调用步数，防失控循环

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not config.llm_api_key:
            raise RuntimeError("LLM_API_KEY 未配置：请复制 .env.example 为 .env 并填写")
        _client = AsyncOpenAI(base_url=config.llm_base_url, api_key=config.llm_api_key)
        # 非 OpenAI 官方端点必须关 tracing（否则要求 OPENAI_API_KEY）
        set_tracing_disabled(True)
        set_default_openai_client(_client)
    return _client


def build_agent() -> Agent:
    system_prompt = SYSTEM_PROMPT_PATH.read_text("utf-8")
    return Agent(
        name="电商运营助手",
        instructions=system_prompt,
        model=OpenAIChatCompletionsModel(
            model=config.llm_model, openai_client=_get_client()),
        tools=ALL_TOOLS,
    )
