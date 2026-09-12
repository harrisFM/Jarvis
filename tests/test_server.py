
from conftest import FakeClient, text_block
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
        assert c.get("/").status_code == 200 and "Jarvis" in c.get("/").text
        assert c.get("/static/app.js").status_code == 200
        assert c.get("/static/../app.py").status_code in (404, 400)
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
        for _ in range(40):
            ev = ws.receive_json()
            seen.add(ev["type"])
            if ev["type"] == "turn_finished":
                break
        assert {"transcript", "turn_started", "speak", "turn_finished"} <= seen
