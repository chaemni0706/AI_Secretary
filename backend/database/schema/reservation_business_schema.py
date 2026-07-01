"""Virtual-business reservation schemas (/api/v1/reservations, business layer).

A mock-business layer that sits ON TOP of the existing rule-based recommender
(``services/reservation_recommender.py``). These are intentionally NAMED with a
``Business`` prefix so they never collide with the pre-existing
``ReservationCandidateRequest`` / ``ReservationCandidateResponse`` in
``reservation_schema.py`` (which back the locked /reservations/candidates
contract). All date values are 'YYYY-MM-DD', all times 'HH:mm'.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.database.schema.personalization_schema import Personalization

# Preferred time-of-day windows. "any" == the business' full operating hours.
TimePreference = Literal["morning", "afternoon", "evening", "any"]


class ReservedSlot(BaseModel):
    """An already-booked interval at a business, on a specific date."""

    date: str = Field(..., description="'YYYY-MM-DD'")
    start_time: str = Field(..., description="'HH:mm'")
    end_time: str = Field(..., description="'HH:mm'")


class VirtualBusiness(BaseModel):
    """A mock business (no external API). Seeded from rules/virtual_businesses.json."""

    business_id: str
    name: str
    category: str
    address: Optional[str] = None
    open_time: str = Field(..., description="'HH:mm'")
    close_time: str = Field(..., description="'HH:mm'")
    slot_interval_minutes: int = 30
    default_service_duration_minutes: int = 60
    closed_days: List[str] = Field(
        default_factory=list, description="휴무 요일: MON, TUE, WED, THU, FRI, SAT, SUN"
    )
    reserved_slots: List[ReservedSlot] = Field(default_factory=list)


class BusinessCandidateRequest(BaseModel):
    """Body for POST /reservations/business-candidates."""

    user_id: str = "local-user"
    category: str = Field(..., description="hair | hospital | nail | restaurant | studyroom | pt ...")
    date: str = Field(..., description="'YYYY-MM-DD'")
    time_preference: TimePreference = "any"
    duration_minutes: Optional[int] = Field(
        None, description="미지정 시 업체 default_service_duration_minutes 사용"
    )
    business_id: Optional[str] = Field(
        None, description="특정 업체만 대상으로 하고 싶을 때 (선택)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "local-user",
                "category": "hair",
                "date": "2026-07-03",
                "time_preference": "evening",
                "duration_minutes": 60,
            }
        }
    )


class BusinessCandidate(BaseModel):
    """A single recommended, conflict-free reservation slot at a business."""

    business_id: str
    business_name: str
    category: str
    date: str
    start_time: str
    end_time: str
    reason: str
    personalization_score: Optional[float] = Field(
        None, description="개인 선호 반영 점수 0.0~1.0 (optional)"
    )


class BusinessAlternative(BaseModel):
    """A fallback suggestion when no candidate matches the request."""

    date: str
    time_preference: TimePreference
    reason: str


class BusinessCandidateData(BaseModel):
    """``data`` payload for the business-candidate endpoint."""

    requested: BusinessCandidateRequest
    candidates: List[BusinessCandidate] = Field(default_factory=list)
    alternatives: List[BusinessAlternative] = Field(default_factory=list)
    personalization: Optional[Personalization] = None


class BusinessCandidateResponse(BaseModel):
    """Envelope-shaped model (mirrors core.response.ApiResponse) for docs."""

    success: bool = True
    message: str = "OK"
    data: Optional[BusinessCandidateData] = None


class ReservationBookingRequest(BaseModel):
    """Body for POST /reservations/book — saves a chosen candidate as a local schedule."""

    user_id: str = "local-user"
    business_id: str
    business_name: str
    category: Optional[str] = None
    date: str = Field(..., description="'YYYY-MM-DD'")
    start_time: str = Field(..., description="'HH:mm'")
    end_time: str = Field(..., description="'HH:mm'")
    memo: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "local-user",
                "business_id": "hair_001",
                "business_name": "챔니 헤어살롱",
                "category": "hair",
                "date": "2026-07-03",
                "start_time": "18:00",
                "end_time": "19:00",
                "memo": "예약 후보 추천에서 선택한 일정",
            }
        }
    )


class ReservationBookingResponse(BaseModel):
    """Envelope-shaped model for docs; ``data.schedule`` is the saved ScheduleRead."""

    success: bool = True
    message: str = "OK"
    data: Optional[dict] = None
