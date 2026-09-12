"""Sentence chunker: turns a token stream into speakable sentences as early as possible."""

from __future__ import annotations

import re

_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])|(?<=[.!?])$|\n+")
_ABBREV = re.compile(r"\b(e\.g|i\.e|Mr|Mrs|Dr|St|vs|No)\.$")


class SentenceChunker:
    def __init__(self, min_chars: int = 12) -> None:
        self.buf = ""
        self.min_chars = min_chars

    def feed(self, text: str) -> list[str]:
        self.buf += text
        out: list[str] = []
        while True:
            m = _BOUNDARY.search(self.buf)
            if not m:
                break
            sentence = self.buf[: m.start()].strip()
            rest = self.buf[m.end():]
            if _ABBREV.search(sentence) or len(sentence) < self.min_chars and rest.strip():
                # too short or an abbreviation: keep accumulating unless it's the end
                if not rest.strip():
                    break
                self.buf = sentence + " " + rest
                # avoid infinite loop when boundary is at same spot
                m2 = _BOUNDARY.search(self.buf, len(sentence) + 1)
                if not m2:
                    break
                sentence2 = self.buf[: m2.start()].strip()
                self.buf = self.buf[m2.end():]
                if sentence2:
                    out.append(sentence2)
                continue
            self.buf = rest
            if sentence:
                out.append(sentence)
        return out

    def flush(self) -> list[str]:
        s = self.buf.strip()
        self.buf = ""
        return [s] if s else []


def strip_for_speech(text: str) -> str:
    """Remove markdown artefacts that would be read aloud."""
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return re.sub(r"\s{2,}", " ", text).strip()
