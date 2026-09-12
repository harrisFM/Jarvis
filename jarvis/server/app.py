"""FastAPI server: REST + WebSocket API and the dashboard. One household conversation, many clients."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from jarvis import __version__
from jarvis.brain.agent import Agent
from jarvis.config import Settings, load_settings
from jarvis.events import EventBus
from jarvis.memory.store import MemoryStore
from jarvis.policy.audit import AuditLog
from jarvis.policy.permissions import PermissionEngine, User, parse_confirmation
from jarvis.tools.basic import TimerService, register_basic_tools
from jarvis.tools.home_assistant import HomeAssistantClient, register_home_assistant_tools
from jarvis.tools.registry import ToolRegistry
from jarvis.voice.stt import make_transcriber
from jarvis.voice.tts import make_synthesizer

STATIC = Path(__file__).parent / "static"


class MessageIn(BaseModel):
    text: str
    user_id: str = "owner"
    room: str = "office"
    force_tier: str | None = None


class ApprovalIn(BaseModel):
    approved: bool
    by: str = "dashboard"


class MemoryIn(BaseModel):
    text: str
    category: str = "general"
    user_id: str = "owner"


class JarvisRuntime:
    """Everything the server needs, wired once at startup."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self.bus = EventBus()
        self.memory = MemoryStore(settings.db_path)
        self.audit = AuditLog(settings.db_path)
        self.permissions = PermissionEngine()
        self.registry = ToolRegistry()
        self.timers = TimerService(self.bus.publish)
        register_basic_tools(self.registry, settings, self.memory, self.timers)
        self.ha: HomeAssistantClient | None = None
        if settings.ha_configured:
            self.ha = HomeAssistantClient(settings.ha_url or "", settings.ha_token or "", settings.exposed_entities)
            register_home_assistant_tools(self.registry, settings, self.ha)
        persona = ""
        persona_path = Path("agent/prompts/persona.md")
        if persona_path.exists():
            persona = "\n" + persona_path.read_text(encoding="utf-8")
        self.agent = Agent(settings, self.registry, self.permissions, self.audit, self.memory, self.bus,
                           client=client, persona_extra=persona)
        self.stt = make_transcriber(settings.stt)
        self.tts = make_synthesizer(settings.tts)
        self.users = {u["id"]: User(id=u["id"], name=u["name"], role=u["role"]) for u in settings.user_list()}
        self.ha_online: bool | None = None
        self._queue: asyncio.Queue[tuple[MessageIn, asyncio.Future]] = asyncio.Queue()
        self._worker: asyncio.Task | None = None

    def resolve_user(self, user_id: str) -> User:
        return self.users.get(user_id.lower(), User(id=user_id.lower(), name=user_id, role="guest"))

    async def start(self) -> None:
        if self.ha:
            self.ha_online = await self.ha.ping()
        self._worker = asyncio.create_task(self._run_queue())

    async def stop(self) -> None:
        if self._worker:
            self._worker.cancel()
        if self.ha:
            await self.ha.aclose()

    async def submit(self, msg: MessageIn) -> str:
        """Queue a user message; turns run one at a time (a household has one conversation).

        A bare yes/no while an approval is pending must not wait behind the turn that is blocked on that
        approval, so it is handled immediately instead of queued."""
        if self.permissions.pending and parse_confirmation(msg.text) is not None:
            await self.agent.handle(msg.text, self.resolve_user(msg.user_id), room=msg.room)
            return "answered"
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        await self._queue.put((msg, fut))
        return "queued"

    async def _run_queue(self) -> None:
        while True:
            msg, fut = await self._queue.get()
            task = asyncio.create_task(
                self.agent.handle(msg.text, self.resolve_user(msg.user_id), room=msg.room, force_tier=msg.force_tier)
            )
            self.agent.current_task = task
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:  # keep the worker alive
                await self.bus.publish("error", text=f"{e.__class__.__name__}: {e}")
            finally:
                self.agent.current_task = None
                if not fut.done():
                    fut.set_result(True)

    def interrupt(self) -> bool:
        t = self.agent.current_task
        if t and not t.done():
            t.cancel()
            return True
        return False

    def state(self) -> dict[str, Any]:
        s = self.settings
        return {
            "version": __version__,
            "assistant_name": s.assistant_name,
            "models": {"default": s.model_default, "fast": s.model_fast, "router_enabled": s.router_enabled,
                       "effort_chat": s.effort_chat, "effort_complex": s.effort_complex, "fallbacks": s.fallbacks,
                       "web_search": s.web_search},
            "credentials": self.agent.client is not None,
            "home_assistant": {"configured": s.ha_configured, "online": self.ha_online},
            "voice": {"stt": self.stt.name, "tts": self.tts.name, "server_tts": self.tts.server_side, "wake_word": s.wake_word},
            "tools": self.registry.names(),
            "users": [{"id": u.id, "name": u.name, "role": u.role} for u in self.users.values()],
            "pending_approvals": [
                {"id": a.id, "tool": a.tool, "input": a.tool_input, "reason": a.reason, "user": a.user.name}
                for a in self.permissions.pending.values()
            ],
            "timers": self.timers.list(),
            "todos": self.memory.list_todos(),
            "metrics": self.agent.metrics[-50:],
        }


def create_app(settings: Settings | None = None, client: Any | None = None) -> FastAPI:
    settings = settings or load_settings()
    rt = JarvisRuntime(settings, client=client)
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await rt.start()
        try:
            yield
        finally:
            await rt.stop()

    app = FastAPI(title="Jarvis", version=__version__, lifespan=lifespan)
    app.state.rt = rt

    def auth(request: Request, token: str | None = Query(default=None)) -> None:
        expected = settings.dashboard_token
        if not expected:
            return
        provided = token or request.headers.get("x-jarvis-token") or request.cookies.get("jarvis_token")
        if provided != expected:
            raise HTTPException(status_code=401, detail="dashboard token required")

    # ---------------------------------------------------------------- pages
    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8"))

    @app.get("/static/{name}")
    async def static(name: str) -> FileResponse:
        path = STATIC / Path(name).name  # single path segment only; the router already rejects '/'
        if not path.is_file():
            raise HTTPException(404)
        return FileResponse(path)

    # ---------------------------------------------------------------- api
    @app.get("/api/state", dependencies=[Depends(auth)])
    async def get_state() -> dict[str, Any]:
        return rt.state()

    @app.post("/api/message", dependencies=[Depends(auth)])
    async def post_message(msg: MessageIn) -> dict[str, str]:
        if not msg.text.strip():
            raise HTTPException(400, "empty message")
        return {"status": await rt.submit(msg)}

    @app.post("/api/interrupt", dependencies=[Depends(auth)])
    async def post_interrupt() -> dict[str, bool]:
        return {"interrupted": rt.interrupt()}

    @app.post("/api/reset", dependencies=[Depends(auth)])
    async def post_reset() -> dict[str, bool]:
        rt.agent.reset()
        await rt.bus.publish("conversation_reset")
        return {"ok": True}

    @app.post("/api/approvals/{approval_id}", dependencies=[Depends(auth)])
    async def post_approval(approval_id: str, body: ApprovalIn) -> dict[str, bool]:
        ok = rt.permissions.resolve(approval_id, body.approved, by=body.by)
        if not ok:
            raise HTTPException(404, "no such pending approval")
        return {"ok": True}

    @app.get("/api/memory", dependencies=[Depends(auth)])
    async def get_memory(q: str = "") -> dict[str, Any]:
        facts = rt.memory.recall(q, limit=50, confirmed_only=False) if q else rt.memory.list_facts(limit=200)
        return {"facts": facts}

    @app.post("/api/memory", dependencies=[Depends(auth)])
    async def post_memory(body: MemoryIn) -> dict[str, int]:
        fid = rt.memory.remember(body.text, user_id=body.user_id, category=body.category)
        await rt.bus.publish("memory_changed", action="remember", id=fid)
        return {"id": fid}

    @app.delete("/api/memory/{fact_id}", dependencies=[Depends(auth)])
    async def delete_memory(fact_id: int) -> dict[str, bool]:
        ok = rt.memory.forget(fact_id)
        await rt.bus.publish("memory_changed", action="forget", id=fact_id)
        return {"ok": ok}

    @app.get("/api/audit", dependencies=[Depends(auth)])
    async def get_audit(limit: int = 50) -> dict[str, Any]:
        return {"entries": rt.audit.recent(limit)}

    @app.get("/api/history", dependencies=[Depends(auth)])
    async def get_history() -> dict[str, Any]:
        return {"episodes": rt.memory.recent_turns(100), "context": rt.agent.export_history()}

    @app.get("/api/events", dependencies=[Depends(auth)])
    async def get_events(limit: int = 100) -> dict[str, Any]:
        return {"events": rt.bus.history[-limit:]}

    @app.post("/api/stt", dependencies=[Depends(auth)])
    async def post_stt(audio: UploadFile = File(...)) -> dict[str, str]:
        try:
            text = await rt.stt.transcribe(await audio.read(), audio.content_type or "audio/webm")
        except RuntimeError as e:
            raise HTTPException(400, str(e))
        return {"text": text}

    @app.get("/api/tts", dependencies=[Depends(auth)])
    async def get_tts(text: str) -> Response:
        if not rt.tts.server_side:
            raise HTTPException(400, "server TTS not configured (JARVIS_TTS=browser)")
        return Response(await rt.tts.synthesize(text), media_type="audio/wav")

    # ---------------------------------------------------------------- websocket
    @app.websocket("/ws")
    async def ws(websocket: WebSocket, token: str | None = None) -> None:
        if settings.dashboard_token and token != settings.dashboard_token:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        send_lock = asyncio.Lock()

        async def forward(event: dict[str, Any]) -> None:
            async with send_lock:
                await websocket.send_text(json.dumps(event, default=str))

        unsubscribe = rt.bus.subscribe(forward)
        try:
            await forward({"type": "hello", "state": rt.state()})
            for ev in rt.bus.history[-40:]:
                if ev["type"] in ("transcript", "tool_call", "tool_result", "approval_requested", "approval_resolved"):
                    await forward(ev)
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                kind = data.get("type")
                if kind == "user_message" and data.get("text", "").strip():
                    await rt.submit(MessageIn(text=data["text"], user_id=data.get("user_id", "owner"),
                                              room=data.get("room", "office"), force_tier=data.get("force_tier")))
                elif kind == "approve":
                    rt.permissions.resolve(data.get("id", ""), bool(data.get("approved")), by=data.get("by", "dashboard"))
                elif kind == "interrupt":
                    rt.interrupt()
                elif kind == "state":
                    await forward({"type": "state", "state": rt.state()})
        except WebSocketDisconnect:
            pass
        finally:
            unsubscribe()

    return app


def run() -> None:
    import uvicorn

    settings = load_settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level="info")
