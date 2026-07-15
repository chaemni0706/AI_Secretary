"""Local Schedule (EVENT) CRUD endpoints.

Additive endpoints under /api/v1/local/schedules backed by the planner_items +
event_details tables. The existing AI parse endpoint (/ai/schedule/parse) is
untouched. Common envelope {success, message, data} is preserved.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.response import success_response
from backend.database import repository as repo
from backend.database.schema.local_schedule_schema import (
    ScheduleCreate,
    ScheduleFromDraftRequest,
    ScheduleUpdate,
)
from backend.database.session import get_db
from backend.services import local_schedule_service as service

router = APIRouter(tags=["local-schedule"])


@router.post("/local/schedules", summary="로컬 일정 생성")
def create_schedule(payload: ScheduleCreate, db: Session = Depends(get_db)):
    user_id, calendar_id = repo.ensure_default_owner(db)
    try:
        data = service.create_schedule(db, payload, user_id=user_id, calendar_id=calendar_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=422, detail="유효하지 않은 일정 데이터입니다. 종료 시각은 시작 시각보다 뒤여야 합니다.")
    return success_response(message="일정을 생성했습니다.", data=data.model_dump())


@router.post("/local/schedules/from-draft", summary="parse 결과(schedule_draft)로 일정 저장")
def create_schedule_from_draft(req: ScheduleFromDraftRequest, db: Session = Depends(get_db)):
    user_id, calendar_id = repo.ensure_default_owner(db)
    try:
        data = service.create_schedule_from_draft(
            db, req.schedule_draft, user_id=user_id, calendar_id=calendar_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=422, detail="유효하지 않은 일정 데이터입니다. 종료 시각은 시작 시각보다 뒤여야 합니다.")
    return success_response(message="draft로부터 일정을 저장했습니다.", data=data.model_dump())


@router.get("/local/schedules", summary="로컬 일정 목록 조회")
def list_schedules(
    db: Session = Depends(get_db),
    date: Optional[str] = Query(None, description="'YYYY-MM-DD'"),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None, description="low | medium | high"),
    status: Optional[str] = Query(None, description="draft | scheduled | ..."),
):
    items = service.list_schedules(db, user_id=repo.DEFAULT_USER_ID)

    def keep(s) -> bool:
        if date and s.date != date:
            return False
        if category and s.category != category:
            return False
        if priority and s.priority != priority:
            return False
        if status and s.status != status:
            return False
        return True

    items = [s for s in items if keep(s)]
    items.sort(key=lambda s: (s.date or "", s.start_time or ""))  # date asc, start asc
    return success_response(message="일정 목록입니다.", data=[s.model_dump() for s in items])


@router.get("/local/schedules/{schedule_id}", summary="로컬 일정 단건 조회")
def get_schedule(schedule_id: str, db: Session = Depends(get_db)):
    data = service.get_schedule(db, schedule_id)
    if data is None:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
    return success_response(message="일정 단건입니다.", data=data.model_dump())


@router.patch("/local/schedules/{schedule_id}", summary="로컬 일정 수정")
def update_schedule(schedule_id: str, payload: ScheduleUpdate, db: Session = Depends(get_db)):
    try:
        data = service.update_schedule(db, schedule_id, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=422, detail="유효하지 않은 일정 데이터입니다. 종료 시각은 시작 시각보다 뒤여야 합니다.")
    if data is None:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
    return success_response(message="일정을 수정했습니다.", data=data.model_dump())


@router.delete("/local/schedules/{schedule_id}", summary="로컬 일정 삭제")
def delete_schedule(schedule_id: str, db: Session = Depends(get_db)):
    ok = service.delete_schedule(db, schedule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
    return success_response(message="일정을 삭제했습니다.", data={"id": schedule_id, "deleted": True})
