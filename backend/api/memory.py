"""Personal memory / user-preference endpoints (rule-based MVP).

Additive endpoints under /api/v1/memory. Backed by user_memories. Common
envelope preserved. GET returns defaults for unknown users (no write);
writes auto-create the user row.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.response import success_response
from backend.database.schema.memory_schema import (
    MemoryUpsert,
    PlaceCreate,
    PreferencesPatch,
)
from backend.database.session import get_db
from backend.services import memory_service as service

router = APIRouter(tags=["memory"])


@router.get("/memory/{user_id}", summary="사용자 메모리/선호 조회 (없으면 기본값)")
def get_memory(user_id: str, db: Session = Depends(get_db)):
    data = service.get_memory(db, user_id)
    return success_response(message="사용자 메모리입니다.", data=data.model_dump())


@router.get("/memory/{user_id}/context", summary="alert/reservation용 사용자 context")
def get_memory_context(user_id: str, db: Session = Depends(get_db)):
    return success_response(message="사용자 context입니다.", data=service.get_user_context(db, user_id))


@router.put("/memory/{user_id}", summary="사용자 메모리 upsert")
def put_memory(user_id: str, payload: MemoryUpsert, db: Session = Depends(get_db)):
    try:
        data = service.upsert_memory(db, user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return success_response(message="사용자 메모리를 저장했습니다.", data=data.model_dump())


@router.patch("/memory/{user_id}/preferences", summary="알림 성향/이동·여유시간 등 수정")
def patch_preferences(user_id: str, payload: PreferencesPatch, db: Session = Depends(get_db)):
    try:
        data = service.patch_preferences(db, user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return success_response(message="선호 설정을 수정했습니다.", data=data.model_dump())


@router.post("/memory/{user_id}/places", summary="자주 가는 장소 추가")
def add_place(user_id: str, payload: PlaceCreate, db: Session = Depends(get_db)):
    data = service.add_place(db, user_id, payload)
    return success_response(message="장소를 추가했습니다.", data=data.model_dump())
