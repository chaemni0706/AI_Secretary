"""Personal memory / user-preference service (rule-based MVP).

Stores preferences/places as rows in user_memories (memory_type PREFERENCE /
PLACE), keyed by memory_key. Provides get_user_context() for alert/reservation.
No LLM, RAG, vector DB, or external calls.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.database import repository as repo
from backend.services import llm_service
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


def to_alert_preference(notification_preference: str) -> dict:
    """Public: map a single notification_preference to alert UserPreference fields."""
    return _to_alert_preference(notification_preference)


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


# ==========================================================================  #
# Learned preferences (발화 → 지속 선호 추출/저장)                              #
# ==========================================================================  #
_logger = logging.getLogger("memory_service")

# 학습된 선호를 담는 별도 memory_key (기존 MemoryData 스키마 불변). JSON dict 저장.
_LEARNED_KEY = "learned_preferences"

# 저장 허용 항목(허용목록). enum 이 있는 키는 값도 화이트리스트로 강제한다.
_ALLOWED_PREF: Dict[str, Optional[set]] = {
    "preferred_focus_time": {"morning", "afternoon", "evening", "night"},  # 일정 선호 시간
    "notification_preference": {"normal", "strong", "forgetful", "late_prone"},  # 알림 선호
    "assistant_tone": {"formal", "friendly", "caring", "concise"},  # 말투 선호
    "repeat_habit": None,  # 반복 습관(짧은 자유 토큰; 아래 길이/블록리스트로 제한)
}

# 저장 금지 신호(개인/민감/건강). 값이든 키든 하나라도 걸리면 폐기.
_SENSITIVE = re.compile(
    r"(주민|여권|계좌|비밀번호|전화|연락처|휴대폰|이메일|메일주소|주소|생년월일|"
    r"카드번호|병|질환|질병|우울증|불안장애|약물|복용|처방|진단|증상|혈압|당뇨|"
    r"임신|장애|성적|종교|정치)"
)
_REPEAT_HABIT_MAX = 20


def _is_sensitive(text: str) -> bool:
    return bool(_SENSITIVE.search(text or ""))


def _validate_pref(key: str, value) -> Optional[Dict[str, str]]:
    """허용목록/블록리스트로 검증한 (key, value) 반환. 위반 시 None."""
    if not isinstance(key, str) or key not in _ALLOWED_PREF:
        return None
    if value is None:
        return None
    val = str(value).strip()
    if not val or _is_sensitive(val) or _is_sensitive(key):
        return None
    allowed = _ALLOWED_PREF[key]
    if allowed is not None:
        val = val.lower()
        if val not in allowed:
            return None
    else:  # 자유 토큰(repeat_habit): 길이 제한.
        if len(val) > _REPEAT_HABIT_MAX:
            return None
    return {"key": key, "value": val}


def extract_preference(text: str) -> Optional[Dict[str, str]]:
    """발화에서 '지속 선호'를 LLM(JSON)으로 추출·검증. 허용목록 밖/민감/파싱실패/
    키없음 시 None. 반환: {"key","value"} 또는 None."""
    prompt = (
        f'발화: "{text}"\n'
        "이 발화에 드러난 사용자의 '지속적 선호'를 아래 허용 항목 중 하나로만 추출해.\n"
        "- preferred_focus_time: morning|afternoon|evening|night (집중 잘 되는 시간대)\n"
        "- notification_preference: normal|strong|forgetful|late_prone (알림 성향)\n"
        "- assistant_tone: formal|friendly|caring|concise (말투 선호)\n"
        "- repeat_habit: 20자 이내 짧은 습관 표현\n"
        "이름·연락처·주소·계정·질병·약·진단 등 개인정보/민감정보/건강정보는 절대 추출하지 마.\n"
        "지속 선호가 아니거나 허용 항목이 아니면 {\"type\":\"none\"}.\n"
        '출력은 JSON만: {"type":"preference","key":"<허용키>","value":"<허용값>"} 또는 {"type":"none"}'
    )
    data = llm_service.generate_json(
        prompt,
        system="너는 선호 추출기야. 허용 항목만 JSON 하나로 출력하고 민감정보는 절대 담지 마.",
        temperature=0.0,
    )
    if not data or data.get("type") != "preference":
        return None
    return _validate_pref(data.get("key"), data.get("value"))


def get_learned_preferences(db: Session, user_id: str) -> Dict[str, str]:
    """저장된 학습 선호 dict(없으면 {})."""
    rows = repo.get_active_memories(db, user_id)
    for r in rows:
        if r.memory_key == _LEARNED_KEY:
            try:
                data = json.loads(r.memory_value_masked)
                return data if isinstance(data, dict) else {}
            except (TypeError, ValueError):
                return {}
    return {}


def save_learned_preference(db: Session, user_id: str, key: str, value: str) -> Dict[str, str]:
    """검증된 (key,value)를 learned_preferences JSON 에 병합 저장."""
    repo.ensure_user(db, user_id)
    current = get_learned_preferences(db, user_id)
    current[key] = value
    repo.upsert_memory(
        db, user_id=user_id, memory_type="PREFERENCE",
        memory_key=_LEARNED_KEY, value=json.dumps(current, ensure_ascii=False),
    )
    db.commit()
    return current


def extract_and_save_preference(db: Session, user_id: str, text: str) -> Optional[Dict[str, str]]:
    """발화 → 선호 추출 → (허용/비민감이면) 저장. 저장한 {key,value} 또는 None.
    ENABLE_LLM_MEMORY OFF/키없음/추출실패 시 아무것도 저장하지 않고 None."""
    if not (settings.ENABLE_LLM_MEMORY and llm_service.is_enabled()):
        return None
    try:
        pref = extract_preference(text)
    except Exception:
        _logger.exception("preference extraction failed for text=%r", text)
        return None
    if not pref:
        return None
    save_learned_preference(db, user_id, pref["key"], pref["value"])
    _logger.info("[MEMORY] learned preference saved: %s=%s", pref["key"], pref["value"])
    return pref


def build_recommendation_profile(db: Session, user_id: str) -> Dict[str, object]:
    """학습 선호를 다른 서비스가 쓰는 형태로 매핑(추천 활용).
    - preferred_focus_time → reschedule user_profile.preferred_time_blocks
    - assistant_tone → assistant_style prefs(assistant_tone)
    - notification_preference → alert/notification
    """
    prefs = get_learned_preferences(db, user_id)
    profile: Dict[str, object] = {}
    focus = prefs.get("preferred_focus_time")
    if focus in _ALLOWED_PREF["preferred_focus_time"]:
        profile["preferred_time_blocks"] = [focus]
    if prefs.get("assistant_tone"):
        profile["assistant_tone"] = prefs["assistant_tone"]
    if prefs.get("notification_preference"):
        profile["notification_preference"] = prefs["notification_preference"]
    if prefs.get("repeat_habit"):
        profile["repeat_habit"] = prefs["repeat_habit"]
    return profile
