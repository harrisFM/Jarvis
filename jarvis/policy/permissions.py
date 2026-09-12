"""Permission engine: decides allow / ask / deny for every tool call *outside* the model.

Rules are evaluated most-specific-first. A rule matches on the tool name, an optional
predicate over the tool input, and the caller's role. The default for unknown tools is
"ask" so a new tool can never act silently."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


ROLE_RANK = {"guest": 0, "child": 1, "adult": 2, "owner": 3}


@dataclass
class User:
    id: str = "owner"
    name: str = "Owner"
    role: str = "owner"  # guest | child | adult | owner

    @property
    def rank(self) -> int:
        return ROLE_RANK.get(self.role, 0)


@dataclass
class Rule:
    tool: str  # exact tool name or prefix ending with '*'
    decision: Decision
    predicate: Callable[[dict[str, Any]], bool] | None = None
    min_role: str = "guest"  # rule applies to callers with at least this role
    max_role: str = "owner"  # ...and at most this role (lets a deny target only guests/children)
    reason: str = ""

    def matches(self, tool: str, tool_input: dict[str, Any], user: User) -> bool:
        if self.tool.endswith("*"):
            if not tool.startswith(self.tool[:-1]):
                return False
        elif tool != self.tool:
            return False
        if user.rank < ROLE_RANK.get(self.min_role, 0) or user.rank > ROLE_RANK.get(self.max_role, 3):
            return False
        if self.predicate is not None:
            try:
                return bool(self.predicate(tool_input))
            except Exception:
                return False
        return True


@dataclass
class Approval:
    id: str
    tool: str
    tool_input: dict[str, Any]
    user: User
    reason: str
    future: asyncio.Future = field(repr=False)


def _ha_domain(inp: dict[str, Any]) -> str:
    entity = str(inp.get("entity_id") or "")
    return str(inp.get("domain") or entity.split(".")[0] or "")


HIGH_RISK_DOMAINS = {"lock", "alarm_control_panel", "cover", "water_heater", "siren"}


def default_rules() -> list[Rule]:
    """The household policy from docs/JARVIS-PLAN.md §6.2, expressed as code."""
    return [
        # Reads are always fine.
        Rule("get_current_time", Decision.ALLOW),
        Rule("recall_memory", Decision.ALLOW),
        Rule("list_timers", Decision.ALLOW),
        Rule("list_todos", Decision.ALLOW),
        Rule("ha_get_states", Decision.ALLOW),
        Rule("ha_list_entities", Decision.ALLOW),
        # Low-risk writes for anyone in the house.
        Rule("set_timer", Decision.ALLOW),
        Rule("cancel_timer", Decision.ALLOW),
        Rule("add_todo", Decision.ALLOW),
        Rule("complete_todo", Decision.ALLOW),
        Rule("remember", Decision.DENY, max_role="guest", reason="Guests cannot write memories"),
        Rule("remember", Decision.ALLOW, min_role="child"),
        Rule("forget_memory", Decision.ASK, reason="Deleting memories needs confirmation"),
        # Home control: high-risk domains and children/guests need confirmation.
        Rule(
            "ha_call_service",
            Decision.DENY,
            predicate=lambda i: _ha_domain(i) in HIGH_RISK_DOMAINS,
            max_role="child",
            reason="Guests and children cannot operate locks, alarms, covers or heaters",
        ),
        Rule(
            "ha_call_service",
            Decision.ASK,
            predicate=lambda i: _ha_domain(i) in HIGH_RISK_DOMAINS,
            min_role="adult",
            reason="Security-relevant device",
        ),
        Rule("ha_call_service", Decision.ASK, max_role="guest", reason="Guests need approval to control devices"),
        Rule("ha_call_service", Decision.ALLOW, min_role="child"),
        # Outward-facing actions always ask.
        Rule("send_message", Decision.DENY, max_role="child", reason="Guests and children cannot send messages"),
        Rule("send_message", Decision.ASK, min_role="adult", reason="Sending a message to someone"),
    ]


class PermissionEngine:
    def __init__(self, rules: list[Rule] | None = None, default: Decision = Decision.ASK) -> None:
        self.rules = rules if rules is not None else default_rules()
        self.default = default
        self.pending: dict[str, Approval] = {}

    def decide(self, tool: str, tool_input: dict[str, Any], user: User) -> tuple[Decision, str]:
        """Return the first matching rule's decision. Order in the rule list is precedence:
        put deny/ask rules with narrow predicates before broad allows."""
        for rule in self.rules:
            if rule.matches(tool, tool_input, user):
                return rule.decision, rule.reason
        return self.default, "No rule matched; asking by default"

    def request_approval(self, tool: str, tool_input: dict[str, Any], user: User, reason: str) -> Approval:
        loop = asyncio.get_event_loop()
        approval = Approval(
            id=uuid.uuid4().hex[:8], tool=tool, tool_input=tool_input, user=user, reason=reason,
            future=loop.create_future(),
        )
        self.pending[approval.id] = approval
        return approval

    def resolve(self, approval_id: str, approved: bool, by: str = "dashboard") -> bool:
        approval = self.pending.pop(approval_id, None)
        if approval is None or approval.future.done():
            return False
        approval.future.set_result((approved, by))
        return True

    def resolve_latest(self, approved: bool, by: str = "voice") -> Approval | None:
        """Used when the user answers "yes"/"no" by voice to the most recent question."""
        if not self.pending:
            return None
        approval_id = next(reversed(self.pending))
        approval = self.pending[approval_id]
        self.resolve(approval_id, approved, by)
        return approval

    async def wait(self, approval: Approval, timeout: float) -> tuple[bool, str]:
        try:
            return await asyncio.wait_for(asyncio.shield(approval.future), timeout=timeout)
        except asyncio.TimeoutError:
            self.pending.pop(approval.id, None)
            return False, "timeout"


YES_WORDS = {"yes", "yeah", "yep", "sure", "do it", "go ahead", "confirm", "approved", "ok", "okay", "please do"}
NO_WORDS = {"no", "nope", "don't", "do not", "cancel", "stop", "never mind", "deny", "negative"}


def parse_confirmation(text: str) -> bool | None:
    """Classify a short utterance as yes / no / neither. Only the first few words matter."""
    t = " ".join("".join(ch if ch.isalnum() or ch in "' " else " " for ch in text.lower()).split())
    if not t:
        return None
    head = " ".join(t.split()[:3])
    for words, value in ((YES_WORDS, True), (NO_WORDS, False)):
        for w in sorted(words, key=len, reverse=True):
            if head == w or head.startswith(w + " "):
                return value
    return None
