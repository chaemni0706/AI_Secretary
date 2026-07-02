"""Local To-do (TODO) CRUD endpoints.

Additive endpoints under /api/v1/local/todos backed by planner_items +
todo_details. Common envelope preserved.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.response import success_response
from backend.database import repository as repo
from backend.database.schema.todo_schema import TodoCreate, TodoFromDraftRequest, TodoUpdate
from backend.database.session import get_db
from backend.services import todo_service as service

router = APIRouter(tags=["local-todo"])

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


@router.post("/local/todos", summary="로컬 To-do 생성")
def create_todo(payload: TodoCreate, db: Session = Depends(get_db)):
    user_id, _ = repo.ensure_default_owner(db)
    try:
        data = service.create_todo(db, payload, user_id=user_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=422, detail="유효하지 않은 To-do 데이터입니다.")
    return success_response(message="To-do를 생성했습니다.", data=data.model_dump())


@router.post("/local/todos/from-draft", summary="parse 결과(draft)로 To-do 저장")
def create_todo_from_draft(req: TodoFromDraftRequest, db: Session = Depends(get_db)):
    user_id, _ = repo.ensure_default_owner(db)
    try:
        data = service.create_todo_from_draft(db, req.schedule_draft, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=422, detail="유효하지 않은 To-do 데이터입니다.")
    return success_response(message="draft로부터 To-do를 저장했습니다.", data=data.model_dump())


@router.get("/local/todos", summary="로컬 To-do 목록 조회")
def list_todos(
    db: Session = Depends(get_db),
    due_date: Optional[str] = Query(None, description="'YYYY-MM-DD'"),
    completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None, description="low | medium | high"),
    category: Optional[str] = Query(None),
):
    items = service.list_todos(db, user_id=repo.DEFAULT_USER_ID)

    def keep(t) -> bool:
        if due_date and t.due_date != due_date:
            return False
        if completed is not None and t.completed != completed:
            return False
        if priority and t.priority != priority:
            return False
        if category and t.category != category:
            return False
        return True

    items = [t for t in items if keep(t)]
    # not-completed first, then high>medium>low, then earliest due_date
    items.sort(key=lambda t: (
        t.completed,
        _PRIORITY_RANK.get(t.priority, 1),
        t.due_date or "9999-99-99",
    ))
    return success_response(message="To-do 목록입니다.", data=[t.model_dump() for t in items])


@router.get("/local/todos/{todo_id}", summary="로컬 To-do 단건 조회")
def get_todo(todo_id: str, db: Session = Depends(get_db)):
    data = service.get_todo(db, todo_id)
    if data is None:
        raise HTTPException(status_code=404, detail="To-do를 찾을 수 없습니다.")
    return success_response(message="To-do 단건입니다.", data=data.model_dump())


@router.patch("/local/todos/{todo_id}", summary="로컬 To-do 수정")
def update_todo(todo_id: str, payload: TodoUpdate, db: Session = Depends(get_db)):
    try:
        data = service.update_todo(db, todo_id, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=422, detail="유효하지 않은 To-do 데이터입니다.")
    if data is None:
        raise HTTPException(status_code=404, detail="To-do를 찾을 수 없습니다.")
    return success_response(message="To-do를 수정했습니다.", data=data.model_dump())


@router.delete("/local/todos/{todo_id}", summary="로컬 To-do 삭제")
def delete_todo(todo_id: str, db: Session = Depends(get_db)):
    ok = service.delete_todo(db, todo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="To-do를 찾을 수 없습니다.")
    return success_response(message="To-do를 삭제했습니다.", data={"id": todo_id, "deleted": True})
