"""Tier router: decides which model and effort a turn gets (docs/JARVIS-PLAN.md §4.6).

Kept deliberately simple and deterministic so it costs nothing and is easy to reason about."""

from __future__ import annotations

import re
from dataclasses import dataclass

from jarvis.config import Settings

COMPLEX_HINTS = re.compile(
    r"\b(plan|research|compare|analy[sz]e|summari[sz]e|explain in detail|write|draft|debug|code|schedule .* and|"
    r"why|think hard|step by step|pros and cons|investigate)\b",
    re.I,
)
SIMPLE_HINTS = re.compile(
    r"^(turn|switch|set|dim|lock|unlock|open|close|start|stop|pause|play|what time|what's the time|timer|remind|add|"
    r"hi|hello|hey|thanks|thank you|good (morning|night))\b",
    re.I,
)


@dataclass
class Route:
    model: str
    effort: str
    tier: str  # "fast" | "default" | "complex"
    reason: str


def route(text: str, settings: Settings, *, force: str | None = None) -> Route:
    t = text.strip()
    if force == "complex" or COMPLEX_HINTS.search(t) or len(t.split()) > 60:
        return Route(settings.model_default, settings.effort_complex, "complex", "complex request")
    if settings.router_enabled and force != "default" and (SIMPLE_HINTS.match(t) or len(t.split()) <= 8):
        return Route(settings.model_fast, "low", "fast", "short or device-control request")
    return Route(settings.model_default, settings.effort_chat, "default", "conversational request")
