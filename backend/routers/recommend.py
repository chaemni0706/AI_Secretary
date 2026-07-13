"""개인화 추천 API — M1(빈 시간) / M2(미룰 일정) / M3(장소).

M1·M3는 ML(LogisticRegression Pipeline), M2는 규칙 기반. ml_recommender 서비스 참조.
"""

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from backend.services import ml_recommender

router = APIRouter(prefix="/api/v1/recommend", tags=["recommend"])


class UserProfile(BaseModel):
    gender: str
    age_group: str
    job_group: str
    planning_score: float
    execution_score: float
    morning_score: float
    social_score: float
    exploration_score: float


class FreeTimeCandidate(BaseModel):
    candidate_id: str
    start_time: str
    end_time: str
    day_index: int
    start_minutes: int
    week_start_minutes: int
    time_slot: str
    is_weekend: int
    is_earliest_free_slot: int
    day_event_count: int
    before_free_minutes: int
    after_free_minutes: int
    is_empty_day: int
    is_right_after_existing_event: int


class PostponeCandidate(BaseModel):
    candidate_id: str
    reschedulability_level: int
    importance_level: int
    urgency_level: int
    fatigue_burden_level: int
    penalty_if_postponed_level: int
    has_other_people: int


class PlaceCandidate(BaseModel):
    candidate_id: str
    place_category: str
    distance_minutes: float
    distance_km: float
    price_level: int
    wait_minutes: float
    rating: float
    review_count: int
    reservation_available: int
    atmosphere: str
    purpose_fit_level: int
    familiarity_level: int


class FreeTimeRecommendRequest(BaseModel):
    user: UserProfile
    candidates: List[FreeTimeCandidate]


class PostponeRecommendRequest(BaseModel):
    user: UserProfile
    candidates: List[PostponeCandidate]


class PlaceRecommendRequest(BaseModel):
    user: UserProfile
    candidates: List[PlaceCandidate]


@router.post("/free-time")
def recommend_free_time(request: FreeTimeRecommendRequest):
    recommendations = ml_recommender.recommend_free_time(
        request.user.model_dump(), [c.model_dump() for c in request.candidates]
    )
    return {"recommendations": recommendations}


@router.post("/postpone")
def recommend_postpone(request: PostponeRecommendRequest):
    recommendations = ml_recommender.recommend_postpone(
        request.user.model_dump(), [c.model_dump() for c in request.candidates]
    )
    return {"recommendations": recommendations}


@router.post("/place")
def recommend_place(request: PlaceRecommendRequest):
    recommendations = ml_recommender.recommend_place(
        request.user.model_dump(), [c.model_dump() for c in request.candidates]
    )
    return {"recommendations": recommendations}
