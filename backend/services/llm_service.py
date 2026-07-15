"""LLM service.

Single `generate()` entry point used by feature services.
- If `OPENAI_API_KEY` is not configured, returns None so callers fall back
  to their template implementation.
- The OpenAI client is imported lazily so the package is optional at runtime.
- Any error (no key / network / quota / rate-limit / timeout / bad JSON) is
  swallowed and reported as None — callers MUST treat None as "use template
  fallback". This keeps the whole app working rule-based when the LLM is
  unavailable (Hybrid: LLM-우선 + 규칙 fallback).

Wire real prompts/models here without touching callers.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from backend.core.config import settings

logger = logging.getLogger("llm_service")

# 출력 토큰 상한. 비용/응답시간 폭주를 막는 안전장치이며, 호출부에서 max_tokens
# 인자로 개별 조정할 수 있다(분류/슬롯추출은 작게, 브리핑 등 긴 문장은 크게).
DEFAULT_MAX_TOKENS = 600


def is_enabled() -> bool:
    """True when an API key is configured."""
    return bool(settings.OPENAI_API_KEY)


def _classify_error(exc: Exception) -> str:
    """예외를 사용자 진단용 사유 문자열로 매핑(로그용). 실패해도 항상 None 반환은 동일."""
    reason = type(exc).__name__
    try:  # openai 예외 타입은 있을 때만 세분화(패키지 없으면 그냥 타입명).
        import openai

        if isinstance(exc, openai.APITimeoutError):
            return "timeout"
        if isinstance(exc, openai.RateLimitError):
            return "rate_limit"
        if isinstance(exc, openai.AuthenticationError):
            return "auth_invalid_key"
        if isinstance(exc, openai.APIConnectionError):
            return "network"
        if isinstance(exc, openai.BadRequestError):
            return "bad_request"
        if isinstance(exc, openai.APIStatusError):
            return f"api_status_{getattr(exc, 'status_code', '?')}"
    except Exception:
        pass
    return reason


def generate(
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    response_format: Optional[dict] = None,
    max_tokens: Optional[int] = None,
) -> Optional[str]:
    """Return generated text, or None if LLM is unavailable / fails.

    실패 유형(키없음/타임아웃/네트워크/레이트리밋/기타)은 모두 None 으로 수렴하며,
    호출부는 None 을 "템플릿 fallback 사용"으로 처리한다(기존 계약 그대로).

    `response_format` 은 OpenAI 클라이언트로 그대로 전달된다
    (예: {"type": "json_object"} 로 JSON 모드). `max_tokens` 미지정 시
    [DEFAULT_MAX_TOKENS] 가 적용된다.
    """
    if not is_enabled():
        logger.debug("LLM 비활성(OPENAI_API_KEY 없음) → 템플릿 fallback")
        return None

    model = model or settings.OPENAI_MODEL
    temperature = settings.LLM_TEMPERATURE if temperature is None else temperature
    max_tokens = max_tokens or DEFAULT_MAX_TOKENS
    started = time.monotonic()

    try:
        from openai import OpenAI  # lazy import; optional dependency

        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        extra = {"response_format": response_format} if response_format else {}

        logger.info(
            "LLM 호출 model=%s json=%s temp=%.2f max_tokens=%d prompt_len=%d",
            model, bool(response_format), temperature, max_tokens, len(prompt or ""),
        )
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **extra,
        )
        elapsed_ms = (time.monotonic() - started) * 1000

        text = (resp.choices[0].message.content or "").strip()
        # 모델이 코드펜스/따옴표로 감싸는 경우가 있어 벗겨 깔끔한 본문만 돌려준다.
        text = text.strip("`").strip().strip("\"'“”").strip()
        if not text:
            logger.warning("LLM 빈 응답(%.0fms) → 템플릿 fallback", elapsed_ms)
            return None
        logger.info("LLM 성공(%.0fms, %d자)", elapsed_ms, len(text))
        return text
    except Exception as exc:  # 어떤 실패든 앱을 멈추지 않고 fallback 으로.
        elapsed_ms = (time.monotonic() - started) * 1000
        logger.warning(
            "LLM 호출 실패 reason=%s (%.0fms) → 템플릿 fallback: %s",
            _classify_error(exc), elapsed_ms, exc,
        )
        return None


def generate_json(
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
) -> Optional[dict]:
    """JSON 모드 전용 헬퍼. 파싱된 dict 를 반환하며, 키없음/오류/JSON 파싱 실패 시
    None 을 반환한다(호출부는 규칙 fallback). 분류·슬롯추출·선호 추출처럼
    구조화 출력이 필요한 곳에서 사용한다. 기본 temperature=0.0(결정적)."""
    raw = generate(
        prompt,
        system=system,
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        max_tokens=max_tokens,
    )
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("LLM JSON 파싱 실패 → 규칙 fallback: %s", exc)
        return None
    if not isinstance(data, dict):
        logger.warning("LLM JSON 이 객체가 아님(%s) → 규칙 fallback", type(data).__name__)
        return None
    return data
