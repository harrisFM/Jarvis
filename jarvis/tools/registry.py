"""Tool registry: each tool has a name, a description, a strict JSON schema, and an async handler.
The registry renders Anthropic tool definitions in a stable order so the prompt prefix stays cacheable."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from jarvis.policy.permissions import User


@dataclass
class ToolContext:
    user: User
    room: str = "unknown"
    session: str = "default"
    emit: Callable[..., Awaitable[Any]] | None = None  # bus.publish

    async def event(self, type_: str, **data: Any) -> None:
        if self.emit is not None:
            await self.emit(type_, **data)


Handler = Callable[[dict[str, Any], ToolContext], Awaitable[str] | str]


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Handler
    strict: bool = True
    tags: list[str] = field(default_factory=list)

    def definition(self) -> dict[str, Any]:
        schema = dict(self.input_schema)
        schema.setdefault("type", "object")
        schema.setdefault("properties", {})
        schema.setdefault("required", [])
        schema.setdefault("additionalProperties", False)
        d: dict[str, Any] = {"name": self.name, "description": self.description, "input_schema": schema}
        if self.strict:
            d["strict"] = True
        return d

    async def run(self, tool_input: dict[str, Any], ctx: ToolContext) -> str:
        result = self.handler(tool_input, ctx)
        if inspect.isawaitable(result):
            result = await result
        return str(result)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        self._tools[tool.name] = tool
        return tool

    def add(self, name: str, description: str, input_schema: dict[str, Any], handler: Handler, **kw: Any) -> Tool:
        return self.register(Tool(name, description, input_schema, handler, **kw))

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def definitions(self) -> list[dict[str, Any]]:
        return [self._tools[n].definition() for n in self.names()]
