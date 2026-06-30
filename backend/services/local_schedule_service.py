"""Schedule (EVENT) domain service: orchestrates repository + mapping.

Owns the transaction boundary (commit). Translates between the lowercase
date/time API model and the planner_items + event_details SQL rows.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.database import repository as repo
from backend.database.schema.local_schedule_schema import (
    ScheduleCreate,
    ScheduleDraftInput,
    ScheduleRead,
    ScheduleUpdate,
)
from backend.services import planner_mapping as pm


def _to_read(item) -> ScheduleRead:
    ev = item.event_detail
    return ScheduleRead(
        id=item.item_id,
        title=item.title,
        date=pm.date_from_dt(ev.start_at) if ev else None,
        start_time=pm.time_from_dt(ev.start_at) if ev else None,
        end_time=pm.time_from_dt(ev.end_at) if ev and ev.end_at else None,
        category=item.category,
        priority=pm.priority_from_db(item.priority),
        location=ev.location_text if ev else None,
        memo=item.description,
        status=pm.status_from_db(item.status),
        source=pm.source_from_db(item.source_type),
        travel_time_minutes=ev.travel_time_minutes if ev else None,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def create_schedule(
    db: Session, payload: ScheduleCreate, *, user_id: str, calendar_id: str
) -> ScheduleRead:
    item_id = uuid.uuid4().hex
    item = repo.create_planner_item(
        db, item_id=item_id, user_id=user_id, item_type="EVENT",
        title=payload.title, description=payload.memo, category=payload.category,
        status="SCHEDULED", priority=pm.priority_to_db(payload.priority),
        source_type=pm.source_to_db(payload.source),
    )
    repo.create_event_detail(
        db, item_id=item_id, calendar_id=calendar_id,
        start_at=pm.combine_date_time(payload.date, payload.start_time),
        end_at=pm.combine_date_time(payload.date, payload.end_time),
        location_text=payload.location,
        travel_time_minutes=payload.travel_time_minutes,
    )
    db.commit()
    db.refresh(item)
    return _to_read(item)


def get_schedule(db: Session, item_id: str) -> Optional[ScheduleRead]:
    item = repo.get_planner_item(db, item_id)
    if item is None or item.item_type != "EVENT":
        return None
    return _to_read(item)


def list_schedules(db: Session, *, user_id: str) -> List[ScheduleRead]:
    items = repo.list_planner_items(db, user_id=user_id, item_type="EVENT")
    return [_to_read(i) for i in items]


def update_schedule(
    db: Session, item_id: str, payload: ScheduleUpdate
) -> Optional[ScheduleRead]:
    item = repo.get_planner_item(db, item_id)
    if item is None or item.item_type != "EVENT":
        return None

    planner_updates = {}
    if payload.title is not None:
        planner_updates["title"] = payload.title
    if payload.memo is not None:
        planner_updates["description"] = payload.memo
    if payload.category is not None:
        planner_updates["category"] = payload.category
    if payload.priority is not None:
        planner_updates["priority"] = pm.priority_to_db(payload.priority)
    if payload.status is not None:
        planner_updates["status"] = pm.status_to_db(payload.status)
    if payload.source is not None:
        planner_updates["source_type"] = pm.source_to_db(payload.source)
    if planner_updates:
        repo.update_planner_item(db, item_id, **planner_updates)

    ev = item.event_detail
    if ev is not None:
        new_date = payload.date or pm.date_from_dt(ev.start_at)
        if payload.start_time is not None:
            ev.start_at = pm.combine_date_time(new_date, payload.start_time)
        elif payload.date is not None:
            ev.start_at = pm.combine_date_time(new_date, pm.time_from_dt(ev.start_at))
        if payload.end_time is not None:
            ev.end_at = pm.combine_date_time(new_date, payload.end_time)
        elif payload.date is not None and ev.end_at:
            # date moved but end_time untouched: keep end's time on the new date
            # (otherwise end_at would stay on the old date and break end_at>start_at)
            ev.end_at = pm.combine_date_time(new_date, pm.time_from_dt(ev.end_at))
        if payload.location is not None:
            ev.location_text = payload.location
        if payload.travel_time_minutes is not None:
            ev.travel_time_minutes = payload.travel_time_minutes
        db.flush()

    db.commit()
    db.refresh(item)
    return _to_read(item)


def delete_schedule(db: Session, item_id: str) -> bool:
    item = repo.get_planner_item(db, item_id)
    if item is None or item.item_type != "EVENT":
        return False
    ok = repo.soft_delete_planner_item(db, item_id)
    db.commit()
    return ok


def create_schedule_from_draft(
    db: Session, draft: ScheduleDraftInput, *, user_id: str, calendar_id: str
) -> ScheduleRead:
    """Persist a parse `schedule_draft` as an EVENT.

    Requires title + date. Missing start_time -> all-day event (start_at at
    00:00, is_all_day=1). Invalid time format raises ValueError (router -> 422).
    """
    if not draft.title or not draft.title.strip():
        raise ValueError("title이 없어 일정을 저장할 수 없습니다.")
    if not draft.date:
        raise ValueError("date가 없어 일정을 저장할 수 없습니다.")
    if draft.start_time is not None and not pm.valid_hhmm(draft.start_time):
        raise ValueError("start_time 포맷이 올바르지 않습니다 (HH:mm).")
    if draft.end_time is not None and not pm.valid_hhmm(draft.end_time):
        raise ValueError("end_time 포맷이 올바르지 않습니다 (HH:mm).")

    item_id = uuid.uuid4().hex
    is_all_day = 1 if draft.start_time is None else 0
    start_time = draft.start_time or "00:00"

    item = repo.create_planner_item(
        db, item_id=item_id, user_id=user_id, item_type="EVENT",
        title=draft.title, description=draft.memo, category=draft.category,
        status="SCHEDULED", priority=pm.priority_to_db(draft.priority),
        source_type=pm.source_to_db(draft.source),
    )
    repo.create_event_detail(
        db, item_id=item_id, calendar_id=calendar_id,
        start_at=pm.combine_date_time(draft.date, start_time),
        end_at=pm.combine_date_time(draft.date, draft.end_time),
        is_all_day=is_all_day, location_text=draft.location,
    )
    db.commit()
    db.refresh(item)
    return _to_read(item)
