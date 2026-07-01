"""Emotion endpoints — emotion analysis & life coaching."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.response import success_response
from backend.database.schema.emotion_schema import (
    EmotionAnalyzeRequest,
    EmotionAnalyzeResponse,
)
from backend.database.schema.personalization_schema import (
    EmotionCoachRequest,
    EmotionCoachResponse,
)
from backend.database.session import get_db
from backend.services import emotion_coach_service
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


@router.post(
    "/emotion/coach",
    response_model=EmotionCoachResponse,
    summary="개인 선호 반영 감정 코칭 (rule-based, 비진단)",
)
def emotion_coach(req: EmotionCoachRequest, db: Session = Depends(get_db)):
    data = emotion_coach_service.coach(db, req)
    return success_response(message="감정 코칭 결과를 생성했습니다.", data=data.model_dump())
