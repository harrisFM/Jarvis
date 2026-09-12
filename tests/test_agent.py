import asyncio

from conftest import FakeClient, text_block, tool_use_block

from jarvis.brain.agent import Agent
from jarvis.events import EventBus
from jarvis.memory.store import MemoryStore
from jarvis.policy.audit import AuditLog
from jarvis.policy.permissions import PermissionEngine, User
from jarvis.tools.basic import TimerService, register_basic_tools
from jarvis.tools.registry import ToolRegistry


def make_agent(settings, script):
    bus = EventBus()
    memory = MemoryStore(settings.db_path)
    audit = AuditLog(settings.db_path)
    reg = ToolRegistry()
    register_basic_tools(reg, settings, memory, TimerService(bus.publish))

    async def fake_send_message(inp, ctx):
        return "Message sent (fake)."

    reg.get("send_message").handler = fake_send_message
    agent = Agent(settings, reg, PermissionEngine(), audit, memory, bus, client=FakeClient(script))
    events = []
    bus.subscribe(lambda e: _collect(events, e))
    return agent, events, audit


async def _collect(events, e):
    events.append(e)


async def test_plain_reply_streams_sentences_and_records_metrics(settings):
    agent, events, _ = make_agent(settings, [([text_block("Hello there. The time is noon.")], "end_turn")])
    turn = await agent.handle("hi", User(), room="kitchen")
    assert turn.reply == "Hello there. The time is noon."
    spoken = [e["text"] for e in events if e["type"] == "speak"]
    assert spoken == ["Hello there.", "The time is noon."]
    assert turn.ttft_ms is not None and turn.input_tokens == 100 and turn.cache_read_tokens == 50
    call = agent.client.calls[0]
    assert call["model"] == settings.model_default and call["output_config"] == {"effort": settings.effort_chat}
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "fallbacks" not in call  # disabled in test settings
    assert "[context]" in agent.history[0]["content"] and "room: kitchen" in agent.history[0]["content"]


async def test_tool_call_allowed_then_final_answer(settings):
    script = [
        ([text_block("Checking."), tool_use_block("set_timer", {"seconds": 60, "label": "tea"})], "tool_use"),
        ([text_block("Tea timer set for one minute.")], "end_turn"),
    ]
    agent, events, audit = make_agent(settings, script)
    turn = await agent.handle("set a tea timer for a minute", User())
    assert turn.rounds == 2 and turn.tool_calls[0]["decision"] == "allow"
    assert "Timer" in turn.tool_calls[0]["result"]
    # tool results are sent back as a single user message with a tool_result block
    second_call_messages = agent.client.calls[1]["messages"]
    assert second_call_messages[-1]["role"] == "user"
    assert second_call_messages[-1]["content"][0]["type"] == "tool_result"
    assert audit.recent()[0]["tool"] == "set_timer" and audit.recent()[0]["decision"] == "allow"
    assert turn.reply.startswith("Checking.") and turn.reply.endswith("one minute.")


async def test_ask_tier_tool_waits_for_approval_and_runs(settings):
    script = [
        ([tool_use_block("send_message", {"recipient": "Alex", "text": "Dinner at 7"})], "tool_use"),
        ([text_block("Sent.")], "end_turn"),
    ]
    agent, events, audit = make_agent(settings, script)
    task = asyncio.create_task(agent.handle("tell Alex dinner is at 7", User()))
    for _ in range(50):
        await asyncio.sleep(0.01)
        if agent.permissions.pending:
            break
    assert agent.permissions.pending, "an approval should be pending"
    req = [e for e in events if e["type"] == "approval_requested"][0]
    assert "Confirmation needed" in req["question"]
    agent.permissions.resolve(req["id"], True, by="dashboard")
    turn = await task
    assert turn.tool_calls[0]["result"] == "Message sent (fake)."
    assert audit.recent()[0]["approved_by"] == "dashboard"


async def test_ask_tier_tool_denied_by_voice(settings):
    script = [
        ([tool_use_block("send_message", {"recipient": "Alex", "text": "hi"})], "tool_use"),
        ([text_block("Understood, not sending.")], "end_turn"),
    ]
    agent, events, _ = make_agent(settings, script)
    task = asyncio.create_task(agent.handle("message Alex hi", User()))
    while not agent.permissions.pending:
        await asyncio.sleep(0.01)
    answer = await agent.handle("no", User())  # voice answer resolves the pending approval, no LLM call
    assert answer.tier == "confirmation" and answer.reply == "Cancelled."
    turn = await task
    assert turn.tool_calls[0]["is_error"] and "declined" in turn.tool_calls[0]["result"]


async def test_policy_denied_tool_never_runs(settings):
    script = [
        ([tool_use_block("send_message", {"recipient": "x", "text": "y"})], "tool_use"),
        ([text_block("I can't do that for a guest.")], "end_turn"),
    ]
    agent, _, audit = make_agent(settings, script)
    turn = await agent.handle("send x y", User(id="g", name="Guest", role="guest"))
    assert turn.tool_calls[0]["decision"] == "deny" and turn.tool_calls[0]["is_error"]
    assert audit.recent()[0]["decision"] == "deny"


async def test_refusal_is_spoken_briefly(settings):
    agent, events, _ = make_agent(settings, [([], "refusal")])
    turn = await agent.handle("do something bad", User())
    assert turn.reply == "I can't help with that one." and turn.stop_reason == "refusal"


async def test_history_trimming_keeps_whole_turns(settings):
    settings.max_history_turns = 2
    script = [([text_block(f"r{i}.")], "end_turn") for i in range(4)]
    agent, _, _ = make_agent(settings, script)
    for i in range(4):
        await agent.handle(f"q{i}", User())
    assert len(agent._turn_starts) == 2 and agent.history[0]["role"] == "user" and "q2" in agent.history[0]["content"]


async def test_no_credentials_returns_error(settings):
    settings.anthropic_api_key = None
    agent, events, _ = make_agent(settings, [])
    agent.client = None
    turn = await agent.handle("hi", User())
    assert turn.error and any(e["type"] == "error" for e in events)
