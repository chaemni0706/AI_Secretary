"""Application settings.

Values can be overridden via environment variables or a `.env` file
(see `.env.example`). Uses pydantic-settings so OpenAI / external keys
can be wired in later without code changes.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env 로딩을 실행 위치(CWD)와 무관하게 만든다.
# 이 파일은 backend/core/config.py 이므로 parents[1] = backend/ 다.
# 실제 파일은 backend/.env 이지만, 루트/백엔드 어디서 uvicorn 을 실행해도
# 로드되도록 두 위치를 모두 시도한다(뒤 항목 우선 → backend/.env 값이 최종 적용).
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ROOT_DIR = _BACKEND_DIR.parent
_ENV_FILES = (_ROOT_DIR / ".env", _BACKEND_DIR / ".env")


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

    # --- Schedule parsing ---
    # Master switch for the rule-based schedule parser's optional LLM fallback
    # (backend.services.schedule_parser.parse_schedule_with_llm_fallback).
    # Default OFF so the parser works fully offline with rule-based extraction.
    ENABLE_LLM_SCHEDULE_PARSE: bool = False

    # --- Intent classification (voice router) ---
    # 규칙 분류가 fallback_chat(=명확한 매칭 없음)으로 떨어질 때만 LLM 보조 분류를
    # 시도한다. Default OFF → 켜기 전까지 기존 규칙 동작과 100% 동일.
    ENABLE_LLM_INTENT: bool = False

    # --- Clarification (부족 정보 되묻기 문장) ---
    # 부족 정보 질문을 LLM로 자연스럽게 생성. 실패/비활성 시 기존 템플릿 유지.
    ENABLE_LLM_CLARIFY: bool = False

    # --- Reschedule (일정 변경 제안 설명 문장) ---
    # 시간 계산·후보·점수는 항상 규칙. LLM은 최상위 후보의 '설명 문장'만 생성.
    ENABLE_LLM_RESCHEDULE: bool = False

    # --- Preference memory (발화 → 지속 선호 추출) ---
    # 발화에서 지속적 선호(집중시간/알림/말투/습관)를 LLM으로 추출·저장. 개인/민감/
    # 건강 정보는 저장 금지(허용목록 + 블록리스트로 이중 차단). Default OFF.
    ENABLE_LLM_MEMORY: bool = False

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
        env_file=_ENV_FILES,
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
