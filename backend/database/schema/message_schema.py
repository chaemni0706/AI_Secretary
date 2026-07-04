"""Reservation message generation schemas (/api/v1/messages)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MessageStyle(BaseModel):
    tone: str = Field("polite", description="polite | casual | formal")
    length: str = Field("short", description="short | medium | long")
    channel: str = Field("sms", description="sms | call | kakao | etc")


class ReservationInfo(BaseModel):
    category: str = Field("etc", description="hospital | beauty | restaurant | meeting | etc")
    target_date: Optional[str] = Field(None, description="'YYYY-MM-DD'")
    preferred_time: Optional[str] = Field(None, description="'HH:mm'")
    purpose: Optional[str] = Field(None, description="e.g. 진료 예약")


class ReservationMessageRequest(BaseModel):
    input: Optional[str] = Field(None, description="Original user utterance (optional)")
    reservation_info: ReservationInfo
    style: MessageStyle = Field(default_factory=MessageStyle)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "input": "내일 병원 예약 문의 문자 만들어줘",
                "reservation_info": {
                    "category": "hospital",
                    "target_date": "2026-06-30",
                    "preferred_time": "10:00",
                    "purpose": "진료 예약",
                },
                "style": {"tone": "polite", "length": "short", "channel": "sms"},
            }
        }
    )


class ReservationMessageData(BaseModel):
    generated_message: str
    alternatives: List[str] = Field(default_factory=list)
    style: MessageStyle


class ReservationMessageResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[ReservationMessageData] = None
