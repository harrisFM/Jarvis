"""The agent loop: streams a Claude response, speaks sentences as they form, executes tool calls through
the permission engine, and records everything to the audit log and episodic memory.

Manual loop (not the SDK tool runner) because "ask"-tier tools must pause the turn until a human answers."""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import anthropic

from jarvis.brain.chunker import SentenceChunker, strip_for_speech
from jarvis.brain.prompts import build_system_prompt, context_block
from jarvis.brain.router import Route, route
from jarvis.config import Settings
from jarvis.events import EventBus
from jarvis.memory.store import MemoryStore
from jarvis.policy.audit import AuditLog
from jarvis.policy.permissions import Decision, PermissionEngine, User, parse_confirmation
from jarvis.tools.registry import ToolContext, ToolRegistry

FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class Turn:
    id: str
    text: str
    user: User
    room: str
    session: str
    model: str = ""
    tier: str = ""
    effort: str = ""
    reply: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    ttft_ms: float | None = None
    total_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    rounds: int = 0
    stop_reason: str = ""
    error: str | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id, "model": self.model, "tier": self.tier, "effort": self.effort, "rounds": self.rounds,
            "ttft_ms": None if self.ttft_ms is None else round(self.ttft_ms), "total_ms": round(self.total_ms),
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens, "cache_write_tokens": self.cache_write_tokens,
            "tool_calls": len(self.tool_calls), "stop_reason": self.stop_reason, "error": self.error,
        }


class Agent:
    def __init__(self, settings: Settings, registry: ToolRegistry, permissions: PermissionEngine, audit: AuditLog,
                 memory: MemoryStore, bus: EventBus, client: Any | None = None, persona_extra: str = "") -> None:
        self.settings = settings
        self.registry = registry
        self.permissions = permissions
        self.audit = audit
        self.memory = memory
        self.bus = bus
        self.client = client if client is not None else _make_client(settings)
        self.system_prompt = build_system_prompt(settings, persona_extra)
        self.history: list[dict[str, Any]] = []
        self._turn_starts: list[int] = []
        self.metrics: list[dict[str, Any]] = []
        self._use_fallbacks = settings.fallbacks
        self._tz = ZoneInfo(settings.home_timezone) if settings.home_timezone else None
        self.current_task: asyncio.Task | None = None

    # ------------------------------------------------------------------ public API
    async def handle(self, text: str, user: User, room: str = "unknown", session: str = "default",
                     force_tier: str | None = None) -> Turn:
        turn = Turn(id=uuid.uuid4().hex[:8], text=text, user=user, room=room, session=session)
        started = time.perf_counter()
        await self.bus.publish("transcript", role="user", text=text, user=user.name, room=room, turn=turn.id)
        self.memory.log_turn(session, user.id, room, "user", text)

        # A bare yes/no while a confirmation is pending answers that confirmation instead of starting a turn.
        if self.permissions.pending:
            answer = parse_confirmation(text)
            if answer is not None:
                latest = self.permissions.pending[next(reversed(self.permissions.pending))]
                turn.tier = "confirmation"
                if self._may_confirm(user, latest):
                    self.permissions.resolve(latest.id, answer, by=f"voice:{user.id}")  # waiter publishes approval_resolved
                    turn.reply = "Understood." if answer else "Cancelled."
                else:
                    turn.reply = f"Only {latest.user.name} or another adult can confirm that."
                    await self.bus.publish("approval_refused", id=latest.id, by=user.name,
                                           reason="insufficient role to confirm")
                await self.bus.publish("speak", text=turn.reply, turn=turn.id)
                await self.bus.publish("transcript", role="assistant", text=turn.reply, turn=turn.id)
                turn.total_ms = (time.perf_counter() - started) * 1000
                return turn

        if self.client is None:
            turn.error = "No Anthropic credentials configured (set ANTHROPIC_API_KEY)."
            await self.bus.publish("error", text=turn.error, turn=turn.id)
            return turn

        r = route(text, self.settings, force=force_tier)
        turn.model, turn.tier, turn.effort = r.model, r.tier, r.effort
        await self.bus.publish("turn_started", turn=turn.id, model=r.model, tier=r.tier, effort=r.effort, reason=r.reason)

        self._append_user_turn(text, user, room)
        try:
            await self._run_loop(turn, r, started)
        except asyncio.CancelledError:
            self._drop_last_turn()
            turn.stop_reason = "interrupted"
            await self.bus.publish("interrupted", turn=turn.id)
            raise
        except anthropic.APIStatusError as e:
            self._drop_last_turn()
            turn.error = f"API error {e.status_code}: {e.message}"
            await self.bus.publish("error", text=turn.error, turn=turn.id)
        except anthropic.APIConnectionError as e:
            self._drop_last_turn()
            turn.error = f"Could not reach the model provider ({e.__class__.__name__})."
            await self.bus.publish("error", text=turn.error, turn=turn.id)
        except Exception as e:  # auth resolution errors, tool bugs that escaped, etc. — never kill the worker
            self._drop_last_turn()
            turn.error = f"{e.__class__.__name__}: {e}"
            await self.bus.publish("error", text=turn.error, turn=turn.id)
        finally:
            turn.total_ms = (time.perf_counter() - started) * 1000
            self.metrics.append(turn.summary())
            del self.metrics[:-200]
            await self.bus.publish("turn_finished", **turn.summary())
        if turn.reply:
            self.memory.log_turn(session, user.id, room, "assistant", turn.reply)
        return turn

    def _may_confirm(self, user: User, approval: Any) -> bool:
        """The requester, or anyone of equal/higher rank who is not themselves denied that action, may answer."""
        if user.id == approval.user.id:
            return True
        if user.rank < approval.user.rank:
            return False
        decision, _ = self.permissions.decide(approval.tool, approval.tool_input, user)
        return decision != Decision.DENY

    def reset(self) -> None:
        self.history.clear()
        self._turn_starts.clear()

    def export_history(self) -> list[dict[str, Any]]:
        out = []
        for m in self.history:
            content = m["content"]
            if isinstance(content, str):
                out.append({"role": m["role"], "content": content})
            else:
                blocks = []
                for b in content:
                    d = b if isinstance(b, dict) else b.model_dump(exclude_none=True)
                    blocks.append({k: v for k, v in d.items() if k not in ("signature",)})
                out.append({"role": m["role"], "content": blocks})
        return out

    # ------------------------------------------------------------------ loop
    async def _run_loop(self, turn: Turn, r: Route, started: float) -> None:
        tools = self.registry.definitions()
        if self.settings.web_search:
            tools = tools + [{"type": "web_search_20260209", "name": "web_search",
                              "max_uses": self.settings.web_search_max_uses}]
        chunker = SentenceChunker()
        reply_parts: list[str] = []

        for _ in range(self.settings.max_tool_rounds + 1):
            turn.rounds += 1
            message = await self._stream_once(turn, r, tools, chunker, reply_parts, started)
            self._accumulate_usage(turn, message)
            turn.stop_reason = message.stop_reason or ""

            if message.stop_reason == "refusal":
                text = "I can't help with that one."
                await self.bus.publish("speak", text=text, turn=turn.id)
                reply_parts.append(text)
                self.history.append({"role": "assistant", "content": text})
                break

            self.history.append({"role": "assistant", "content": message.content})

            if message.stop_reason == "pause_turn":
                continue
            if message.stop_reason != "tool_use":
                break

            tool_uses = [b for b in message.content if b.type == "tool_use"]
            results = []
            for tu in tool_uses:
                results.append(await self._execute_tool(turn, tu))
            self.history.append({"role": "user", "content": results})

        for s in chunker.flush():
            await self._speak(turn, s, reply_parts)
        turn.reply = " ".join(reply_parts).strip()
        await self.bus.publish("transcript", role="assistant", text=turn.reply, turn=turn.id)

    async def _stream_once(self, turn: Turn, r: Route, tools: list[dict[str, Any]], chunker: SentenceChunker,
                           reply_parts: list[str], started: float) -> Any:
        kwargs: dict[str, Any] = dict(
            model=r.model,
            max_tokens=4096,
            system=[{"type": "text", "text": self.system_prompt, "cache_control": {"type": "ephemeral"}}],
            tools=tools,
            messages=self.history,
            output_config={"effort": r.effort},
        )
        if self._use_fallbacks:
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        try:
            return await self._consume_stream(kwargs, turn, chunker, reply_parts, started)
        except anthropic.BadRequestError as e:
            if self._use_fallbacks and "fallback" in str(e).lower():
                self._use_fallbacks = False  # model/platform without server-side fallbacks: retry without
                kwargs.pop("betas", None)
                kwargs.pop("fallbacks", None)
                return await self._consume_stream(kwargs, turn, chunker, reply_parts, started)
            raise

    async def _consume_stream(self, kwargs: dict[str, Any], turn: Turn, chunker: SentenceChunker,
                              reply_parts: list[str], started: float) -> Any:
        async with self.client.beta.messages.stream(**kwargs) as stream:
            async for event in stream:
                et = getattr(event, "type", "")
                if et == "content_block_delta" and getattr(event.delta, "type", "") == "text_delta":
                    if turn.ttft_ms is None:
                        turn.ttft_ms = (time.perf_counter() - started) * 1000
                        await self.bus.publish("first_token", turn=turn.id, ttft_ms=round(turn.ttft_ms))
                    await self.bus.publish("assistant_delta", text=event.delta.text, turn=turn.id)
                    for s in chunker.feed(event.delta.text):
                        await self._speak(turn, s, reply_parts)
                elif et == "content_block_start" and getattr(event.content_block, "type", "") == "tool_use":
                    for s in chunker.flush():
                        await self._speak(turn, s, reply_parts)
                    await self.bus.publish("tool_call", turn=turn.id, name=event.content_block.name, status="pending")
            return await stream.get_final_message()

    async def _speak(self, turn: Turn, sentence: str, reply_parts: list[str]) -> None:
        clean = strip_for_speech(sentence)
        if clean:
            reply_parts.append(clean)
            await self.bus.publish("speak", text=clean, turn=turn.id)

    # ------------------------------------------------------------------ tools + policy
    async def _execute_tool(self, turn: Turn, tu: Any) -> dict[str, Any]:
        name, tool_input, tool_use_id = tu.name, dict(tu.input or {}), tu.id
        user, room = turn.user, turn.room
        t0 = time.perf_counter()
        decision, reason = self.permissions.decide(name, tool_input, user)
        approved_by: str | None = None
        is_error = False
        record: dict[str, Any] = {"name": name, "input": tool_input, "decision": decision.value}
        await self.bus.publish("tool_call", turn=turn.id, name=name, input=tool_input, status=decision.value, reason=reason)

        if decision == Decision.ASK:
            approval = self.permissions.request_approval(name, tool_input, user, reason)
            question = f"Confirmation needed: {_describe(name, tool_input)}. Say yes or no, or use the dashboard."
            await self.bus.publish("approval_requested", id=approval.id, tool=name, input=tool_input, reason=reason,
                                   user=user.name, room=room, turn=turn.id, question=question)
            await self.bus.publish("speak", text=question, turn=turn.id)
            ok, by = await self.permissions.wait(approval, self.settings.approval_timeout)
            await self.bus.publish("approval_resolved", id=approval.id, approved=ok, by=by)
            if ok:
                approved_by = by
                decision = Decision.ALLOW
            else:
                decision = Decision.DENY
                reason = "declined by the user" if by != "timeout" else "no confirmation received in time"

        if decision == Decision.DENY:
            result = f"Action not performed: {reason}."
            is_error = True
        else:
            tool = self.registry.get(name)
            if tool is None:
                result, is_error = f"Error: unknown tool {name}", True
            else:
                try:
                    ctx = ToolContext(user=user, room=room, session=turn.session, emit=self.bus.publish)
                    result = await tool.run(tool_input, ctx)
                    is_error = result.startswith("Error")
                except Exception as e:  # tool bugs must not kill the turn
                    result, is_error = f"Error: {e.__class__.__name__}: {e}", True

        duration = (time.perf_counter() - t0) * 1000
        self.audit.record(user_id=user.id, user_role=user.role, room=room, tool=name, tool_input=tool_input,
                          decision=record["decision"], approved_by=approved_by, result=result, is_error=is_error,
                          duration_ms=duration)
        record.update({"result": result, "is_error": is_error, "duration_ms": round(duration)})
        turn.tool_calls.append(record)
        await self.bus.publish("tool_result", turn=turn.id, name=name, result=result[:500], is_error=is_error,
                               duration_ms=round(duration))
        block: dict[str, Any] = {"type": "tool_result", "tool_use_id": tool_use_id, "content": result}
        if is_error:
            block["is_error"] = True
        return block

    # ------------------------------------------------------------------ history helpers
    def _append_user_turn(self, text: str, user: User, room: str) -> None:
        pending = None
        if self.permissions.pending:
            a = self.permissions.pending[next(reversed(self.permissions.pending))]
            pending = _describe(a.tool, a.tool_input)
        memories = [m["text"] for m in self.memory.recall(text, limit=5)]
        ctx = context_block(time_str=datetime.now(self._tz).strftime("%A %d %B %Y %H:%M"), room=room,
                            speaker=user.name, role=user.role, pending_approval=pending, memories=memories)
        self._turn_starts.append(len(self.history))
        self.history.append({"role": "user", "content": f"{ctx}\n\n{text}"})
        self._trim_history()

    def _drop_last_turn(self) -> None:
        if self._turn_starts:
            start = self._turn_starts.pop()
            del self.history[start:]

    def _trim_history(self) -> None:
        max_turns = self.settings.max_history_turns
        while len(self._turn_starts) > max_turns:
            cut = self._turn_starts[1]
            del self.history[:cut]
            self._turn_starts = [i - cut for i in self._turn_starts[1:]]

    @staticmethod
    def _accumulate_usage(turn: Turn, message: Any) -> None:
        u = getattr(message, "usage", None)
        if not u:
            return
        turn.input_tokens += getattr(u, "input_tokens", 0) or 0
        turn.output_tokens += getattr(u, "output_tokens", 0) or 0
        turn.cache_read_tokens += getattr(u, "cache_read_input_tokens", 0) or 0
        turn.cache_write_tokens += getattr(u, "cache_creation_input_tokens", 0) or 0


def _make_client(settings: Settings) -> Any | None:
    """Build the Anthropic client only when some credential source exists; the SDK itself defers the
    check to the first request, which would surface as a confusing error mid-conversation."""
    if settings.anthropic_api_key:
        return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return anthropic.AsyncAnthropic()
    profile_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "anthropic"
    if profile_dir.exists() and any(profile_dir.iterdir()):  # `ant auth login` profile
        return anthropic.AsyncAnthropic()
    return None


def _describe(tool: str, inp: dict[str, Any]) -> str:
    if tool == "ha_call_service":
        return f"{inp.get('domain')}.{inp.get('service')} on {inp.get('entity_id') or 'the selected devices'}"
    if tool == "send_message":
        return f"send \"{inp.get('text', '')[:80]}\" to {inp.get('recipient', 'someone')}"
    if tool == "forget_memory":
        return f"delete memory {inp.get('id')}"
    return f"{tool} {json.dumps(inp, default=str)[:120]}"
