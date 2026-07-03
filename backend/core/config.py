"""Application settings.

Values can be overridden via environment variables or a `.env` file
(see `.env.example`). Uses pydantic-settings so OpenAI / external keys
can be wired in later without code changes.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "AI Secretary Backend"
    APP_VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # --- Database (local SQLite; no external DB server) ---
    # Relative sqlite path is anchored to the project root in session.py.
    DATABASE_URL: str = "sqlite:///runtime/ai_secretary_local.db"

    # --- CORS ---
    # Comma-separated list, or "*" to allow all origins (dev default).
    CORS_ORIGINS: str = "*"

    # --- LLM (optional; falls back to template when key absent) ---
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.7
    LLM_TIMEOUT_SECONDS: float = 8.0

    # --- Naver local search (optional; endpoint errors clearly when absent) ---
    # Keys live in `.env` (NAVER_CLIENT_ID / NAVER_CLIENT_SECRET). When missing,
    # the server still boots; the place-recommend endpoint returns a clear error
    # instead of crashing at import/startup time.
    NAVER_CLIENT_ID: str | None = None
    NAVER_CLIENT_SECRET: str | None = None
    NAVER_LOCAL_SEARCH_URL: str = "https://openapi.naver.com/v1/search/local.json"
    NAVER_TIMEOUT_SECONDS: float = 5.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def naver_configured(self) -> bool:
        """True only when both Naver credentials are present and non-empty."""
        return bool((self.NAVER_CLIENT_ID or "").strip()) and bool(
            (self.NAVER_CLIENT_SECRET or "").strip()
        )


settings = Settings()
