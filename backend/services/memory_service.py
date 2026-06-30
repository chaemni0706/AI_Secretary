"""Personal memory / user-preference service (rule-based MVP).

Stores preferences/places as rows in user_memories (memory_type PREFERENCE /
PLACE), keyed by memory_key. Provides get_user_context() for alert/reservation.
No LLM, RAG, vector DB, or external calls.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.database import repository as repo
from backend.database.schema.memory_schema import (
    MemoryData,
    MemoryUpsert,
    PlaceCreate,
    PlaceItem,
    PreferencesPatch,
)

NOTIF_VALUES = {"normal", "strong", "forgetful", "late_prone"}
TRANSPORT_VALUES = {"walk", "car", "public_transport"}

DEFAULTS: Dict[str, object] = {
    "notification_preference": "normal",
    "default_travel_minutes": 30,
    "default_buffer_minutes": 10,
    "preferred_transport": "public_transport",
    "home_location": None,
    "work_or_school_location": None,
    "frequently_visited_places": [],
    "checklist_preferences": [],
}

# memory_type per key (PREFERENCE vs PLACE), matching local_schema.sql CHECK
KEY_TYPE = {
    "notification_preference": "PREFERENCE",
    "default_travel_minutes": "PREFERENCE",
    "default_buffer_minutes": "PREFERENCE",
    "preferred_transport": "PREFERENCE",
    "checklist_preferences": "PREFERENCE",
    "home_location": "PLACE",
    "work_or_school_location": "PLACE",
    "frequently_visited_places": "PLACE",
}

_INT_KEYS = {"default_travel_minutes", "default_buffer_minutes"}
_JSON_KEYS = {"frequently_visited_places", "checklist_preferences"}


# --- (de)serialization to user_memories.memory_value_masked (TEXT) ----------
def _dump(key: str, value) -> str:
    if key in _INT_KEYS:
        return str(max(0, int(value)))
    if key in _JSON_KEYS:
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _parse(key: str, raw: str):
    if key in _INT_KEYS:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return DEFAULTS[key]
    if key in _JSON_KEYS:
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return []
    return raw


def _validate(notification_preference: Optional[str], preferred_transport: Optional[str]) -> None:
    if notification_preference is not None and notification_preference not in NOTIF_VALUES:
        raise ValueError(f"notification_preference는 {sorted(NOTIF_VALUES)} 중 하나여야 합니다.")
    if preferred_transport is not None and preferred_transport not in TRANSPORT_VALUES:
        raise ValueError(f"preferred_transport는 {sorted(TRANSPORT_VALUES)} 중 하나여야 합니다.")


# --- reads ------------------------------------------------------------------
def get_memory(db: Session, user_id: str) -> MemoryData:
    """Stored values merged over defaults. Missing user -> defaults (no write)."""
    rows = repo.get_active_memories(db, user_id)
    stored = {r.memory_key: r.memory_value_masked for r in rows}
    updated = max((r.updated_at for r in rows), default=None)

    data: Dict[str, object] = dict(DEFAULTS)
    data["user_id"] = user_id
    for key in DEFAULTS:
        if key in stored:
            data[key] = _parse(key, stored[key])
    data["updated_at"] = updated
    return MemoryData(**data)


def get_user_context(db: Session, user_id: str) -> dict:
    """Context for alert/reservation. Includes an alert_user_preference mapping
    from the single notification_preference to the alert API's fields."""
    mem = get_memory(db, user_id)
    return {
        "user_id": user_id,
        "notification_preference": mem.notification_preference,
        "default_travel_minutes": mem.default_travel_minutes,
        "default_buffer_minutes": mem.default_buffer_minutes,
        "preferred_transport": mem.preferred_transport,
        "frequently_visited_places": [p.model_dump() for p in mem.frequently_visited_places],
        "alert_user_preference": _to_alert_preference(mem.notification_preference),
    }


def _to_alert_preference(np: str) -> dict:
    table = {
        "normal": {"notification_style": "normal", "forgetful": False, "late_prone": False},
        "strong": {"notification_style": "strong", "forgetful": False, "late_prone": False},
        "forgetful": {"notification_style": "normal", "forgetful": True, "late_prone": False},
        "late_prone": {"notification_style": "normal", "forgetful": False, "late_prone": True},
    }
    return table.get(np, table["normal"])


# --- writes -----------------------------------------------------------------
def _write_fields(db: Session, user_id: str, fields: Dict[str, object]) -> MemoryData:
    # No-op guard: an empty PUT/PATCH writes nothing, so don't create a user
    # row (or any user_memories row) — just return current (default) memory.
    writable = {k: v for k, v in fields.items() if v is not None}
    if not writable:
        return get_memory(db, user_id)

    repo.ensure_user(db, user_id)
    for key, value in writable.items():
        repo.upsert_memory(
            db, user_id=user_id, memory_type=KEY_TYPE[key],
            memory_key=key, value=_dump(key, value),
        )
    db.commit()
    return get_memory(db, user_id)


def upsert_memory(db: Session, user_id: str, payload: MemoryUpsert) -> MemoryData:
    _validate(payload.notification_preference, payload.preferred_transport)
    fields = payload.model_dump(exclude_none=True)
    if "frequently_visited_places" in fields:
        fields["frequently_visited_places"] = [
            p.model_dump() if isinstance(p, PlaceItem) else p
            for p in payload.frequently_visited_places
        ]
    return _write_fields(db, user_id, fields)


def patch_preferences(db: Session, user_id: str, payload: PreferencesPatch) -> MemoryData:
    _validate(payload.notification_preference, payload.preferred_transport)
    return _write_fields(db, user_id, payload.model_dump(exclude_none=True))


def add_place(db: Session, user_id: str, place: PlaceCreate) -> MemoryData:
    current = get_memory(db, user_id).frequently_visited_places
    places: List[dict] = [p.model_dump() for p in current]
    places.append(place.model_dump())
    return _write_fields(db, user_id, {"frequently_visited_places": places})
