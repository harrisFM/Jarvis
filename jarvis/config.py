"""Runtime configuration, loaded from environment variables and an optional .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Brain
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    model_default: str = Field(default="claude-opus-5", alias="JARVIS_MODEL_DEFAULT")
    model_fast: str = Field(default="claude-sonnet-5", alias="JARVIS_MODEL_FAST")
    router_enabled: bool = Field(default=False, alias="JARVIS_ROUTER_ENABLED")
    effort_chat: str = Field(default="medium", alias="JARVIS_EFFORT_CHAT")
    effort_complex: str = Field(default="high", alias="JARVIS_EFFORT_COMPLEX")
    fallbacks: bool = Field(default=True, alias="JARVIS_FALLBACKS")
    web_search: bool = Field(default=False, alias="JARVIS_WEB_SEARCH")
    web_search_max_uses: int = Field(default=3, alias="JARVIS_WEB_SEARCH_MAX_USES")
    max_history_turns: int = Field(default=30, alias="JARVIS_MAX_HISTORY_TURNS")
    max_tool_rounds: int = Field(default=8, alias="JARVIS_MAX_TOOL_ROUNDS")

    # Persona
    assistant_name: str = Field(default="Jarvis", alias="JARVIS_ASSISTANT_NAME")
    owner_name: str = Field(default="", alias="JARVIS_OWNER_NAME")
    home_timezone: str = Field(default="UTC", alias="JARVIS_HOME_TIMEZONE")
    language: str = Field(default="en", alias="JARVIS_LANGUAGE")
    # Household members as "Name:role" pairs (roles: owner|adult|child|guest)
    users: str = Field(default="Owner:owner,Guest:guest", alias="JARVIS_USERS")

    # Home Assistant
    ha_url: str | None = Field(default=None, alias="HA_URL")
    ha_token: str | None = Field(default=None, alias="HA_TOKEN")
    ha_exposed_entities: str = Field(default="", alias="HA_EXPOSED_ENTITIES")

    # Messaging
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, alias="TELEGRAM_CHAT_ID")

    # Server
    host: str = Field(default="0.0.0.0", alias="JARVIS_HOST")
    port: int = Field(default=8080, alias="JARVIS_PORT")
    data_dir: Path = Field(default=Path("./data"), alias="JARVIS_DATA_DIR")
    dashboard_token: str = Field(default="", alias="JARVIS_DASHBOARD_TOKEN")
    approval_timeout: float = Field(default=120.0, alias="JARVIS_APPROVAL_TIMEOUT")

    # Voice
    stt: str = Field(default="browser", alias="JARVIS_STT")
    tts: str = Field(default="browser", alias="JARVIS_TTS")
    wake_word: str = Field(default="jarvis", alias="JARVIS_WAKE_WORD")

    def user_list(self) -> list[dict[str, str]]:
        out = []
        for pair in self.users.split(","):
            if ":" in pair:
                name, role = pair.split(":", 1)
                out.append({"id": name.strip().lower(), "name": name.strip(), "role": role.strip().lower()})
        return out or [{"id": "owner", "name": "Owner", "role": "owner"}]

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jarvis.db"

    @property
    def exposed_entities(self) -> set[str]:
        return {e.strip() for e in self.ha_exposed_entities.split(",") if e.strip()}

    @property
    def ha_configured(self) -> bool:
        return bool(self.ha_url and self.ha_token)


def load_settings(**overrides) -> Settings:
    settings = Settings(**overrides)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
