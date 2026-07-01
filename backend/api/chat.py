"""Chat endpoints — emotion-aware empathy response for the AI secretary.

Path here is prefix-free; ``main.py`` mounts every feature router under
``settings.API_V1_PREFIX`` (/api/v1). So the live endpoint is:

    POST /api/v1/chat/respond
"""

from fastapi import APIRouter

from backend.core.response import success_response
from backend.database.schema.chat_schema import (
    ChatRespondRequest,
    ChatRespondResponse,
)
from backend.services import chat_orchestrator

router = APIRouter(tags=["chat"])


@router.post(
    "/chat/respond",
    response_model=ChatRespondResponse,
    summary="감정·의도 기반 공감 응답 (rule-based + optional LLM, 비진단)",
)
async def chat_respond(req: ChatRespondRequest):
    data = chat_orchestrator.respond(req)
    return success_response(
        message="챗봇 응답 생성 완료",
        data=data.model_dump(),
    )
