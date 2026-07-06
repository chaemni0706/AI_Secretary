"""Per-user AI voice-response style preferences (rule-based MVP, no LLM).

Three independent axes control how `tts_response_builder` phrases a sentence:

    assistant_tone   -> polite | friendly | concise | caring | professional
    response_length  -> short | normal | detailed
    nudge_strength   -> low | medium | high

Storage is a process-local in-memory dict. This is intentionally the ONLY
place that knows about storage: swapping to SQLite/a real user table later
only requires reimplementing `_load(user_id)` / `_save(user_id, prefs)` here,
the public function signatures stay the same.

Never raises: unknown/invalid values fall back to the default for that axis.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

DEFAULT_PREFERENCES: Dict[str, str] = {
    "assistant_tone": "friendly",
    "response_length": "normal",
    "nudge_strength": "medium",
    # additive: 'HH:mm' 자동 브리핑 시각, ""이면 비활성화. 자유 형식이라 VALID_VALUES
    # (enum) 이 아니라 _BRIEFING_TIME_RE 로 별도 검증한다.
    "briefing_time": "",
}

VALID_VALUES: Dict[str, tuple] = {
    "assistant_tone": ("polite", "friendly", "concise", "caring", "professional"),
    "response_length": ("short", "normal", "detailed"),
    "nudge_strength": ("low", "medium", "high"),
}

BRIEFING_TIME_KEY = "briefing_time"
_BRIEFING_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

# Display metadata for the two axes that have no dedicated JSON file
# (assistant_tone's display names live in backend/data/tone_profiles.json).
_DISPLAY_NAMES: Dict[str, Dict[str, str]] = {
    "response_length": {"short": "짧게", "normal": "보통", "detailed": "자세하게"},
    "nudge_strength": {"low": "거의 안 함", "medium": "적당히", "high": "꼼꼼하게"},
}

_DEFAULT_USER_ID = "local-user"

# --------------------------------------------------------------------------- #
# storage layer (swap this block for SQLite/a real table later)
# --------------------------------------------------------------------------- #
_STORE: Dict[str, Dict[str, str]] = {}


def _load(user_id: str) -> Dict[str, str]:
    return dict(_STORE.get(user_id, {}))


def _save(user_id: str, prefs: Dict[str, str]) -> None:
    _STORE[user_id] = dict(prefs)


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def _normalize_user_id(user_id: Optional[str]) -> str:
    if not user_id or not str(user_id).strip():
        return _DEFAULT_USER_ID
    return str(user_id).strip()


def get_default_preferences() -> Dict[str, str]:
    """Always-fresh copy of the 3-axis defaults."""
    return dict(DEFAULT_PREFERENCES)


def normalize_preference_value(category: str, value: Optional[str]) -> Optional[str]:
    """Return `value` if it is a valid option for `category`, else None.
    Unknown categories also return None (never raises)."""
    if category == BRIEFING_TIME_KEY:
        if not isinstance(value, str):
            return None
        value = value.strip()
        if value == "":
            return ""  # explicit disable
        return value if _BRIEFING_TIME_RE.match(value) else None
    options = VALID_VALUES.get(category)
    if not options or not isinstance(value, str):
        return None
    value = value.strip()
    return value if value in options else None


def validate_preferences(preferences: dict) -> Dict[str, str]:
    """Keep only recognized axes with valid values from an arbitrary dict.
    Unknown keys and invalid values are silently dropped (never raises)."""
    if not isinstance(preferences, dict):
        return {}
    cleaned: Dict[str, str] = {}
    for category in list(VALID_VALUES) + [BRIEFING_TIME_KEY]:
        val = normalize_preference_value(category, preferences.get(category))
        if val is not None:
            cleaned[category] = val
    return cleaned


def get_user_preferences(user_id: Optional[str]) -> Dict[str, str]:
    """Effective preferences for a user: defaults overlaid by any stored,
    validated values. Always returns all 3 axes."""
    uid = _normalize_user_id(user_id)
    prefs = dict(DEFAULT_PREFERENCES)
    prefs.update(validate_preferences(_load(uid)))
    return prefs


def update_user_preferences(user_id: Optional[str], updates: dict) -> Dict[str, str]:
    """Merge only the valid, provided axes into the user's stored preferences
    and return the new effective preferences. Invalid/unknown fields in
    `updates` are ignored rather than raising."""
    uid = _normalize_user_id(user_id)
    current = get_user_preferences(uid)
    current.update(validate_preferences(updates))
    _save(uid, current)
    return current


def get_options() -> Dict[str, list]:
    """{category: [{code, display_name}, ...]} for the Flutter settings screen."""
    try:
        from backend.services.tts_response_builder import load_tone_profiles

        tone_meta = load_tone_profiles()
    except Exception:
        tone_meta = {}

    options: Dict[str, list] = {}
    options["assistant_tone"] = [
        {"code": code, "display_name": tone_meta.get(code, {}).get("display_name", code)}
        for code in VALID_VALUES["assistant_tone"]
    ]
    for category in ("response_length", "nudge_strength"):
        options[category] = [
            {"code": code, "display_name": _DISPLAY_NAMES[category].get(code, code)}
            for code in VALID_VALUES[category]
        ]
    return options
