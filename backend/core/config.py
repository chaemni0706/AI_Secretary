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
    OPENAI_VISION_MODEL: str = "gpt-4.1-mini-2025-04-14"
    LLM_TEMPERATURE: float = 0.7
    LLM_TIMEOUT_SECONDS: float = 8.0

    # --- Image verification VLM provider (on-device local models) ---
    # 기본은 OpenAI 없이 로컬 VLM 어댑터로 동작한다. water/exercise/study 는 로컬 모델이
    # 시각 evidence 만 추출하고, 최종 판정은 항상 Rule Engine 이 수행한다.
    #   IMAGE_VERIFICATION_VLM_PROVIDER: 1차 provider (smolvlm | qwen_awq | openai | mock 등 adapter key)
    #   IMAGE_VERIFICATION_STUDY_FALLBACK: study 재판정 fallback provider (없으면 빈 값/None)
    #   IMAGE_VERIFICATION_USE_OPENAI: true 면 OpenAI vision analyzer 사용(키 필요)
    IMAGE_VERIFICATION_VLM_PROVIDER: str = "smolvlm"
    IMAGE_VERIFICATION_STUDY_FALLBACK: str | None = "qwen_awq"
    IMAGE_VERIFICATION_USE_OPENAI: bool = False

    # --- Schedule parsing ---
    # Master switch for the rule-based schedule parser's optional LLM fallback
    # (backend.services.schedule_parser.parse_schedule_with_llm_fallback).
    # Default OFF so the parser works fully offline with rule-based extraction.
    ENABLE_LLM_SCHEDULE_PARSE: bool = False

    # --- Naver local search (지역 검색용; endpoint errors clearly when absent) ---
    # Keys live in `.env` (NAVER_CLIENT_ID / NAVER_CLIENT_SECRET). When missing,
    # the server still boots; the place-recommend endpoint returns a clear error
    # instead of crashing at import/startup time.
    NAVER_CLIENT_ID: str | None = None
    NAVER_CLIENT_SECRET: str | None = None
    NAVER_LOCAL_SEARCH_URL: str = "https://openapi.naver.com/v1/search/local.json"
    NAVER_TIMEOUT_SECONDS: float = 5.0

    # --- Naver Cloud Maps (지도/거리/경로 계산용; 인증 정보 분리) ---
    # Separate credentials from the local-search API. Missing keys never block
    # startup; the Maps-backed endpoints return a clear config error instead.
    NAVER_MAPS_CLIENT_ID: str | None = None
    NAVER_MAPS_CLIENT_SECRET: str | None = None
    NAVER_MAPS_GEOCODE_URL: str = (
        "https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode"
    )
    NAVER_MAPS_REVERSE_GEOCODE_URL: str = (
        "https://naveropenapi.apigw.ntruss.com/map-reversegeocode/v2/gc"
    )
    NAVER_MAPS_DIRECTIONS_URL: str = (
        "https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving"
    )
    NAVER_MAPS_TIMEOUT_SECONDS: float = 5.0

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
        """True only when both local-search credentials are present."""
        return bool((self.NAVER_CLIENT_ID or "").strip()) and bool(
            (self.NAVER_CLIENT_SECRET or "").strip()
        )

    @property
    def naver_maps_configured(self) -> bool:
        """True only when both Naver Cloud Maps credentials are present."""
        return bool((self.NAVER_MAPS_CLIENT_ID or "").strip()) and bool(
            (self.NAVER_MAPS_CLIENT_SECRET or "").strip()
        )


settings = Settings()
