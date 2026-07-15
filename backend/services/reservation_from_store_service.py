"""Recommend reservation candidates from SAVED schedules.

Reuses reservation_recommender.recommend_candidates unchanged. Pulls stored
EVENTs for the target date, converts them to existing_schedules (busy
intervals), optionally pads them by the user's preferred buffer, then defers to
the existing rule-based recommender. No external calendar.
"""

from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from backend.database import repository as repo
from backend.database.repository import DEFAULT_USER_ID
from backend.database.schema.reservation_schema import (
    ExistingSchedule,
    ReservationCandidateData,
    ReservationCandidateRequest,
    ReservationConstraints,
    ReservationFromStoreRequest,
)
from backend.services import memory_service
from backend.services import planner_mapping as pm
from backend.services.reservation_recommender import recommend_candidates

# statuses that must NOT count as busy (deleted rows already excluded by query)
_INACTIVE_STATUSES = {"CANCELLED", "DELETED"}


def _to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _to_hhmm(minutes: int) -> str:
    minutes = max(0, min(24 * 60 - 1, minutes))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _stored_busy(db: Session, date: str) -> List[ExistingSchedule]:
    """Stored EVENTs on `date` as busy intervals. Skips cancelled/deleted,
    all-day or end-less events, and rows with unparseable times."""
    busy: List[ExistingSchedule] = []
    for item in repo.list_events_by_date(db, user_id=DEFAULT_USER_ID, date=date):
        if (item.status or "").upper() in _INACTIVE_STATUSES:
            continue
        ev = item.event_detail
        if ev is None or not ev.start_at or not ev.end_at:
            continue
        start = pm.time_from_dt(ev.start_at)
        end = pm.time_from_dt(ev.end_at)
        if not pm.valid_hhmm(start) or not pm.valid_hhmm(end):
            continue
        busy.append(ExistingSchedule(
            id=item.item_id, title=item.title, date=date,
            start_time=start, end_time=end,
        ))
    return busy


def recommend_from_store(
    db: Session, req: ReservationFromStoreRequest
) -> ReservationCandidateData:
    busy = _stored_busy(db, req.target_date)

    # optional preference reflection: pad busy intervals by the user's buffer
    if req.apply_preference_buffer and req.user_id:
        buffer = memory_service.get_user_context(db, req.user_id)["default_buffer_minutes"]
        if buffer > 0:
            busy = [
                ExistingSchedule(
                    id=e.id, title=e.title, date=e.date,
                    start_time=_to_hhmm(_to_min(e.start_time) - buffer),
                    end_time=_to_hhmm(_to_min(e.end_time) + buffer),
                )
                for e in busy
            ]

    rc_req = ReservationCandidateRequest(
        constraints=ReservationConstraints(
            target_date=req.target_date,
            preferred_start_time=req.preferred_start_time,
            preferred_end_time=req.preferred_end_time,
            duration_minutes=req.duration_minutes,
            category=req.category,
        ),
        existing_schedules=busy,
    )
    return recommend_candidates(rc_req)
