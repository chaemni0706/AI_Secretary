"""LLM service.

Single `generate()` entry point used by feature services.
- If `OPENAI_API_KEY` is not configured, returns None so callers fall back
  to their template implementation.
- The OpenAI client is imported lazily so the package is optional at runtime.
- Any error (network, quota, missing package, timeout) is swallowed and
  reported as None — callers MUST treat None as "use template fallback".

Wire real prompts/models here without touching callers.
"""

from __future__ import annotations

from typing import Optional

from backend.core.config import settings


def is_enabled() -> bool:
    """True when an API key is configured."""
    return bool(settings.OPENAI_API_KEY)


def generate(
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> Optional[str]:
    """Return generated text, or None if LLM is unavailable / fails."""
    if not is_enabled():
        return None
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
        resp = client.chat.completions.create(
            model=model or settings.OPENAI_MODEL,
            messages=messages,
            temperature=settings.LLM_TEMPERATURE if temperature is None else temperature,
        )
        text = (resp.choices[0].message.content or "").strip()
        # Models sometimes wrap the reply in code fences or quotes; strip them so
        # callers get a clean message body to use directly.
        text = text.strip("`").strip().strip("\"'\u201c\u201d").strip()
        return text or None
    except Exception:
        return None
