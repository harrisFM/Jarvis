import httpx

from jarvis.tools.home_assistant import HomeAssistantClient, register_home_assistant_tools
from jarvis.tools.registry import ToolContext, ToolRegistry
from jarvis.policy.permissions import User

STATES = [
    {"entity_id": "light.kitchen", "state": "off", "attributes": {"friendly_name": "Kitchen light", "brightness": 0}},
    {"entity_id": "lock.front", "state": "locked", "attributes": {"friendly_name": "Front door"}},
    {"entity_id": "sensor.secret", "state": "42", "attributes": {"friendly_name": "Secret"}},
]


def make_client(exposed=None):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/api/":
            return httpx.Response(200, json={"message": "API running."})
        if request.url.path == "/api/states":
            states = [dict(s) for s in STATES]
            if any(c.url.path.endswith("/turn_on") for c in calls):
                states[0]["state"] = "on"
            return httpx.Response(200, json=states)
        if request.url.path.startswith("/api/services/"):
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    client = HomeAssistantClient("http://ha.local:8123", "tok", exposed, transport=httpx.MockTransport(handler))
    return client, calls


async def test_states_filtering_and_exposure():
    client, _ = make_client(exposed={"light.kitchen", "lock.front"})
    assert await client.ping()
    rows = await client.states()
    assert {r["entity_id"] for r in rows} == {"light.kitchen", "lock.front"}
    assert (await client.states(domain="light"))[0]["attributes"]["brightness"] == 0
    assert await client.states(search="front") and (await client.states(search="front"))[0]["entity_id"] == "lock.front"


async def test_call_service_verifies_state_and_respects_exposure(settings):
    client, calls = make_client(exposed={"light.kitchen"})
    reg = ToolRegistry()
    register_home_assistant_tools(reg, settings, client)
    ctx = ToolContext(user=User())
    out = await reg.get("ha_call_service").run({"domain": "light", "service": "turn_on", "entity_id": "light.kitchen", "data": {}}, ctx)
    assert "New state: on" in out
    assert calls[0].url.path == "/api/services/light/turn_on" and calls[0].headers["authorization"] == "Bearer tok"
    denied = await reg.get("ha_call_service").run({"domain": "lock", "service": "unlock", "entity_id": "lock.front", "data": {}}, ctx)
    assert denied.startswith("Error") and "not exposed" in denied
