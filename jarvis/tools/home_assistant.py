"""Home Assistant REST tools (read states, call services). Writes go through the permission engine.

The plan (docs/JARVIS-PLAN.md §4.7) prefers the HA MCP server for the long run; this REST client is the
zero-dependency path that works against any HA instance with a long-lived access token."""

from __future__ import annotations

from typing import Any

import httpx

from jarvis.config import Settings
from jarvis.tools.registry import ToolContext, ToolRegistry

READ_ATTRS = ("friendly_name", "unit_of_measurement", "device_class", "brightness", "temperature",
              "current_temperature", "hvac_mode", "media_title", "volume_level", "area")


class HomeAssistantClient:
    def __init__(self, url: str, token: str, exposed: set[str] | None = None, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.url = url.rstrip("/")
        self.exposed = exposed or set()
        self._client = httpx.AsyncClient(
            base_url=self.url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=10, transport=transport,
        )

    def _visible(self, entity_id: str) -> bool:
        return not self.exposed or entity_id in self.exposed

    async def ping(self) -> bool:
        try:
            r = await self._client.get("/api/")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def states(self, domain: str | None = None, search: str | None = None) -> list[dict[str, Any]]:
        r = await self._client.get("/api/states")
        r.raise_for_status()
        out = []
        for s in r.json():
            eid = s["entity_id"]
            if not self._visible(eid):
                continue
            if domain and not eid.startswith(domain + "."):
                continue
            name = s.get("attributes", {}).get("friendly_name", "")
            if search and search.lower() not in (eid + " " + name).lower():
                continue
            attrs = {k: v for k, v in s.get("attributes", {}).items() if k in READ_ATTRS}
            out.append({"entity_id": eid, "state": s.get("state"), "name": name, "attributes": attrs})
        return out

    async def call_service(self, domain: str, service: str, entity_id: str | None, data: dict[str, Any] | None) -> Any:
        if entity_id and not self._visible(entity_id):
            raise PermissionError(f"{entity_id} is not exposed to the assistant")
        payload: dict[str, Any] = dict(data or {})
        if entity_id:
            payload["entity_id"] = entity_id
        r = await self._client.post(f"/api/services/{domain}/{service}", json=payload)
        r.raise_for_status()
        return r.json()

    async def aclose(self) -> None:
        await self._client.aclose()


def register_home_assistant_tools(reg: ToolRegistry, settings: Settings, client: HomeAssistantClient) -> None:
    async def list_entities(inp: dict[str, Any], _: ToolContext) -> str:
        rows = await client.states(domain=inp.get("domain") or None, search=inp.get("search") or None)
        if not rows:
            return "No matching entities."
        return "\n".join(f"{r['entity_id']} ({r['name']}): {r['state']}" for r in rows[:60])

    reg.add(
        "ha_list_entities",
        "List smart-home entities (lights, switches, sensors, media players, climate, locks, covers) with their current "
        "state. Filter by domain (e.g. 'light') and/or a name search. Use this to find the right entity_id before acting.",
        {"properties": {"domain": {"type": "string"}, "search": {"type": "string"}}, "required": ["domain", "search"]},
        list_entities,
    )

    async def get_states(inp: dict[str, Any], _: ToolContext) -> str:
        rows = await client.states()
        wanted = set(inp["entity_ids"])
        rows = [r for r in rows if r["entity_id"] in wanted]
        if not rows:
            return "No such entities (check ha_list_entities)."
        return "\n".join(f"{r['entity_id']}: {r['state']} {r['attributes']}" for r in rows)

    reg.add("ha_get_states", "Get the current state and key attributes of specific entities.",
            {"properties": {"entity_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["entity_ids"]},
            get_states)

    async def call_service(inp: dict[str, Any], ctx: ToolContext) -> str:
        domain, service = inp["domain"], inp["service"]
        entity_id = inp.get("entity_id") or None
        data = inp.get("data") or {}
        try:
            await client.call_service(domain, service, entity_id, data)
        except PermissionError as e:
            return f"Error: {e}"
        except httpx.HTTPStatusError as e:
            return f"Error: Home Assistant returned {e.response.status_code}: {e.response.text[:200]}"
        except httpx.HTTPError as e:
            return f"Error: could not reach Home Assistant ({e.__class__.__name__})"
        # Verify, never assume success (HA issue #177156: agents fabricating success).
        if entity_id:
            after = [r for r in await client.states() if r["entity_id"] == entity_id]
            if after:
                await ctx.event("ha_state", entity_id=entity_id, state=after[0]["state"])
                return f"Called {domain}.{service} on {entity_id}. New state: {after[0]['state']}."
        return f"Called {domain}.{service}."

    reg.add(
        "ha_call_service",
        "Control a smart-home device by calling a Home Assistant service, e.g. domain 'light', service 'turn_on', "
        "entity_id 'light.kitchen', data {'brightness_pct': 50}. Only report success after the tool result confirms it.",
        {"properties": {"domain": {"type": "string"}, "service": {"type": "string"}, "entity_id": {"type": "string"},
                        "data": {"type": "object", "additionalProperties": True}},
         "required": ["domain", "service", "entity_id", "data"]},
        call_service,
        strict=False,
    )
