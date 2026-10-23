"""终端入口：python cli.py ["一句话任务"]  /  python cli.py 进入交互模式。"""
from __future__ import annotations

import asyncio
import sys

from agents import Runner, SQLiteSession
from agents.stream_events import RawResponsesStreamEvent, RunItemStreamEvent

from server.agent import MAX_TURNS, build_agent
from server.config import config

SESSION_ID = "cli"


async def run_turn(user_input: str) -> None:
    session = SQLiteSession(SESSION_ID, str(config.chat_db))
    agent = build_agent()
    result = Runner.run_streamed(agent, user_input, max_turns=MAX_TURNS, session=session)
    async for event in result.stream_events():
        if isinstance(event, RawResponsesStreamEvent):
            delta = getattr(event.data, "delta", None)
            if delta:
                print(delta, end="", flush=True)
        elif isinstance(event, RunItemStreamEvent) and event.name == "tool_called":
            name = getattr(getattr(event.item, "raw_item", None), "name", "")
            print(f"\n\033[33m⚙ {name} …\033[0m", flush=True)
    print()


async def main() -> None:
    if len(sys.argv) > 1:
        await run_turn(" ".join(sys.argv[1:]))
        return
    print("电商运营助手（CLI）· 输入任务，exit 退出")
    print("─" * 50)
    while True:
        try:
            user_input = input("\033[36m你> \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            break
        await run_turn(user_input)


if __name__ == "__main__":
    asyncio.run(main())
