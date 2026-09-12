import asyncio

from jarvis.policy.permissions import Decision, PermissionEngine, User, parse_confirmation


def u(role):
    return User(id=role, name=role, role=role)


def test_reads_allowed_for_everyone():
    e = PermissionEngine()
    for role in ("guest", "child", "adult", "owner"):
        assert e.decide("get_current_time", {}, u(role))[0] == Decision.ALLOW


def test_lock_requires_confirmation_for_adults_and_is_denied_for_children():
    e = PermissionEngine()
    inp = {"domain": "lock", "service": "unlock", "entity_id": "lock.front"}
    assert e.decide("ha_call_service", inp, u("owner"))[0] == Decision.ASK
    assert e.decide("ha_call_service", inp, u("adult"))[0] == Decision.ASK
    assert e.decide("ha_call_service", inp, u("child"))[0] == Decision.DENY
    assert e.decide("ha_call_service", inp, u("guest"))[0] == Decision.DENY


def test_lights_allowed_for_child_ask_for_guest():
    e = PermissionEngine()
    inp = {"domain": "light", "service": "turn_on", "entity_id": "light.kitchen"}
    assert e.decide("ha_call_service", inp, u("child"))[0] == Decision.ALLOW
    assert e.decide("ha_call_service", inp, u("guest"))[0] == Decision.ASK


def test_unknown_tool_defaults_to_ask():
    e = PermissionEngine()
    assert e.decide("launch_rockets", {}, u("owner"))[0] == Decision.ASK


def test_send_message_policy():
    e = PermissionEngine()
    assert e.decide("send_message", {"recipient": "x", "text": "y"}, u("owner"))[0] == Decision.ASK
    assert e.decide("send_message", {"recipient": "x", "text": "y"}, u("child"))[0] == Decision.DENY


async def test_approval_flow_resolve_and_timeout():
    e = PermissionEngine()
    a = e.request_approval("send_message", {}, u("owner"), "test")
    assert a.id in e.pending
    asyncio.get_event_loop().call_later(0.05, e.resolve, a.id, True, "dashboard")
    assert await e.wait(a, timeout=1) == (True, "dashboard")
    assert a.id not in e.pending
    b = e.request_approval("send_message", {}, u("owner"), "test")
    assert await e.wait(b, timeout=0.05) == (False, "timeout")


async def test_resolve_latest_and_confirmation_parsing():
    e = PermissionEngine()
    a = e.request_approval("send_message", {}, u("owner"), "t")
    assert parse_confirmation("Yes, go ahead") is True
    assert parse_confirmation("no thanks") is False
    assert parse_confirmation("what time is it") is None
    got = e.resolve_latest(False, by="voice")
    assert got is a and a.future.result() == (False, "voice")
