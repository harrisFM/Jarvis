
import time

from fakes import FakeClient, text_block, tool_use_block
from fastapi.testclient import TestClient

from jarvis.server.app import create_app


def test_state_message_and_memory_endpoints(settings):
    app = create_app(settings, client=FakeClient([([text_block("Hello.")], "end_turn")]))
    with TestClient(app) as c:
        s = c.get("/api/state").json()
        assert s["assistant_name"] == "Jarvis" and s["credentials"] is True and "set_timer" in s["tools"]
        assert c.post("/api/message", json={"text": "hi", "user_id": "owner", "room": "office"}).json() == {"status": "queued"}
        fid = c.post("/api/memory", json={"text": "Alex likes oat milk", "category": "preference"}).json()["id"]
        assert any(f["id"] == fid for f in c.get("/api/memory?q=oat").json()["facts"])
        assert c.delete(f"/api/memory/{fid}").json()["ok"]
        assert c.get("/").status_code == 200 and 'id="transcript"' in c.get("/").text
        assert c.get("/static/app.js").status_code == 200
        assert c.get("/static/nope.js").status_code == 404
        assert c.post("/api/approvals/nope", json={"approved": True}).status_code == 404


def test_dashboard_token_enforced(settings):
    settings.dashboard_token = "secret"
    app = create_app(settings, client=FakeClient([]))
    with TestClient(app) as c:
        assert c.get("/api/state").status_code == 401
        assert c.get("/api/state", headers={"X-Jarvis-Token": "secret"}).status_code == 200
        assert c.get("/api/state?token=secret").status_code == 200


def test_websocket_roundtrip(settings):
    app = create_app(settings, client=FakeClient([([text_block("Hi there.")], "end_turn")]))
    with TestClient(app) as c, c.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["state"]["assistant_name"] == "Jarvis"
        ws.send_json({"type": "user_message", "text": "hello", "user_id": "owner", "room": "kitchen"})
        seen = set()
        deadline = time.time() + 5
        while "turn_finished" not in seen and time.time() < deadline:
            # poll the REST event log instead of blocking forever on the socket
            seen |= {e["type"] for e in c.get("/api/events?limit=50").json()["events"]}
            time.sleep(0.05)
        assert {"transcript", "turn_started", "speak", "turn_finished"} <= seen


def test_voice_answer_bypasses_the_turn_queue(settings):
    settings.approval_timeout = 5
    script = [
        ([tool_use_block("send_message", {"recipient": "Alex", "text": "hi"})], "tool_use"),
        ([text_block("Not sent.")], "end_turn"),
    ]
    app = create_app(settings, client=FakeClient(script))
    with TestClient(app) as c:
        c.post("/api/message", json={"text": "message Alex hi", "user_id": "owner", "room": "office"})
        deadline = time.time() + 3
        while not c.get("/api/state").json()["pending_approvals"] and time.time() < deadline:
            time.sleep(0.05)
        assert c.get("/api/state").json()["pending_approvals"], "approval should be pending"
        assert c.post("/api/message", json={"text": "no", "user_id": "owner", "room": "office"}).json() == {"status": "answered"}
        deadline = time.time() + 3
        while c.get("/api/state").json()["pending_approvals"] and time.time() < deadline:
            time.sleep(0.05)
        events = c.get("/api/events?limit=100").json()["events"]
        resolved = [e for e in events if e["type"] == "approval_resolved"]
        assert resolved and resolved[-1]["approved"] is False and resolved[-1]["by"] == "voice:owner"
