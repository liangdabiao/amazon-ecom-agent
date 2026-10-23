"""本地知识库检索：knowledge/ 目录下的 markdown，零依赖关键词打分。

原系统的知识库走本地向量检索（ONNX embedding）；简化版用词面重合度打分，
对"查政策/查费用/查流程"这类精确关键词场景足够用，且完全离线。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from agents import function_tool

from ..config import config

_CHUNK = 600          # 每块字符数
_OVERLAP = 80


def _load_docs() -> list[dict]:
    docs: list[dict] = []
    if not config.knowledge_dir.is_dir():
        return docs
    for p in sorted(config.knowledge_dir.rglob("*.md")):
        try:
            text = p.read_text("utf-8", errors="replace")
        except OSError:
            continue
        rel = str(p.relative_to(config.knowledge_dir))
        # 滑窗切块
        for i in range(0, max(len(text), 1), _CHUNK - _OVERLAP):
            chunk = text[i:i + _CHUNK]
            if chunk.strip():
                docs.append({"source": rel, "offset": i, "text": chunk})
            if i + _CHUNK >= len(text):
                break
    return docs


def _terms(query: str) -> list[str]:
    """中文按 2-gram、英文按小写单词切。"""
    query = query.lower()
    words = re.findall(r"[a-z0-9]{2,}", query)
    cjk = re.findall(r"[\u4e00-\u9fff]", query)
    bigrams = [cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1)]
    return list(dict.fromkeys(words + bigrams))


@function_tool
def knowledge_search(query: str) -> str:
    """检索本地知识库（knowledge/ 目录的 markdown 文档：亚马逊政策、费用、FBA、
    Listing 规则、SP-API 等运营知识）。回答事实性问题前先查这里，引用时注明来源文件。

    Args:
        query: 要查的问题关键词，如 "FBA fees" / "跟卖政策" / "标题字符限制"
    """
    docs = _load_docs()
    if not docs:
        return ("知识库为空。把运营知识 markdown 放进项目 knowledge/ 目录后即可检索"
                "（已内置知识可直接放 IvyeaAgent 仓库 knowledge_base/ 下的文件）。")
    terms = _terms(query)
    if not terms:
        return "查询词太短，请给出更具体的关键词。"
    scored = []
    for doc in docs:
        low = doc["text"].lower()
        score = sum(low.count(t) for t in terms)
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return f"知识库里没有找到与「{query}」相关的内容。"
    hits = []
    for score, doc in scored[:4]:
        hits.append({"source": doc["source"], "relevance": score, "excerpt": doc["text"].strip()})
    return json.dumps({"query": query, "results": hits}, ensure_ascii=False, indent=2)
