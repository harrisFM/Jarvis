"""Text-to-speech adapters. 'browser' sends sentences to the dashboard, which speaks them with
speechSynthesis; 'kokoro' synthesises WAV on the server when the optional dependency is installed.
Qwen3-TTS / Cartesia adapters from the plan fit the same two-method interface."""

from __future__ import annotations

import asyncio
import io
from typing import Protocol


class Synthesizer(Protocol):
    name: str
    server_side: bool

    async def synthesize(self, text: str) -> bytes: ...


class BrowserSynthesizer:
    name = "browser"
    server_side = False

    async def synthesize(self, text: str) -> bytes:
        return b""


class KokoroSynthesizer:
    name = "kokoro"
    server_side = True

    def __init__(self, voice: str = "bm_george", lang: str = "b") -> None:
        from kokoro import KPipeline  # type: ignore

        self.pipeline = KPipeline(lang_code=lang)
        self.voice = voice

    async def synthesize(self, text: str) -> bytes:
        def _run() -> bytes:
            import numpy as np  # type: ignore
            import soundfile as sf  # type: ignore

            chunks = [audio for _, _, audio in self.pipeline(text, voice=self.voice)]
            audio = np.concatenate(chunks) if chunks else np.zeros(1, dtype="float32")
            buf = io.BytesIO()
            sf.write(buf, audio, 24000, format="WAV")
            return buf.getvalue()

        return await asyncio.to_thread(_run)


def make_synthesizer(kind: str) -> Synthesizer:
    if kind == "kokoro":
        return KokoroSynthesizer()
    return BrowserSynthesizer()
