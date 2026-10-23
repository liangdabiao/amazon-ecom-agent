"""FastAPI 入口：一个 SSE 聊天端点 + 静态托管，没有别的。

对比原 IvyeaOps 的 main.py：没有 CSRF、没有权限依赖、没有 lifespan 七个后台
任务——启动即可用。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from agents import Runner, SQLiteSession
from agents.stream_events import RawResponsesStreamEvent, RunItemStreamEvent
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import MAX_TURNS, build_agent
from . import chat_store
from .config import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ecom.server")

app = FastAPI(title="ecom-agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])  # 本机自用，放开无妨

app.mount("/images", StaticFiles(directory=str(config.images_dir)), name="images")


class ChatReq(BaseModel):
    message: str
    session_id: str = ""


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/api/chat")
async def chat(req: ChatReq):
    """对话端点：SSE 流式返回 delta / tool / tool_output / done / error。"""
    session_id = req.session_id or chat_store.new_session()
    session = SQLiteSession(session_id, str(config.chat_db))
    agent = build_agent()

    async def stream():
        yield _sse({"type": "session", "session_id": session_id})
        final_text = ""
        try:
            result = Runner.run_streamed(agent, req.message, max_turns=MAX_TURNS, session=session)
            async for event in result.stream_events():
                if isinstance(event, RawResponsesStreamEvent):
                    delta = getattr(event.data, "delta", None)
                    if delta:
                        yield _sse({"type": "delta", "text": delta})
                elif isinstance(event, RunItemStreamEvent):
                    raw = getattr(event.item, "raw_item", None)
                    if event.name == "tool_called":
                        name = getattr(raw, "name", "")
                        args = getattr(raw, "arguments", "")
                        yield _sse({"type": "tool", "name": name, "args": str(args)[:500]})
                    elif event.name == "tool_output":
                        out = getattr(event.item, "output", "")
                        yield _sse({"type": "tool_output",
                                    "preview": str(out)[:300]})
            final_text = str(result.final_output or "")
            yield _sse({"type": "done", "final": final_text})
            chat_store.record_turn(session_id, req.message, final_text)
        except Exception as exc:  # noqa: BLE001 — 错误原样送到前端，不静默
            logger.exception("chat failed")
            yield _sse({"type": "error", "message": f"{type(exc).__name__}: {exc}"})

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/api/sessions")
async def sessions():
    return chat_store.list_sessions()


@app.post("/api/sessions")
async def create_session():
    return {"id": chat_store.new_session()}


@app.delete("/api/sessions/{sid}")
async def remove_session(sid: str):
    chat_store.delete_session(sid)
    return {"ok": True}


@app.get("/api/sessions/{sid}/history")
async def history(sid: str):
    return chat_store.session_history(sid)


# SPA：单页聊天界面
_WEB = Path(__file__).resolve().parent.parent / "web"


@app.get("/")
async def index():
    return FileResponse(_WEB / "index.html")
