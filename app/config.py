"""Zentrale Konfiguration — alle Secrets kommen aus der Umgebung / .env (Zero-Trust)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SOUL_DIR = BASE_DIR / "soul"
WEB_DIR = BASE_DIR / "web"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Claude API
    anthropic_api_key: str | None = None
    model: str = "claude-opus-4-8"
    effort: str = "high"
    max_tokens: int = 64000

    # Server (Zero-Cloud-Default: nur localhost)
    host: str = "127.0.0.1"
    port: int = 8100

    # Zero-Trust
    app_api_key: str | None = None
    allowed_origins: str = ""
    rate_limit_per_minute: int = 30
    max_request_bytes: int = 262_144

    # Gedächtnis / RAG
    db_path: Path = DATA_DIR / "memory.db"
    max_context_chunks: int = 6

    # Eingabe-Limits
    max_message_chars: int = 32_000
    max_history_messages: int = 60

    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
