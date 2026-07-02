"""Turn a chosen reservation candidate into a reservation-message card.

Reuses the EXISTING template+LLM message generator (message_generator) for the
`inquiry` action (template first, LLM fallback preserved) and small templates
for confirm/change/cancel/check. Draft-only: NO external send, NO booking.
Never raises 500 — missing required fields raise MissingFieldsError which the
router turns into a 422 + missing_fields payload.
"""

from __future__ import annotations

from typing import List, Optional

from backend.database.schema.message_schema import (
    ReservationInfo,
    ReservationMessageRequest,
)
from backend.database.schema.reservation_message_schema import (
    CandidateInput,
    DeliveryDraft,
    FromCandidateData,
    FromCandidateRequest,
    MessageCard,
    SourceCandidate,
)
from backend.services import llm_service
from backend.services.message_generator import generate_message

# candidate category -> reservation_type LABEL shown in the card
_RESERVATION_TYPE = {
    "hair": "beauty", "beauty": "beauty", "nail": "beauty",
    "health": "hospital", "hospital": "hospital", "dental": "hospital",
    "meal": "restaurant", "restaurant": "restaurant",
    "study": "meeting", "meeting": "meeting",
    "pt": "fitness", "fitness": "fitness",
}
# reservation_type LABEL -> category the message engine actually supports
_ENGINE_CATEGORY = {
    "beauty": "beauty", "hospital": "hospital", "restaurant": "restaurant",
    "meeting": "meeting", "fitness": "etc", "general": "etc",
}
_ACTION_LABEL = {
    "inquiry": "문의", "confirm": "확정 요청", "change": "변경 문의",
    "cancel": "취소 요청", "check": "확인 요청",
}
_ACTION_MESSAGE_VERB = {
    "confirm": "예약을 확정하고 싶어 문의드립니다.",
    "change": "예약을 변경하고 싶어 문의드립니다.",
    "cancel": "예약을 취소하고 싶어 문의드립니다.",
    "check": "예약이 정상 접수되었는지 확인 부탁드립니다.",
}


class MissingFieldsError(Exception):
    def __init__(self, missing: List[str]):
        self.missing = missing
        super().__init__("예약 메시지 생성에 필요한 정보가 부족합니다.")


def reservation_type_for(category: Optional[str]) -> str:
    return _RESERVATION_TYPE.get((category or "").lower(), "general")


def _date_kor(date: Optional[str]) -> str:
    if not date:
        return ""
    try:
        y, m, d = date.split("-")
        return f"{int(y)}년 {int(m)}월 {int(d)}일"
    except (ValueError, AttributeError):
        return date


def reservation_candidate_to_message_request(
    candidate: CandidateInput, *, service_name: Optional[str] = None,
) -> ReservationMessageRequest:
    """Map a candidate onto the existing ReservationMessageRequest.

    category -> engine category via the reservation_type alias; date/start_time
    -> target_date/preferred_time; service_name -> purpose (beauty keeps its own
    default '커트 또는 시술' regardless)."""
    rtype = reservation_type_for(candidate.category)
    engine_category = _ENGINE_CATEGORY.get(rtype, "etc")
    return ReservationMessageRequest(
        reservation_info=ReservationInfo(
            category=engine_category,
            target_date=candidate.date,
            preferred_time=candidate.start_time,
            purpose=service_name,   # None -> engine category default
        )
    )


def _missing_fields(c: CandidateInput) -> List[str]:
    missing: List[str] = []
    if not (c.business_name and c.business_name.strip()):
        missing.append("business_name")
    if not (c.date and c.date.strip()):
        missing.append("date")
    if not (c.start_time and c.start_time.strip()):
        missing.append("start_time")
    if not (c.category and c.category.strip()):
        missing.append("category")
    return missing


def build_message_card(req: FromCandidateRequest) -> FromCandidateData:
    c = req.candidate
    missing = _missing_fields(c)
    if missing:
        raise MissingFieldsError(missing)

    rtype = reservation_type_for(c.category)
    action = req.action_type
    party_size = req.party_size if req.party_size is not None else c.party_size

    # --- message body ---------------------------------------------------- #
    if action == "inquiry":
        # reuse the existing engine (template first; LLM fallback preserved)
        data = generate_message(
            reservation_candidate_to_message_request(c, service_name=req.service_name)
        )
        message_text = data.generated_message
        alternatives = data.alternatives
        generation_source = "llm_fallback" if llm_service.is_enabled() else "template"
    else:
        when = f"{_date_kor(c.date)} {c.start_time}".strip()
        subject = f"{req.service_name} " if req.service_name else ""
        message_text = f"안녕하세요. {when} {subject}{_ACTION_MESSAGE_VERB[action]}"
        alternatives = []
        generation_source = "template"

    # restaurant party size -> reflect in the message
    if rtype == "restaurant" and party_size:
        message_text = f"{message_text} {party_size}명 예약 가능할까요?"

    message_text = " ".join(message_text.split())

    card = MessageCard(
        title=f"{c.business_name} 예약 {_ACTION_LABEL.get(action, '문의')}",
        message_text=message_text,
        copy_text=message_text,
        action_type=action,
        reservation_type=rtype,
        business_name=c.business_name,
        date=c.date,
        time=c.start_time,
        service_name=req.service_name,
        request_note=req.request_note,
        alternatives=alternatives,
        generation_source=generation_source,
        delivery=DeliveryDraft(),
    )
    source = SourceCandidate(
        business_id=c.business_id, business_name=c.business_name, category=c.category,
        date=c.date, start_time=c.start_time, end_time=c.end_time,
    )
    return FromCandidateData(message_card=card, source_candidate=source)
