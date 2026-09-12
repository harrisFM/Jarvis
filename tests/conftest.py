from __future__ import annotations

import pytest

from jarvis.config import Settings

ENV_PREFIXES = ("JARVIS_", "HA_", "TELEGRAM_", "ANTHROPIC_")


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    """Tests must not depend on whatever JARVIS_*/HA_* variables the developer's shell exports."""
    import os

    for key in list(os.environ):
        if key.startswith(ENV_PREFIXES):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(ANTHROPIC_API_KEY="test-key", JARVIS_DATA_DIR=str(tmp_path), JARVIS_FALLBACKS=False,
                    JARVIS_APPROVAL_TIMEOUT=2, _env_file=None)
