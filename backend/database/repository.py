"""Data-access layer for planner_items + event_details / todo_details.

Pure persistence helpers operating on a passed-in SQLAlchemy ``Session``. They
``flush`` (so FK/triggers see prior rows in the same transaction) but do NOT
``commit`` — the service layer owns the transaction boundary. All values here
are already in SQL form (UPPERCASE enums, ISO datetimes); casing/format
translation lives in ``planner_mapping`` / the service layer.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import (
    Calendar, EventDetail, PlannerItem, TodoDetail, User, UserMemory,
)
from backend.services.planner_mapping import now_iso


# --- planner_items ----------------------------------------------------------
def create_planner_item(
    db: Session, *, item_id: str, user_id: str, item_type: str, title: str,
    description: Optional[str] = None, category: Optional[str] = None,
    status: str = "SCHEDULED", priority: str = "MEDIUM",
    source_type: str = "MANUAL", sort_at: Optional[str] = None,
    created_at: Optional[str] = None, updated_at: Optional[str] = None,
) -> PlannerItem:
    ts = created_at or now_iso()
    item = PlannerItem(
        item_id=item_id, user_id=user_id, item_type=item_type, title=title,
        description=description, category=category, status=status,
        priority=priority, source_type=source_type, sort_at=sort_at,
        created_at=ts, updated_at=updated_at or ts,
    )
    db.add(item)
    db.flush()
    return item


def get_planner_item(
    db: Session, item_id: str, *, include_deleted: bool = False
) -> Optional[PlannerItem]:
    item = db.get(PlannerItem, item_id)
    if item is None:
        return None
    if not include_deleted and item.deleted_at is not None:
        return None
    return item


def list_planner_items(
    db: Session, *, user_id: str, item_type: Optional[str] = None,
    include_deleted: bool = False,
) -> List[PlannerItem]:
    stmt = select(PlannerItem).where(PlannerItem.user_id == user_id)
    if item_type is not None:
        stmt = stmt.where(PlannerItem.item_type == item_type)
    if not include_deleted:
        stmt = stmt.where(PlannerItem.deleted_at.is_(None))
    stmt = stmt.order_by(PlannerItem.created_at, PlannerItem.item_id)
    return list(db.execute(stmt).scalars().all())


def update_planner_item(db: Session, item_id: str, **fields) -> Optional[PlannerItem]:
    item = get_planner_item(db, item_id)
    if item is None:
        return None
    for key, value in fields.items():
        if value is not None and hasattr(item, key):
            setattr(item, key, value)
    item.updated_at = now_iso()
    db.flush()
    return item


def soft_delete_planner_item(db: Session, item_id: str) -> bool:
    item = get_planner_item(db, item_id)
    if item is None:
        return False
    ts = now_iso()
    item.deleted_at = ts
    item.updated_at = ts
    db.flush()
    return True


def update_status(db: Session, item_id: str, status: str) -> Optional[PlannerItem]:
    return update_planner_item(db, item_id, status=status)


# --- event_details ----------------------------------------------------------
def create_event_detail(
    db: Session, *, item_id: str, calendar_id: str, start_at: str,
    end_at: Optional[str] = None, is_all_day: int = 0,
    location_text: Optional[str] = None, travel_time_minutes: Optional[int] = None,
    external_event_id: Optional[str] = None,
) -> EventDetail:
    detail = EventDetail(
        item_id=item_id, calendar_id=calendar_id, start_at=start_at,
        end_at=end_at, is_all_day=is_all_day, location_text=location_text,
        travel_time_minutes=travel_time_minutes, external_event_id=external_event_id,
    )
    db.add(detail)
    db.flush()
    return detail


def update_event_detail(db: Session, item_id: str, **fields) -> Optional[EventDetail]:
    detail = db.get(EventDetail, item_id)
    if detail is None:
        return None
    for key, value in fields.items():
        if value is not None and hasattr(detail, key):
            setattr(detail, key, value)
    db.flush()
    return detail


def list_events_by_date(db: Session, *, user_id: str, date: str) -> List[PlannerItem]:
    stmt = (
        select(PlannerItem)
        .join(EventDetail, EventDetail.item_id == PlannerItem.item_id)
        .where(
            PlannerItem.user_id == user_id,
            PlannerItem.item_type == "EVENT",
            PlannerItem.deleted_at.is_(None),
            EventDetail.start_at.like(f"{date}%"),
        )
        .order_by(EventDetail.start_at)
    )
    return list(db.execute(stmt).scalars().all())


# --- todo_details -----------------------------------------------------------
def create_todo_detail(
    db: Session, *, item_id: str, due_at: Optional[str] = None,
    planned_date: Optional[str] = None, estimated_minutes: Optional[int] = None,
    started_at: Optional[str] = None, completed_at: Optional[str] = None,
) -> TodoDetail:
    detail = TodoDetail(
        item_id=item_id, due_at=due_at, planned_date=planned_date,
        estimated_minutes=estimated_minutes, started_at=started_at,
        completed_at=completed_at,
    )
    db.add(detail)
    db.flush()
    return detail


def update_todo_detail(db: Session, item_id: str, **fields) -> Optional[TodoDetail]:
    detail = db.get(TodoDetail, item_id)
    if detail is None:
        return None
    for key, value in fields.items():
        if value is not None and hasattr(detail, key):
            setattr(detail, key, value)
    db.flush()
    return detail


def list_todos_by_due_date(db: Session, *, user_id: str, due_date: str) -> List[PlannerItem]:
    stmt = (
        select(PlannerItem)
        .join(TodoDetail, TodoDetail.item_id == PlannerItem.item_id)
        .where(
            PlannerItem.user_id == user_id,
            PlannerItem.item_type == "TODO",
            PlannerItem.deleted_at.is_(None),
            TodoDetail.planned_date.like(f"{due_date}%"),
        )
        .order_by(PlannerItem.created_at)
    )
    return list(db.execute(stmt).scalars().all())


# --- default owner bootstrap (no auth yet) ----------------------------------
DEFAULT_USER_ID = "local-user"
DEFAULT_CALENDAR_ID = "local-primary"


def ensure_default_owner(db: Session) -> tuple[str, str]:
    """Idempotently ensure a default user + primary calendar exist, so EVENT
    creation (which has FKs to users/calendars) works before auth is added.
    Returns (user_id, calendar_id)."""
    if db.get(User, DEFAULT_USER_ID) is None:
        ts = now_iso()
        db.add(User(user_id=DEFAULT_USER_ID, display_name="Local User",
                    created_at=ts, updated_at=ts))
        db.commit()
    if db.get(Calendar, DEFAULT_CALENDAR_ID) is None:
        ts = now_iso()
        db.add(Calendar(calendar_id=DEFAULT_CALENDAR_ID, user_id=DEFAULT_USER_ID,
                        name="기본 캘린더", is_primary=1, created_at=ts, updated_at=ts))
        db.commit()
    return DEFAULT_USER_ID, DEFAULT_CALENDAR_ID


# --- users / user_memories (personal memory KV store) -----------------------
def ensure_user(db: Session, user_id: str) -> str:
    """Create a minimal users row if missing (FK parent for memories)."""
    if db.get(User, user_id) is None:
        ts = now_iso()
        db.add(User(user_id=user_id, display_name=user_id, created_at=ts, updated_at=ts))
        db.commit()
    return user_id


def get_active_memories(db: Session, user_id: str) -> List[UserMemory]:
    stmt = select(UserMemory).where(
        UserMemory.user_id == user_id, UserMemory.is_active == 1
    )
    return list(db.execute(stmt).scalars().all())


def upsert_memory(
    db: Session, *, user_id: str, memory_type: str, memory_key: str, value: str
) -> UserMemory:
    """Insert or update the active memory row for (user_id, memory_key)."""
    stmt = select(UserMemory).where(
        UserMemory.user_id == user_id,
        UserMemory.memory_key == memory_key,
        UserMemory.is_active == 1,
    )
    row = db.execute(stmt).scalars().first()
    ts = now_iso()
    if row is None:
        row = UserMemory(
            memory_id=uuid.uuid4().hex, user_id=user_id, memory_type=memory_type,
            memory_key=memory_key, memory_value_masked=value, is_active=1,
            created_at=ts, updated_at=ts,
        )
        db.add(row)
    else:
        row.memory_type = memory_type
        row.memory_value_masked = value
        row.updated_at = ts
    db.flush()
    return row
