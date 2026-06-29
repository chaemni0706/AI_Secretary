"""Emotion endpoints — emotion analysis & life coaching."""

from fastapi import APIRouter

from backend.core.response import success_response
from backend.database.schema.emotion_schema import (
    EmotionAnalyzeRequest,
    EmotionAnalyzeResponse,
)
from backend.services.emotion_analyzer import analyze_emotion

router = APIRouter(tags=["emotion"])


@router.post(
    "/emotion/analyze",
    response_model=EmotionAnalyzeResponse,
    summary="감정 분석 및 생활 코칭 (rule-based, 비진단)",
)
async def emotion_analyze(req: EmotionAnalyzeRequest):
    data = analyze_emotion(req)
    return success_response(
        message="감정 분석이 완료되었습니다.",
        data=data.model_dump(),
    )
