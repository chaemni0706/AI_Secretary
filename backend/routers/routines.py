"""복약 루틴 저장/조회 API."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.response import success_response
from backend.services import routine_service

router = APIRouter(prefix="/api/v1/routines", tags=["routines"])


class MedicineRoutineInput(BaseModel):
    medicine_name: str
    dose: Optional[str] = ""
    frequency_per_day: Optional[int] = None
    duration_days: Optional[int] = None


class MedicineRoutineCreateRequest(BaseModel):
    medicines: List[MedicineRoutineInput]
    start_date: str


@router.post("/medicine")
def create_medicine_routines(request: MedicineRoutineCreateRequest):
    medicines = [m.model_dump() for m in request.medicines]
    try:
        routines = routine_service.create_medicine_routines(medicines, request.start_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return success_response(
        message="복약 루틴이 추가되었습니다.",
        data={
            "routine_count": len(routines),
            "routines": routines,
        },
    )


@router.get("/medicine")
def get_medicine_routines():
    return success_response(
        message="복약 루틴 목록입니다.",
        data={"routines": routine_service.get_all_routines()},
    )
