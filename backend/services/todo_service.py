"""To-do (TODO) domain service: orchestrates repository + mapping.

`completed` is represented by the planner status COMPLETED plus a
todo_details.completed_at timestamp.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.database import repository as repo
from backend.database.models import TodoDetail
from backend.database.schema.todo_schema import TodoCreate, TodoRead, TodoUpdate
from backend.database.schema.local_schedule_schema import ScheduleDraftInput
from backend.services import planner_mapping as pm


def _to_read(item) -> TodoRead:
    td = item.todo_detail
    return TodoRead(
        id=item.item_id,
        title=item.title,
        due_date=pm.date_from_dt(td.planned_date) if td and td.planned_date else None,
        priority=pm.priority_from_db(item.priority),
        completed=(item.status == "COMPLETED"),
        category=item.category,
        memo=item.description,
        status=pm.status_from_db(item.status),
        source=pm.source_from_db(item.source_type),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def create_todo(db: Session, payload: TodoCreate, *, user_id: str) -> TodoRead:
    item_id = uuid.uuid4().hex
    status = "COMPLETED" if payload.completed else "SCHEDULED"
    item = repo.create_planner_item(
        db, item_id=item_id, user_id=user_id, item_type="TODO",
        title=payload.title, description=payload.memo, category=payload.category,
        status=status, priority=pm.priority_to_db(payload.priority),
        source_type=pm.source_to_db(payload.source),
    )
    repo.create_todo_detail(
        db, item_id=item_id, planned_date=payload.due_date,
        completed_at=pm.now_iso() if payload.completed else None,
    )
    db.commit()
    db.refresh(item)
    return _to_read(item)


def get_todo(db: Session, item_id: str) -> Optional[TodoRead]:
    item = repo.get_planner_item(db, item_id)
    if item is None or item.item_type != "TODO":
        return None
    return _to_read(item)


def list_todos(db: Session, *, user_id: str) -> List[TodoRead]:
    items = repo.list_planner_items(db, user_id=user_id, item_type="TODO")
    return [_to_read(i) for i in items]


def update_todo(db: Session, item_id: str, payload: TodoUpdate) -> Optional[TodoRead]:
    item = repo.get_planner_item(db, item_id)
    if item is None or item.item_type != "TODO":
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
    if payload.source is not None:
        planner_updates["source_type"] = pm.source_to_db(payload.source)
    if payload.completed is not None:
        planner_updates["status"] = "COMPLETED" if payload.completed else "SCHEDULED"
    if planner_updates:
        repo.update_planner_item(db, item_id, **planner_updates)

    detail = db.get(TodoDetail, item_id)
    if detail is not None:
        if payload.completed is not None:
            # set on completion, explicitly clear on un-completion
            detail.completed_at = pm.now_iso() if payload.completed else None
        if payload.due_date is not None:
            detail.planned_date = payload.due_date
        db.flush()

    db.commit()
    db.refresh(item)
    return _to_read(item)


def delete_todo(db: Session, item_id: str) -> bool:
    item = repo.get_planner_item(db, item_id)
    if item is None or item.item_type != "TODO":
        return False
    ok = repo.soft_delete_planner_item(db, item_id)
    db.commit()
    return ok


def create_todo_from_draft(
    db: Session, draft: ScheduleDraftInput, *, user_id: str
) -> TodoRead:
    """Persist a parse draft as a TODO. Requires title; date maps to due_date
    (optional). Created as not-completed."""
    if not draft.title or not draft.title.strip():
        raise ValueError("title이 없어 To-do를 저장할 수 없습니다.")
    payload = TodoCreate(
        title=draft.title, due_date=draft.date, priority=draft.priority,
        completed=False, category=draft.category, memo=draft.memo,
        source=draft.source,
    )
    return create_todo(db, payload, user_id=user_id)
