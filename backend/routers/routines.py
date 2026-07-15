"""복약 루틴 저장/조회 API."""

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.services import routine_service

router = APIRouter(prefix="/api/v1/routines", tags=["routines"])


class MedicineCategoryInput(BaseModel):
    dose_amount: Optional[float] = None
    dose_unit: Optional[str] = None
    frequency_per_day: Optional[int] = None
    duration_days: Optional[int] = None
    normalized_text: Optional[str] = ""


class MedicineRoutineInput(BaseModel):
    medicine_name: str
    category: MedicineCategoryInput


class MedicineRoutineCreateRequest(BaseModel):
    medicines: List[MedicineRoutineInput]
    start_date: str


@router.post("/medicine")
def create_medicine_routines(request: MedicineRoutineCreateRequest):
    medicines = [m.model_dump() for m in request.medicines]
    routines = routine_service.create_medicine_routines(medicines, request.start_date)

    return {
        "message": "복약 루틴이 추가되었습니다.",
        "routine_count": len(routines),
        "routines": routines,
    }


@router.get("/medicine")
def get_medicine_routines():
    return {"routines": routine_service.get_all_routines()}
