"""Preference-aware reminder recommendation (rule-based, no push delivery).

Given a schedule-ish input (title/category/start_time/travel) and the user's
effective preference, produce reminder suggestions:
  * a "default" reminder at `default_reminder_minutes` before the event, and
  * a "departure" reminder at (travel + departure_buffer) before, when a
    start_time + travel are known.
Late-prone users get earlier reminders; `notification_style` sets the tone.
Never raises.
"""

from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from backend.database.schema.personalization_schema import (
    ReminderItem,
    ReminderRecommendData,
    ReminderRecommendRequest,
)
from backend.services import preference_service

_LATE_PRONE_EXTRA = 15   # minutes added for late-prone users

_STYLE_TAIL = {
    "soft": "천천히 준비해볼까요?",
    "normal": "준비를 시작하는 게 좋아요.",
    "strong": "지금 바로 준비하세요!",
}


def _subject(req: ReminderRecommendRequest) -> str:
    return (req.title or "일정").strip() or "일정"


def recommend_reminders(db: Session, req: ReminderRecommendRequest) -> ReminderRecommendData:
    eff = preference_service.get_effective_user_preference(db, req.user_id)
    pref, meta = eff["preference"], eff["meta"]
    style = pref.notification_style
    tail = _STYLE_TAIL.get(style, _STYLE_TAIL["normal"])
    subject = _subject(req)
    extra = _LATE_PRONE_EXTRA if pref.late_prone else 0
    used: List[str] = ["default_reminder_minutes", "notification_style"]

    reminders: List[ReminderItem] = []

    default_minutes = max(0, pref.default_reminder_minutes) + extra
    reminders.append(ReminderItem(
        type="default",
        minutes_before=default_minutes,
        message=f"{default_minutes}분 뒤 {subject}이(가) 있어요. {tail}",
    ))

    # departure reminder only when we can estimate travel time
    if req.travel_minutes is not None and req.travel_minutes >= 0 and req.start_time:
        used.append("departure_buffer_minutes")
        dep_minutes = req.travel_minutes + max(0, pref.departure_buffer_minutes) + extra
        reminders.append(ReminderItem(
            type="departure",
            minutes_before=dep_minutes,
            message=f"이동 시간을 고려하면 {subject} {dep_minutes}분 전부터 준비하면 좋아요. {tail}",
        ))

    if pref.late_prone:
        used.append("late_prone")

    meta.used_preferences = used
    if meta.personalization_applied:
        meta.reason = "기본 알림 시간과 출발 버퍼, 지각 경향을 반영했습니다."
    return ReminderRecommendData(reminders=reminders, personalization=meta)
