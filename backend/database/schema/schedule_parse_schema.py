"""Enhanced natural-language schedule parsing schemas.

Backs the enhanced parse + confirm endpoints:
  * POST /api/v1/ai/schedule/parse/enhanced  -> EnhancedParseData
  * POST /api/v1/ai/schedule/confirm          -> save a confirmed parse

The pre-existing /ai/schedule/parse contract (nested intent / slots /
schedule_draft) is intentionally left untouched; this response is a flat,
UX-friendly shape carrying parse_source / warnings / clarification hints.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

# Category enum shared with rules/schedule_category_rules.json
ParseCategory = Literal["health", "beauty", "study", "work", "meal", "personal", "other"]
ParseSource = Literal["llm", "rule_fallback", "hybrid"]
ItemType = Literal["EVENT", "TODO"]


class EnhancedParseRequest(BaseModel):
    # accepts either {"text": ...} (spec) or {"input": ...} (legacy field name)
    text: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("text", "input"),
        description="분석할 자연어 입력",
    )
    user_id: str = "local-user"
    timezone: str = "Asia/Seoul"
    today: Optional[str] = Field(
        None, description="기준 날짜 'YYYY-MM-DD' (테스트/디버깅용). 없으면 timezone 기준 오늘"
    )
    use_llm: bool = Field(True, description="False면 rule-based만 사용")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "text": "내일 오후 3시에 병원 예약 있어",
                "user_id": "local-user",
                "timezone": "Asia/Seoul",
                "today": "2026-07-01",
                "use_llm": True,
            }
        },
    )


class EnhancedParseData(BaseModel):
    original_text: str
    title: Optional[str] = None
    date: Optional[str] = Field(None, description="'YYYY-MM-DD'")
    start_time: Optional[str] = Field(None, description="'HH:MM'")
    end_time: Optional[str] = Field(None, description="'HH:MM'")
    category: Optional[str] = None
    location: Optional[str] = None
    memo: Optional[str] = None
    is_all_day: bool = False
    confidence: float = Field(0.0, description="0.0 ~ 1.0")
    parse_source: ParseSource = "rule_fallback"
    item_type: ItemType = Field("EVENT", description="EVENT(일정) | TODO(할 일)")
    # timezone actually applied + resolved base date used for relative dates
    timezone: Optional[str] = None
    base_date: Optional[str] = Field(None, description="'YYYY-MM-DD'")
    warnings: List[str] = Field(default_factory=list)
    # clarification UX (optional, additive)
    needs_clarification: bool = False
    clarification_questions: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)


class EnhancedParseResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[EnhancedParseData] = None


# --------------------------------------------------------------------------- #
# Confirm (save a confirmed parse into the local schedule store)
# --------------------------------------------------------------------------- #
class ConfirmParsedInput(BaseModel):
    """The parsed result the user approved. Lenient (extra fields ignored) so a
    client can round-trip an EnhancedParseData without friction."""
    original_text: Optional[str] = None
    title: Optional[str] = None
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    memo: Optional[str] = None
    is_all_day: bool = False
    confidence: Optional[float] = None
    parse_source: Optional[str] = None
    item_type: Optional[str] = Field(None, description="EVENT | TODO")
    warnings: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class ScheduleConfirmRequest(BaseModel):
    user_id: str = Field("local-user", min_length=1)
    item_type: Optional[str] = Field(None, description="EVENT | TODO (없으면 parsed.item_type/기본 EVENT)")
    parsed: ConfirmParsedInput

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "local-user",
                "parsed": {
                    "original_text": "내일 오후 3시에 병원 예약 있어",
                    "title": "병원 예약",
                    "date": "2026-07-02",
                    "start_time": "15:00",
                    "end_time": None,
                    "category": "health",
                    "location": None,
                    "memo": None,
                    "is_all_day": False,
                    "confidence": 0.86,
                    "parse_source": "hybrid",
                    "warnings": [],
                },
            }
        }
    )


class ScheduleConfirmResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[dict] = None
