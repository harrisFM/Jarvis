"""Speech-to-text adapters. The default 'browser' adapter means the dashboard does recognition with the
Web Speech API and sends text; 'faster_whisper' runs locally when the optional dependency is installed.
The plan's production choice (NVIDIA Nemotron/Parakeet streaming) plugs in behind the same interface."""

from __future__ import annotations

import asyncio
import io
from typing import Protocol


class Transcriber(Protocol):
    name: str

    async def transcribe(self, audio_bytes: bytes, mime: str = "audio/webm") -> str: ...


class BrowserTranscriber:
    name = "browser"

    async def transcribe(self, audio_bytes: bytes, mime: str = "audio/webm") -> str:
        raise RuntimeError("Browser STT mode: the client sends text, not audio. Set JARVIS_STT=faster_whisper for server STT.")


class FasterWhisperTranscriber:
    name = "faster_whisper"

    def __init__(self, model_size: str = "large-v3-turbo", device: str = "auto") -> None:
        from faster_whisper import WhisperModel  # type: ignore

        self.model = WhisperModel(model_size, device=device, compute_type="int8" if device == "cpu" else "float16")

    async def transcribe(self, audio_bytes: bytes, mime: str = "audio/webm") -> str:
        def _run() -> str:
            segments, _ = self.model.transcribe(io.BytesIO(audio_bytes), vad_filter=True, beam_size=1)
            return " ".join(s.text.strip() for s in segments).strip()

        return await asyncio.to_thread(_run)


def make_transcriber(kind: str) -> Transcriber:
    if kind == "faster_whisper":
        return FasterWhisperTranscriber()
    return BrowserTranscriber()
