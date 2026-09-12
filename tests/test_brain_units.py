from jarvis.brain.chunker import SentenceChunker, strip_for_speech
from jarvis.brain.router import route
from jarvis.config import Settings


def test_chunker_emits_sentences_incrementally():
    c = SentenceChunker()
    out = []
    for piece in ["The kitchen light is on. ", "It is 21 degrees", " in here. Anything", " else?"]:
        out += c.feed(piece)
    out += c.flush()
    assert out == ["The kitchen light is on.", "It is 21 degrees in here.", "Anything else?"]


def test_chunker_handles_abbreviations_and_flush():
    c = SentenceChunker()
    out = c.feed("Ask Dr. Who about it. Fine.") + c.flush()
    assert out == ["Ask Dr. Who about it.", "Fine."]


def test_strip_for_speech():
    assert strip_for_speech("**Bold** and [link](http://x) `code`") == "Bold and link code"


def test_router_defaults_to_default_model_when_router_off():
    s = Settings(_env_file=None)
    assert route("turn on the lights", s).model == s.model_default
    r = route("please research and compare three heat pumps for me", s)
    assert r.tier == "complex" and r.effort == s.effort_complex


def test_router_fast_tier_when_enabled():
    s = Settings(JARVIS_ROUTER_ENABLED=True, _env_file=None)
    r = route("turn on the kitchen lights", s)
    assert r.model == s.model_fast and r.tier == "fast"
    long_cmd = "turn on the kitchen lights and the hallway lamp and the porch light please thanks"
    assert route(long_cmd, s).tier == "fast"  # >8 words: only the device-control regex can pick the fast tier
    assert route("something quite long that is not a command at all and rambles on for a while", s).tier == "default"
    assert route("turn on the kitchen lights", s, force="default").tier == "default"
