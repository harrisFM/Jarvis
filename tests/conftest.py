from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from jarvis.config import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(ANTHROPIC_API_KEY="test-key", JARVIS_DATA_DIR=str(tmp_path), JARVIS_FALLBACKS=False,
                    JARVIS_APPROVAL_TIMEOUT=2, _env_file=None)


# ---------------------------------------------------------------- fake Anthropic client
class _Block(SimpleNamespace):
    def model_dump(self, exclude_none=True):
        return {k: v for k, v in vars(self).items() if v is not None}


def text_block(text: str) -> _Block:
    return _Block(type="text", text=text)


def tool_use_block(name: str, inp: dict[str, Any], id_: str = "toolu_1") -> _Block:
    return _Block(type="tool_use", name=name, input=inp, id=id_)


class FakeMessage(SimpleNamespace):
    pass


class FakeStream:
    """Mimics `client.beta.messages.stream(...)`: yields events then returns a final message."""

    def __init__(self, content: list[_Block], stop_reason: str, recorder: list[dict[str, Any]], kwargs: dict[str, Any]):
        self.content, self.stop_reason = content, stop_reason
        recorder.append({**kwargs, "messages": list(kwargs.get("messages", []))})  # snapshot at call time

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        async def gen():
            for b in self.content:
                if b.type == "text":
                    yield SimpleNamespace(type="content_block_start", content_block=b)
                    for piece in _split(b.text):
                        yield SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type="text_delta", text=piece))
                        await asyncio.sleep(0)
                elif b.type == "tool_use":
                    yield SimpleNamespace(type="content_block_start", content_block=b)
            yield SimpleNamespace(type="message_stop")
        return gen()

    async def get_final_message(self):
        return FakeMessage(content=self.content, stop_reason=self.stop_reason,
                           usage=SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=50,
                                                 cache_creation_input_tokens=0))


def _split(text: str) -> list[str]:
    words = text.split(" ")
    return [w + (" " if i < len(words) - 1 else "") for i, w in enumerate(words)]


class FakeClient:
    """Scripted responses: each call to stream() pops the next (content, stop_reason)."""

    def __init__(self, script: list[tuple[list[_Block], str]]):
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        if not self.script:
            raise AssertionError("FakeClient script exhausted")
        content, stop = self.script.pop(0)
        return FakeStream(content, stop, self.calls, kwargs)
