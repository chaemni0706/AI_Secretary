"""Build MVP notification plans (reminders + checklist) for saved items.

Plan-only: NO OS push, NO external traffic/weather API. Rule-based, reuses
rules/checklist_rules.json (via departure_alert) and preference_service. EVENTs
get default + (location-gated) departure reminders; TODOs get deadline reminders.
Reminders with a computable trigger_time are also persisted to the existing
`reminders` table (idempotent replace) so lookups/dashboards can reuse them.

Never raises: missing start_time / all-day / missing due_date degrade to an
empty reminder list with a warning.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.database import repository as repo
from backend.database.schema.local_schedule_schema import ScheduleRead
from backend.database.schema.notification_plan_schema import (
    ChecklistEntry,
    DeliveryInfo,
    NotificationPlanView,
    ReminderEntry,
    ReminderPlan,
)
from backend.database.schema.todo_schema import TodoRead
from backend.services import preference_service
from backend.services import tts_response_builder, user_preference_service
from backend.services.departure_alert import _build_checklist  # reuse rules loader

_DEFAULT_TRAVEL_MINUTES = 30      # MVP fixed estimate (no traffic API)
_LATE_PRONE_EXTRA = 15            # default reminder brought earlier
_LATE_PRONE_DEPARTURE_EXTRA = 10  # departure reminder buffer bump
_DEADLINE_HOUR = "09:00"          # TODO due-day morning reminder

# enhanced parse categories -> legacy checklist_rules.json categories
_CAT_TO_CHECKLIST = {
    "health": "hospital", "work": "meeting", "study": "study", "meal": "restaurant",
    "beauty": "beauty", "personal": "etc",
    "hospital": "hospital", "meeting": "meeting", "school": "school",
    "restaurant": "restaurant", "exercise": "exercise", "travel": "travel", "etc": "etc",
}
_CAT_HINT = {
    "health": " 신분증과 예약 확인을 챙겨주세요.",
    "work": " 노트북과 회의 자료를 확인해주세요.",
    "study": " 교재와 자료를 확인해주세요.",
    "meal": " 예약 시간과 장소를 확인해주세요.",
    "beauty": " 예약 시간과 시술 내용을 확인해주세요.",
}
_RESERVATION_CATS = {"health", "beauty", "meal", "restaurant", "hospital"}
_SUBMIT_CATS = {"study", "work"}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _valid_hhmm(t: Optional[str]) -> bool:
    if not isinstance(t, str) or ":" not in t:
        return False
    try:
        h, m = (int(x) for x in t.split(":")[:2])
    except (ValueError, TypeError):
        return False
    return 0 <= h <= 23 and 0 <= m <= 59


def _trigger(date: Optional[str], hhmm: Optional[str], minutes_before: int) -> Optional[str]:
    """(date, 'HH:MM') - minutes_before -> ISO 'YYYY-MM-DDTHH:MM:SS'. None if unparseable."""
    if not date or not _valid_hhmm(hhmm):
        return None
    try:
        base = datetime.fromisoformat(f"{date}T{hhmm}:00")
    except ValueError:
        return None
    return (base - timedelta(minutes=max(0, minutes_before))).strftime("%Y-%m-%dT%H:%M:%S")


def _soft(pref) -> bool:
    return pref.notification_style == "soft" or pref.preferred_tone in ("gentle", "warm")


def _tail(pref) -> str:
    return "천천히 준비해볼까요?" if _soft(pref) else "준비해볼까요?"


def _strength_reminders(
    title: str, reminder_strength: Optional[str], date: Optional[str], hhmm: Optional[str]
) -> List[ReminderEntry]:
    """Extra reminders whose COUNT and MESSAGE scale with reminder_strength
    (gentle=1 / normal=2 / strong=3). Returns [] when strength is not provided,
    so the default plan is unchanged. Message/offsets come from the single
    source of truth in assistant_style_service."""
    if not reminder_strength:
        return []
    import logging
    from backend.services import assistant_style_service as style
    profile = style.build_style_profile({"reminder_strength": reminder_strength})
    offsets = style.reminder_offsets(profile)
    message = style.build_reminder_text(title, profile)
    _log = logging.getLogger("assistant_style")
    _log.info("[STYLE DEBUG] reminder_strength=%s offsets=%s message=%s",
              reminder_strength, offsets, message)
    out: List[ReminderEntry] = []
    for mb in offsets:
        out.append(ReminderEntry(
            type="reminder", minutes_before=mb,
            trigger_time=_trigger(date, hhmm, mb),
            message=message,
            reason=f"리마인드 강도({reminder_strength}) 설정을 반영했습니다.",
        ))
    return out


def _checklist(category: Optional[str], location: Optional[str], *, reservation: bool,
               submit: bool) -> List[ChecklistEntry]:
    legacy = _CAT_TO_CHECKLIST.get((category or "").lower(), "etc")
    items = [ChecklistEntry(item=c.item, reason=c.reason)
             for c in _build_checklist(legacy, None)]
    seen = {c.item for c in items}

    def _add(item: str, reason: str):
        if item not in seen:
            seen.add(item)
            items.append(ChecklistEntry(item=item, reason=reason))

    if reservation:
        _add("예약 확인", "예약 일정 확인을 위해 필요할 수 있습니다.")
    if submit:
        _add("제출 파일 확인", "제출 전 파일 확인이 필요할 수 있습니다.")
    if location:
        _add("장소 확인", f"방문 장소({location})를 미리 확인하세요.")
    return items


# --------------------------------------------------------------------------- #
# EVENT plan
# --------------------------------------------------------------------------- #
def build_event_plan(
    db: Session, sched: ScheduleRead, *, user_id: str, is_all_day: bool = False,
    persist: bool = True, reminder_strength: Optional[str] = None,
    custom_reminder_minutes: Optional[int] = None,
) -> ReminderPlan:
    """`custom_reminder_minutes` (additive, default None) overrides the default
    reminder's minutes-before exactly — no late-prone padding — so a voice
    request like "1시간 전에 알려줘" is honored literally. Omitted, behavior is
    byte-identical to before (uses the stored `default_reminder_minutes`)."""
    eff = preference_service.get_effective_user_preference(db, user_id)
    pref, meta = eff["preference"], eff["meta"]
    warnings: List[str] = []
    used: List[str] = []

    category = (sched.category or "").lower()
    title = sched.title or "일정"
    tail = _tail(pref)
    if _soft(pref):
        used.append("notification_style")

    has_time = (not is_all_day) and _valid_hhmm(sched.start_time)
    if is_all_day:
        warnings.append("종일 일정이라 알림 시각(trigger_time)을 계산하지 않았습니다.")
    elif not _valid_hhmm(sched.start_time):
        warnings.append("시작 시간이 없어 알림 시각(trigger_time)을 계산할 수 없습니다.")

    reminders: List[ReminderEntry] = []

    # 1) default reminder
    if custom_reminder_minutes is not None:
        default_mb = max(0, custom_reminder_minutes)
        reason = "사용자가 음성으로 요청한 알림 시간"
        used.append("custom_reminder_minutes")
    else:
        default_mb = max(0, pref.default_reminder_minutes) + (_LATE_PRONE_EXTRA if pref.late_prone else 0)
        reason = "사용자 기본 알림 시간"
        used.append("default_reminder_minutes")
        if _soft(pref):
            reason += "과 부드러운 알림 톤"
        if pref.late_prone:
            reason += ", 지각 경향 보정"
            used.append("late_prone")
    reminders.append(ReminderEntry(
        type="default", minutes_before=default_mb,
        trigger_time=_trigger(sched.date, sched.start_time, default_mb) if has_time else None,
        message=f"{default_mb}분 뒤 {title}이(가) 있어요. {tail}" + _CAT_HINT.get(category, ""),
        reason=reason + "을 반영했습니다.",
    ))

    # 2) departure reminder — only when a location is known
    if sched.location:
        used.append("departure_buffer_minutes")
        extra = _LATE_PRONE_DEPARTURE_EXTRA if pref.late_prone else 0
        dep_mb = _DEFAULT_TRAVEL_MINUTES + max(0, pref.departure_buffer_minutes) + extra
        trig = _trigger(sched.date, sched.start_time, dep_mb) if has_time else None
        when = trig[11:16] if trig else "출발 시각"
        dep_reason = (
            f"기본 이동 시간 {_DEFAULT_TRAVEL_MINUTES}분, 출발 버퍼 "
            f"{max(0, pref.departure_buffer_minutes)}분"
        )
        if extra:
            dep_reason += f", 지각 경향 보정 {extra}분"
        voice_prefs = user_preference_service.get_user_preferences(user_id)
        dep_tts = tts_response_builder.build_tts_response(
            intent="departure_alert",
            slots={"title": title, "time": when, "place": sched.location},
            preferences=voice_prefs,
        )
        reminders.append(ReminderEntry(
            type="departure", minutes_before=dep_mb, trigger_time=trig,
            message=f"기본 이동 시간과 준비 여유 시간을 고려하면 {when}쯤 준비를 시작하면 좋아요.",
            reason=dep_reason + "을 반영했습니다. (실제 교통 API는 사용하지 않는 기본 이동 시간 기준)",
            tts_text=dep_tts,
        ))
    else:
        warnings.append("위치 정보가 없어 출발 알림을 생성하지 않았습니다.")

    # 3) reminder-strength scaled reminders (opt-in; default plan unchanged)
    strength_reminders = _strength_reminders(
        title, reminder_strength, sched.date, sched.start_time if has_time else None
    )
    if strength_reminders:
        reminders.extend(strength_reminders)
        used.append("reminder_strength")

    checklist = _checklist(
        category, sched.location,
        reservation=(category in _RESERVATION_CATS or "예약" in title),
        submit=False,
    )
    meta.used_preferences = _dedupe(used)
    if meta.personalization_applied:
        meta.reason = "기본 알림 시간·출발 버퍼·지각 경향·알림 톤을 반영했습니다."

    if persist:
        _persist(db, sched.id, reminders)

    return ReminderPlan(reminders=reminders, checklist=checklist,
                        personalization=meta, delivery=DeliveryInfo(), warnings=warnings)


# --------------------------------------------------------------------------- #
# TODO plan (deadline only; no departure)
# --------------------------------------------------------------------------- #
def build_todo_plan(
    db: Session, todo: TodoRead, *, user_id: str, persist: bool = True,
    reminder_strength: Optional[str] = None,
) -> ReminderPlan:
    eff = preference_service.get_effective_user_preference(db, user_id)
    pref, meta = eff["preference"], eff["meta"]
    warnings: List[str] = []
    used: List[str] = []

    category = (todo.category or "").lower()
    title = todo.title or "할 일"
    tail = _tail(pref)
    if _soft(pref):
        used.append("notification_style")

    reminders: List[ReminderEntry] = []
    if todo.due_date:
        reminders.append(ReminderEntry(
            type="deadline", minutes_before=None,
            trigger_time=_trigger(todo.due_date, _DEADLINE_HOUR, 0),
            message=f"오늘 {title} 마감이 있어요. 오전에 한 번 확인해볼까요?",
            reason="할 일 마감일 기준 당일 오전 알림을 생성했습니다.",
        ))
        # high priority -> add a day-before reminder
        if todo.priority == "high":
            try:
                prev = (datetime.fromisoformat(f"{todo.due_date}T18:00:00") - timedelta(days=1))
                reminders.append(ReminderEntry(
                    type="deadline", minutes_before=None,
                    trigger_time=prev.strftime("%Y-%m-%dT%H:%M:%S"),
                    message=f"내일 {title} 마감이에요. 미리 준비해볼까요?" if not _soft(pref)
                            else f"내일 {title} 마감이에요. 천천히 미리 준비해볼까요?",
                    reason="우선순위가 높아 하루 전 알림을 추가했습니다.",
                ))
            except ValueError:
                pass
    else:
        warnings.append("마감일(due_date)이 없어 마감 알림을 생성하지 않았습니다.")

    # reminder-strength scaled reminders (opt-in; default plan unchanged)
    strength_reminders = _strength_reminders(
        title, reminder_strength, todo.due_date, _DEADLINE_HOUR if todo.due_date else None
    )
    if strength_reminders:
        reminders.extend(strength_reminders)
        used.append("reminder_strength")

    checklist = _checklist(category, None, reservation=False, submit=(category in _SUBMIT_CATS))
    meta.used_preferences = _dedupe(used)
    if meta.personalization_applied:
        meta.reason = "마감 알림 톤을 개인 선호에 맞춰 조정했습니다."

    if persist:
        _persist(db, todo.id, reminders)

    return ReminderPlan(reminders=reminders, checklist=checklist,
                        personalization=meta, delivery=DeliveryInfo(), warnings=warnings)


# --------------------------------------------------------------------------- #
# persistence (idempotent) + lookup
# --------------------------------------------------------------------------- #
_TYPE_TO_DB = {"default": "STANDARD", "departure": "DEPARTURE", "deadline": "STANDARD"}


def _persist(db: Session, item_id: str, reminders: List[ReminderEntry]) -> int:
    """Idempotent replace into the reminders table (only entries with a trigger)."""
    rows = [
        {"reminder_type": _TYPE_TO_DB.get(r.type, "STANDARD"),
         "trigger_at": r.trigger_time, "message_text": r.message}
        for r in reminders if r.trigger_time
    ]
    try:
        n = repo.replace_reminders_for_item(db, item_id=item_id, reminders=rows)
        db.commit()
        return n
    except Exception:
        db.rollback()
        return 0


def build_plan_for_item(db: Session, item_id: str) -> Optional[NotificationPlanView]:
    """Rebuild the plan for a saved EVENT/TODO (idempotent). None if not found."""
    item = repo.get_planner_item(db, item_id)
    if item is None:
        return None
    user_id = item.user_id or repo.DEFAULT_USER_ID

    if item.item_type == "EVENT":
        from backend.services import local_schedule_service as sched_service
        sched = sched_service.get_schedule(db, item_id)
        if sched is None:
            return None
        ev = item.event_detail
        is_all_day = bool(getattr(ev, "is_all_day", 0)) if ev is not None else False
        plan = build_event_plan(db, sched, user_id=user_id, is_all_day=is_all_day)
        return NotificationPlanView(
            item_id=item_id, item_type="EVENT", title=sched.title, date=sched.date,
            start_time=sched.start_time, category=sched.category, location=sched.location,
            reminder_plan=plan,
        )

    if item.item_type == "TODO":
        from backend.services import todo_service
        todo = todo_service.get_todo(db, item_id)
        if todo is None:
            return None
        plan = build_todo_plan(db, todo, user_id=user_id)
        return NotificationPlanView(
            item_id=item_id, item_type="TODO", title=todo.title, due_date=todo.due_date,
            category=todo.category, reminder_plan=plan,
        )
    return None


def _dedupe(items: List[str]) -> List[str]:
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
