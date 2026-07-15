"""Effective user-preference layer (rule-based, no LLM/external calls).

Bridges the EXISTING memory_service values (notification_preference,
default_buffer_minutes, ...) and richer personalization fields stored as
`pref_*` PREFERENCE rows in the same user_memories table (no schema change).

`get_effective_user_preference` always returns a fully-populated preference:
stored values merged over defaults, invalid values ignored, and metadata telling
callers whether personalization was actually applied. It NEVER raises.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.database import repository as repo
from backend.database.schema.personalization_schema import (
    COACHING_STYLES,
    NOTIFICATION_STYLES,
    TIME_BUCKETS,
    TONES,
    Personalization,
    PreferenceUpdate,
    UserPreference,
)
from backend.services import memory_service

_PREF_PREFIX = "pref_"

DEFAULT_PREFERENCE: Dict[str, object] = {
    "preferred_reservation_times": ["afternoon", "evening"],
    "avoid_times": [],
    "default_reminder_minutes": 30,
    "departure_buffer_minutes": 10,
    "late_prone": False,
    "preferred_tone": "neutral",
    "coaching_style": "supportive",
    "stress_triggers": [],
    "rest_recommendation_enabled": True,
    "notification_style": "normal",
}

_LIST_BUCKET_KEYS = {"preferred_reservation_times", "avoid_times"}
_INT_KEYS = {"default_reminder_minutes", "departure_buffer_minutes"}
_BOOL_KEYS = {"late_prone", "rest_recommendation_enabled"}
_STR_ENUM = {
    "preferred_tone": TONES,
    "coaching_style": COACHING_STYLES,
    "notification_style": NOTIFICATION_STYLES,
}


# --------------------------------------------------------------------------- #
# time-of-day helper (shared with reservation ranking)
# --------------------------------------------------------------------------- #
def time_block_of(hhmm: Optional[str]) -> Optional[str]:
    """'HH:MM' -> time bucket, or None if unparseable."""
    if not isinstance(hhmm, str) or ":" not in hhmm:
        return None
    try:
        h = int(hhmm.split(":")[0])
    except (ValueError, IndexError):
        return None
    if h < 6:
        return "late_night"
    if h < 9:
        return "early_morning"
    if h < 12:
        return "morning"
    if h < 18:
        return "afternoon"
    if h < 22:
        return "evening"
    return "late_night"


# --------------------------------------------------------------------------- #
# validation / coercion (invalid -> default, never raises)
# --------------------------------------------------------------------------- #
def _coerce(key: str, value) -> Tuple[bool, object]:
    """Return (ok, coerced_value). ok=False means the value was invalid and
    should be ignored (caller keeps the default)."""
    if key in _LIST_BUCKET_KEYS:
        if not isinstance(value, list):
            return False, None
        cleaned = [v for v in value if isinstance(v, str) and v in TIME_BUCKETS]
        return True, cleaned
    if key == "stress_triggers":
        if not isinstance(value, list):
            return False, None
        cleaned = [v.strip() for v in value if isinstance(v, str) and v.strip()]
        return True, cleaned
    if key in _INT_KEYS:
        try:
            iv = int(value)
        except (TypeError, ValueError):
            return False, None
        if iv < 0:
            return False, None
        return True, iv
    if key in _BOOL_KEYS:
        if isinstance(value, bool):
            return True, value
        return False, None
    if key in _STR_ENUM:
        if isinstance(value, str) and value in _STR_ENUM[key]:
            return True, value
        return False, None
    return False, None


def _load_stored_pref(db: Session, user_id: str) -> Tuple[Dict[str, str], bool]:
    """Return ({field: raw_value} from pref_* rows, any_memory_row_exists)."""
    rows = repo.get_active_memories(db, user_id)
    stored: Dict[str, str] = {}
    for r in rows:
        if r.memory_key.startswith(_PREF_PREFIX):
            stored[r.memory_key[len(_PREF_PREFIX):]] = r.memory_value_masked
    return stored, bool(rows)


def _decode(key: str, raw: str):
    if key in _LIST_BUCKET_KEYS or key == "stress_triggers":
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None
    if key in _INT_KEYS:
        return raw
    if key in _BOOL_KEYS:
        return raw == "true" or raw is True
    return raw


def get_effective_user_preference(db: Session, user_id: Optional[str]) -> dict:
    """Merged preference + personalization metadata. Never raises."""
    user_id = user_id or repo.DEFAULT_USER_ID
    pref: Dict[str, object] = dict(DEFAULT_PREFERENCE)

    try:
        legacy = memory_service.get_memory(db, user_id)
        stored_pref, has_memory = _load_stored_pref(db, user_id)
    except Exception:
        legacy, stored_pref, has_memory = None, {}, False

    used: List[str] = []

    # 1) bridge from the legacy memory_service fields (reuse existing storage)
    if legacy is not None:
        if legacy.notification_preference == "late_prone":
            pref["late_prone"] = True
        if isinstance(legacy.default_buffer_minutes, int) and legacy.default_buffer_minutes >= 0:
            pref["departure_buffer_minutes"] = legacy.default_buffer_minutes
        if legacy.notification_preference == "strong":
            pref["notification_style"] = "strong"

    # 2) overlay richer pref_* fields (validated; invalid ignored)
    for field, raw in stored_pref.items():
        if field not in DEFAULT_PREFERENCE:
            continue
        ok, val = _coerce(field, _decode(field, raw))
        if ok:
            pref[field] = val

    preference = UserPreference(user_id=user_id, **pref)
    applied = bool(has_memory)
    meta = Personalization(
        personalization_applied=applied,
        memory_source="stored_preference" if applied else "default_preference",
        used_preferences=used,
    )
    return {
        "preference": preference,
        "personalization_applied": applied,
        "memory_source": meta.memory_source,
        "meta": meta,
    }


def save_preference(db: Session, user_id: Optional[str], patch: PreferenceUpdate) -> dict:
    """Persist provided, VALID preference fields as pref_* PREFERENCE rows.
    Invalid values are skipped (not an error). Returns the effective preference."""
    user_id = user_id or repo.DEFAULT_USER_ID
    provided = patch.model_dump(exclude_none=True)

    writable: Dict[str, str] = {}
    for field, value in provided.items():
        ok, val = _coerce(field, value)
        if not ok:
            continue
        if field in _LIST_BUCKET_KEYS or field == "stress_triggers":
            writable[field] = json.dumps(val, ensure_ascii=False)
        elif field in _BOOL_KEYS:
            writable[field] = "true" if val else "false"
        else:
            writable[field] = str(val)

    if writable:
        repo.ensure_user(db, user_id)
        for field, raw in writable.items():
            repo.upsert_memory(
                db, user_id=user_id, memory_type="PREFERENCE",
                memory_key=_PREF_PREFIX + field, value=raw,
            )
        db.commit()

    return get_effective_user_preference(db, user_id)
