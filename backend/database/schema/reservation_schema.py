"""Reservation candidate recommendation schemas (/api/v1/reservations)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReservationConstraints(BaseModel):
    target_date: str = Field(..., description="'YYYY-MM-DD'")
    preferred_start_time: str = Field(..., description="'HH:mm'")
    preferred_end_time: str = Field(..., description="'HH:mm'")
    duration_minutes: int = 60
    category: Optional[str] = None


class ExistingSchedule(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    date: str = Field(..., description="'YYYY-MM-DD'")
    start_time: str = Field(..., description="'HH:mm'")
    end_time: str = Field(..., description="'HH:mm'")


class RecommendedCandidate(BaseModel):
    candidate_id: str
    start_time: str
    end_time: str
    score: int = Field(..., description="0 ~ 100, higher is better")
    reason: str
    conflict: bool = False


class RejectedSlot(BaseModel):
    start_time: str
    end_time: str
    reason: str


class ReservationCandidateRequest(BaseModel):
    input: Optional[str] = Field(None, description="Original user utterance (optional)")
    current_datetime: Optional[str] = Field(None, description="ISO 8601")
    constraints: ReservationConstraints
    existing_schedules: List[ExistingSchedule] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "input": "이번 주 금요일 저녁에 미용실 갈 수 있는 시간 찾아줘",
                "current_datetime": "2026-06-29T10:00:00+09:00",
                "constraints": {
                    "target_date": "2026-07-03",
                    "preferred_start_time": "18:00",
                    "preferred_end_time": "21:00",
                    "duration_minutes": 60,
                    "category": "beauty",
                },
                "existing_schedules": [
                    {"id": "sch_101", "title": "팀플 회의", "date": "2026-07-03",
                     "start_time": "18:00", "end_time": "19:00"},
                    {"id": "sch_102", "title": "저녁 약속", "date": "2026-07-03",
                     "start_time": "20:00", "end_time": "21:00"},
                ],
            }
        }
    )


class ReservationCandidateData(BaseModel):
    target_date: str
    recommended_candidates: List[RecommendedCandidate] = Field(default_factory=list)
    rejected_slots: List[RejectedSlot] = Field(default_factory=list)


class ReservationCandidateResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[ReservationCandidateData] = None


class ReservationFromStoreRequest(BaseModel):
    """Recommend candidates using the user's SAVED schedules as busy intervals."""
    target_date: str = Field(..., description="'YYYY-MM-DD'")
    duration_minutes: int = 60
    preferred_start_time: str = Field("09:00", description="'HH:mm' 창 시작")
    preferred_end_time: str = Field("21:00", description="'HH:mm' 창 끝")
    category: Optional[str] = None
    user_id: Optional[str] = Field(None, description="선호(메모리) 조회용")
    apply_preference_buffer: bool = Field(
        False, description="True면 user 메모리의 default_buffer_minutes만큼 기존 일정 앞뒤를 비움"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_date": "2026-07-03",
                "duration_minutes": 60,
                "preferred_start_time": "13:00",
                "preferred_end_time": "18:00",
                "category": "beauty",
                "user_id": "local-user",
                "apply_preference_buffer": False,
            }
        }
    )
