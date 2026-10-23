"""会话列表与历史（UI 展示用）。agent 的对话记忆由 SDK 的 SQLiteSession 负责，
这里只存"哪有哪些会话、每轮用户问了什么/答了什么"。"""
from __future__ import annotations

import sqlite3
import time
import uuid

from .config import config


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.chat_db))
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY, title TEXT, created_at REAL, updated_at REAL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS turn_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT, role TEXT, content TEXT, created_at REAL)""")
    return conn


def new_session() -> str:
    sid = uuid.uuid4().hex[:12]
    with _conn() as c:
        c.execute("INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?,?,?,?)",
                  (sid, "新对话", time.time(), time.time()))
    return sid


def list_sessions() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, title, updated_at FROM sessions ORDER BY updated_at DESC LIMIT 100"
        ).fetchall()
    return [{"id": r["id"], "title": r["title"], "updated_at": r["updated_at"]} for r in rows]


def delete_session(sid: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM sessions WHERE id=?", (sid,))
        c.execute("DELETE FROM turn_log WHERE session_id=?", (sid,))


def record_turn(sid: str, user_text: str, assistant_text: str) -> None:
    """一轮结束：落两条消息 + 用首句更新会话标题。"""
    now = time.time()
    with _conn() as c:
        c.execute("INSERT INTO turn_log (session_id, role, content, created_at) VALUES (?,?,?,?)",
                  (sid, "user", user_text, now))
        c.execute("INSERT INTO turn_log (session_id, role, content, created_at) VALUES (?,?,?,?)",
                  (sid, "assistant", assistant_text, now))
        title = c.execute(
            "SELECT title FROM sessions WHERE id=?", (sid,)).fetchone()
        if title and title["title"] in ("新对话", "", None):
            first = user_text.strip().replace("\n", " ")[:30]
            if first:
                c.execute("UPDATE sessions SET title=? WHERE id=?", (first, sid))
        c.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, sid))


def session_history(sid: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT role, content, created_at FROM turn_log WHERE session_id=? ORDER BY id",
            (sid,)).fetchall()
    return [{"role": r["role"], "content": r["content"], "created_at": r["created_at"]}
            for r in rows]
