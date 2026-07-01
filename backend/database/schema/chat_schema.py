"""Empathy chat schemas (/api/v1/chat).

Adds an emotion-aware empathy response layer on top of the existing AI-secretary
chatbot. Response stays inside the common {success, message, data} envelope;
`data` is `ChatRespondData`. No fields are removed from or added to any existing
schema — this is a brand-new, additive schema module.

This is a life-coaching aid, NOT a medical diagnosis. Every actionable
suggestion carries `requires_user_confirmation = true`; the assistant never
changes the user's schedule automatically.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ScheduleEvent(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = Field(None, description="low | medium | high")
    start_time: str = Field(..., description="ISO 8601, e.g. '2026-06-30T14:00:00'")
    end_time: str = Field(..., description="ISO 8601")
    is_fixed: bool = False


class ScheduleContext(BaseModel):
    current_time: Optional[str] = Field(None, description="ISO 8601")
    today_schedule: List[ScheduleEvent] = Field(default_factory=list)


class UserProfile(BaseModel):
    preferred_activity: List[str] = Field(default_factory=list)
    favorite_foods: List[str] = Field(default_factory=list)
    preferred_time_blocks: List[str] = Field(
        default_factory=list, description="morning | afternoon | evening | late_night"
    )
    preferred_study_hours: List[int] = Field(default_factory=list)


class ChatRespondRequest(BaseModel):
    user_id: Optional[int] = None
    message: str = Field(..., description="사용자 발화")
    target_event_id: Optional[str] = Field(
        None, description="일정 조정 시 조정 대상 이벤트 id (선택)"
    )
    schedule_context: Optional[ScheduleContext] = None
    user_profile: Optional[UserProfile] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": 1,
                "message": "일정이 너무 많아서 어떻게 해야 할지 모르겠어",
                "schedule_context": {
                    "current_time": "2026-06-30T15:00:00",
                    "today_schedule": [
                        {
                            "id": "event-1",
                            "title": "팀 회의",
                            "category": "meeting",
                            "priority": "high",
                            "start_time": "2026-06-30T14:00:00",
                            "end_time": "2026-06-30T15:00:00",
                            "is_fixed": True,
                        },
                        {
                            "id": "event-2",
                            "title": "과제 정리",
                            "category": "study",
                            "priority": "medium",
                            "start_time": "2026-06-30T17:00:00",
                            "end_time": "2026-06-30T18:00:00",
                            "is_fixed": False,
                        },
                    ],
                },
                "user_profile": {
                    "preferred_activity": ["산책", "조용한 카페"],
                    "favorite_foods": ["디저트"],
                    "preferred_time_blocks": ["afternoon"],
                    "preferred_study_hours": [14, 15, 16],
                },
            }
        }
    )


class Solution(BaseModel):
    category: str
    solution_type: str
    title: str
    reason: str
    action_buttons: List[str] = Field(default_factory=list)
    requires_user_confirmation: bool = True


class RescheduleCandidate(BaseModel):
    category: str = "schedule_adjustment"
    solution_type: str = "reschedule_low_priority"
    title: str
    reason: str
    score: float = Field(..., description="0.0 ~ 1.0")
    model_basis: Dict[str, Any] = Field(default_factory=dict)
    action_buttons: List[str] = Field(default_factory=list)
    requires_user_confirmation: bool = True


class ChatRespondData(BaseModel):
    selected_intent: str
    selected_strategy: str
    selected_solution_category: Optional[str] = None
    intent_scores: Dict[str, float] = Field(default_factory=dict)
    empathy_scores: Dict[str, float] = Field(default_factory=dict)
    matched_keywords: Dict[str, List[str]] = Field(default_factory=dict)
    solutions: List[Solution] = Field(default_factory=list)
    reschedule_candidates: List[RescheduleCandidate] = Field(default_factory=list)
    answer: str
    requires_user_confirmation: bool = True


class ChatRespondResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[ChatRespondData] = None
