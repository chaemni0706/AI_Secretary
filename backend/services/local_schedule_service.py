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
        end_date=pm.date_from_dt(ev.end_at) if ev and ev.end_at else None,
        category=item.category,
        priority=pm.priority_from_db(item.priority),
        location=ev.location_text if ev else None,
        memo=item.description,
        status=pm.status_from_db(item.status),
        source=pm.source_from_db(item.source_type),
        is_all_day=bool(ev.is_all_day) if ev else False,
        travel_time_minutes=ev.travel_time_minutes if ev else None,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def create_schedule(
    db: Session, payload: ScheduleCreate, *, user_id: str, calendar_id: str
) -> ScheduleRead:
    item_id = uuid.uuid4().hex
    # 하루 종일: is_all_day 플래그가 켜졌거나 start_time 이 없으면 all-day 로 저장하고
    # start_at 은 00:00 으로 채운다(event_details.start_at 은 NOT NULL).
    is_all_day = 1 if (payload.is_all_day or payload.start_time is None) else 0
    start_time = payload.start_time or "00:00"
    # 하루 종일 다일 일정(예: 여행 7/15~7/17)도 종료일이 저장되도록, all-day 면
    # end_time 이 없어도 종료일의 23:59 로 채운다(안 그러면 end_time 이 없어 end_at
    # 자체가 저장되지 않아 종료일이 사라진다).
    end_time = "23:59" if is_all_day else payload.end_time
    item = repo.create_planner_item(
        db, item_id=item_id, user_id=user_id, item_type="EVENT",
        title=payload.title, description=payload.memo, category=payload.category,
        status="SCHEDULED", priority=pm.priority_to_db(payload.priority),
        source_type=pm.source_to_db(payload.source),
    )
    repo.create_event_detail(
        db, item_id=item_id, calendar_id=calendar_id,
        start_at=pm.combine_date_time(payload.date, start_time),
        end_at=pm.combine_date_time(payload.end_date or payload.date, end_time),
        is_all_day=is_all_day,
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
        old_start_date = pm.date_from_dt(ev.start_at)
        old_end_date = pm.date_from_dt(ev.end_at) if ev.end_at else None
        new_start_date = payload.date or old_start_date

        if payload.end_date is not None:
            target_end_date = payload.end_date
        elif payload.date is not None:
            # 시작일이 옮겨진 경우: 종료일이 원래 시작일과 같았던(=하루짜리) 일정은
            # 새 시작일을 따라가고, 여러 날짜에 걸친 일정은 종료일을 그대로 둔다.
            target_end_date = (
                new_start_date
                if old_end_date is None or old_end_date == old_start_date
                else old_end_date
            )
        else:
            target_end_date = old_end_date

        if payload.start_time is not None:
            ev.start_at = pm.combine_date_time(new_start_date, payload.start_time)
        elif payload.date is not None:
            ev.start_at = pm.combine_date_time(new_start_date, pm.time_from_dt(ev.start_at))
        is_all_day = (
            payload.is_all_day if payload.is_all_day is not None else bool(ev.is_all_day)
        )
        if payload.end_time is not None:
            ev.end_at = pm.combine_date_time(target_end_date, payload.end_time)
        elif payload.end_date is not None and ev.end_at is None and is_all_day:
            # 하루 종일 일정에 처음으로 종료일이 지정된 경우: end_time 없이도
            # 종료일의 23:59 로 채워야 종료일이 저장된다(create_schedule 과 동일한 규칙).
            ev.end_at = pm.combine_date_time(target_end_date, "23:59")
        elif (payload.end_date is not None or payload.date is not None) and ev.end_at:
            # 시작일/종료일이 옮겨졌지만 end_time 은 그대로: end_at 의 날짜만 갱신
            # (안 그러면 end_at 이 옛 날짜에 남아 end_at>start_at 제약이 깨질 수 있음)
            ev.end_at = pm.combine_date_time(target_end_date, pm.time_from_dt(ev.end_at))
        if payload.location is not None:
            ev.location_text = payload.location
        if payload.is_all_day is not None:
            ev.is_all_day = 1 if payload.is_all_day else 0
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
