"""Built-in tools: time, memory, todos, timers, notifications, messaging."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from jarvis.config import Settings
from jarvis.memory.store import MemoryStore
from jarvis.tools.registry import ToolContext, ToolRegistry


class TimerService:
    def __init__(self, publish) -> None:
        self.publish = publish
        self.timers: dict[str, dict[str, Any]] = {}

    def set(self, seconds: float, label: str, room: str, user_id: str) -> dict[str, Any]:
        tid = uuid.uuid4().hex[:6]
        fire_at = time.time() + seconds
        task = asyncio.get_event_loop().create_task(self._fire(tid, seconds))
        self.timers[tid] = {"id": tid, "label": label, "fire_at": fire_at, "room": room, "user_id": user_id, "task": task}
        return self.describe(tid)

    async def _fire(self, tid: str, seconds: float) -> None:
        await asyncio.sleep(seconds)
        t = self.timers.pop(tid, None)
        if t:
            await self.publish("timer_fired", id=tid, label=t["label"], room=t["room"],
                               speak=f"Timer{': ' + t['label'] if t['label'] else ''} is done.")

    def cancel(self, tid: str) -> bool:
        t = self.timers.pop(tid, None)
        if not t:
            return False
        t["task"].cancel()
        return True

    def describe(self, tid: str) -> dict[str, Any]:
        t = self.timers[tid]
        return {"id": tid, "label": t["label"], "remaining_s": max(0, round(t["fire_at"] - time.time())), "room": t["room"]}

    def list(self) -> list[dict[str, Any]]:
        return [self.describe(t) for t in list(self.timers)]


def register_basic_tools(reg: ToolRegistry, settings: Settings, memory: MemoryStore, timers: TimerService) -> None:
    tz = ZoneInfo(settings.home_timezone) if settings.home_timezone else None

    async def get_current_time(_: dict[str, Any], __: ToolContext) -> str:
        now = datetime.now(tz)
        return now.strftime("%A %d %B %Y, %H:%M (%Z)")

    reg.add("get_current_time", "Get the current local date and time.", {"properties": {}}, get_current_time)

    async def remember(inp: dict[str, Any], ctx: ToolContext) -> str:
        fid = memory.remember(inp["fact"], user_id=ctx.user.id, category=inp.get("category", "general"))
        await ctx.event("memory_changed", action="remember", id=fid)
        return f"Remembered (id {fid})."

    reg.add(
        "remember",
        "Store a durable fact or preference about the household or a person so it can be recalled later. "
        "Use for things the user tells you to remember or clearly wants kept (names, preferences, routines).",
        {"properties": {"fact": {"type": "string"}, "category": {"type": "string",
                        "enum": ["general", "preference", "person", "place", "routine", "reminder"]}},
         "required": ["fact", "category"]},
        remember,
    )

    async def recall(inp: dict[str, Any], _: ToolContext) -> str:
        rows = memory.recall(inp["query"], limit=8)
        if not rows:
            return "No matching memories."
        return "\n".join(f"[{r['id']}] ({r['category']}) {r['text']}" for r in rows)

    reg.add("recall_memory", "Search stored memories about the household, people and preferences.",
            {"properties": {"query": {"type": "string"}}, "required": ["query"]}, recall)

    async def forget(inp: dict[str, Any], ctx: ToolContext) -> str:
        ok = memory.forget(int(inp["id"]))
        await ctx.event("memory_changed", action="forget", id=inp["id"])
        return "Forgotten." if ok else "No such memory."

    reg.add("forget_memory", "Delete a stored memory by id.", {"properties": {"id": {"type": "integer"}}, "required": ["id"]}, forget)

    async def set_timer(inp: dict[str, Any], ctx: ToolContext) -> str:
        secs = float(inp["seconds"])
        if secs <= 0 or secs > 86400:
            return "Error: timer must be between 1 second and 24 hours."
        t = timers.set(secs, inp.get("label", ""), ctx.room, ctx.user.id)
        await ctx.event("timers_changed", timers=timers.list())
        return f"Timer {t['id']} set for {int(secs)} seconds" + (f" ({t['label']})." if t["label"] else ".")

    reg.add("set_timer", "Start a countdown timer. Convert minutes/hours to seconds first.",
            {"properties": {"seconds": {"type": "number"}, "label": {"type": "string"}}, "required": ["seconds", "label"]},
            set_timer)

    async def list_timers(_: dict[str, Any], __: ToolContext) -> str:
        ts = timers.list()
        return "No timers running." if not ts else "\n".join(
            f"{t['id']}: {t['label'] or 'timer'} — {t['remaining_s']}s left" for t in ts)

    reg.add("list_timers", "List running timers.", {"properties": {}}, list_timers)

    async def cancel_timer(inp: dict[str, Any], ctx: ToolContext) -> str:
        ok = timers.cancel(inp["id"])
        await ctx.event("timers_changed", timers=timers.list())
        return "Cancelled." if ok else "No such timer."

    reg.add("cancel_timer", "Cancel a running timer by id.", {"properties": {"id": {"type": "string"}}, "required": ["id"]},
            cancel_timer)

    async def add_todo(inp: dict[str, Any], ctx: ToolContext) -> str:
        tid = memory.add_todo(inp["text"], user_id=ctx.user.id)
        await ctx.event("todos_changed", todos=memory.list_todos())
        return f"Added to the list (id {tid})."

    reg.add("add_todo", "Add an item to the household to-do / shopping list.",
            {"properties": {"text": {"type": "string"}}, "required": ["text"]}, add_todo)

    async def list_todos(_: dict[str, Any], __: ToolContext) -> str:
        items = memory.list_todos()
        return "The list is empty." if not items else "\n".join(f"[{i['id']}] {i['text']}" for i in items)

    reg.add("list_todos", "List open to-do / shopping items.", {"properties": {}}, list_todos)

    async def complete_todo(inp: dict[str, Any], ctx: ToolContext) -> str:
        ok = memory.complete_todo(int(inp["id"]))
        await ctx.event("todos_changed", todos=memory.list_todos())
        return "Done." if ok else "No such item."

    reg.add("complete_todo", "Mark a to-do item as done by id.",
            {"properties": {"id": {"type": "integer"}}, "required": ["id"]}, complete_todo)

    async def send_message(inp: dict[str, Any], ctx: ToolContext) -> str:
        text = inp["text"]
        if settings.telegram_bot_token and settings.telegram_chat_id:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json={"chat_id": settings.telegram_chat_id, "text": f"[{inp.get('recipient', 'household')}] {text}"},
                )
                if r.status_code != 200:
                    return f"Error: Telegram returned {r.status_code}."
            return "Message sent via Telegram."
        await ctx.event("notification", title=f"Message to {inp.get('recipient', 'household')}", text=text)
        return "Message delivered to the dashboard (no messaging provider configured)."

    reg.add(
        "send_message",
        "Send a text message to a person or the household channel. Always confirm the wording with the user first.",
        {"properties": {"recipient": {"type": "string"}, "text": {"type": "string"}}, "required": ["recipient", "text"]},
        send_message,
    )
