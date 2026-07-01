"""Candidate -> reservation-message schemas (/api/v1/reservations/message).

Connects a chosen reservation CANDIDATE to the EXISTING template+LLM message
generator. Draft-only: NO external send, NO booking. All additive; the original
/messages/reservation contract is untouched.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.database.schema.message_schema import MessageStyle

ActionType = Literal["inquiry", "confirm", "change", "cancel", "check"]


class CandidateInput(BaseModel):
    """Lenient echo of a recommended candidate (fields validated in the service
    so missing ones return a friendly missing_fields payload, not a 422 parse
    error)."""
    business_id: Optional[str] = None
    business_name: Optional[str] = None
    category: Optional[str] = None
    date: Optional[str] = Field(None, description="'YYYY-MM-DD'")
    start_time: Optional[str] = Field(None, description="'HH:mm'")
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    party_size: Optional[int] = Field(None, description="식당 인원 수(선택)")

    model_config = ConfigDict(extra="ignore")


class FromCandidateRequest(BaseModel):
    user_id: str = "local-user"
    candidate: CandidateInput
    action_type: ActionType = "inquiry"
    service_name: Optional[str] = Field(None, description="커트/네일/진료 등 서비스명(선택)")
    request_note: Optional[str] = Field(None, description="추가 요청사항(선택)")
    party_size: Optional[int] = Field(None, description="식당 인원 수(선택; candidate에도 넣을 수 있음)")
    style: MessageStyle = Field(default_factory=MessageStyle)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "local-user",
                "candidate": {
                    "business_id": "hair_001", "business_name": "챔니 헤어살롱",
                    "category": "hair", "date": "2026-07-03",
                    "start_time": "18:00", "end_time": "19:00", "duration_minutes": 60,
                },
                "action_type": "inquiry",
                "service_name": "커트 또는 시술",
                "request_note": "예약 가능한지 확인 부탁드립니다.",
            }
        }
    )


class DeliveryDraft(BaseModel):
    external_send_enabled: bool = False
    status: str = "draft_only"
    note: str = "MVP에서는 실제 메시지 전송 없이 문구만 생성합니다."


class MessageCard(BaseModel):
    title: str
    message_text: str
    copy_text: str
    action_type: str
    reservation_type: str
    business_name: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    service_name: Optional[str] = None
    request_note: Optional[str] = None
    alternatives: List[str] = Field(default_factory=list)
    generation_source: str = "template"      # template | llm_fallback
    delivery: DeliveryDraft = Field(default_factory=DeliveryDraft)


class SourceCandidate(BaseModel):
    business_id: Optional[str] = None
    business_name: Optional[str] = None
    category: Optional[str] = None
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class FromCandidateData(BaseModel):
    message_card: MessageCard
    source_candidate: SourceCandidate


class FromCandidateResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[FromCandidateData] = None
