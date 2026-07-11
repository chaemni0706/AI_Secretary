"""Image verification request/response schemas.

The VLM analysis is intentionally limited to observable facts. Final
verification is decided by the deterministic rule engine, not the VLM.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


VerificationType = Literal["gym", "study", "medicine", "water", "wakeup", "exercise"]
VerificationResult = Literal["verified", "retake_required", "rejected"]
ExerciseActivityType = Literal["gym", "running", "swimming", "yoga", "pilates", "home_workout"]
StudyVisualEvidence = Literal[
    "open_textbook",
    "open_workbook",
    "handwritten_notes",
    "highlighted_text",
    "problem_solving_material",
    "study_content_on_screen",
    "lecture_video",
    "educational_document",
    "code_editor",
    "study_timer",
    "gaming_content",
    "entertainment_video",
    "social_media",
    "shopping_content",
    "non_study_screen",
    "closed_study_materials",
    "uncertain_screen_content",
]
WaterVisualEvidence = Literal[
    "visible_water",
    "visible_clear_liquid",
    "filled_container",
    "sealed_water_bottle",
    "water_stream",
    "container_under_dispenser",
    "receiving_water",
    "empty_container",
    "opaque_closed_container",
    "non_water_beverage",
    "uncertain_liquid",
]
ExerciseVisualEvidence = Literal[
    "exercise_environment",
    "exercise_equipment_present",
    "exercise_pose_visible",
    "gym_environment",
    "treadmill_present",
    "dumbbell_present",
    "barbell_present",
    "weight_machine_present",
    "exercise_bike_present",
    "gym_bench_present",
    "running_environment",
    "running_track_present",
    "treadmill_running_environment",
    "stadium_track_present",
    "park_running_path_present",
    "swimming_pool_environment",
    "swimming_lane_present",
    "lane_rope_present",
    "swim_cap_present",
    "swim_goggles_present",
    "yoga_environment",
    "yoga_mat_present",
    "yoga_studio_present",
    "yoga_pose_visible",
    "pilates_environment",
    "pilates_reformer_present",
    "pilates_equipment_present",
    "pilates_studio_present",
    "pilates_pose_visible",
    "home_workout_environment",
    "exercise_mat_present",
    "resistance_band_present",
    "home_dumbbell_present",
    "kettlebell_present",
    "pull_up_bar_present",
    "home_exercise_pose_visible",
    "unrelated_environment",
    "wrong_activity_environment",
    "insufficient_exercise_evidence",
    "uncertain_exercise_environment",
]


class ImageObjectObservation(BaseModel):
    label: str
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    evidence: Optional[str] = None


class ImageQuality(BaseModel):
    brightness: Literal["low", "normal", "high"] = "normal"
    blur: Literal["low", "medium", "high"] = "low"
    usable: bool = True
    issues: list[str] = Field(default_factory=list)


class VisionAnalysis(BaseModel):
    quality: ImageQuality = Field(default_factory=ImageQuality)
    scene: Optional[str] = None
    objects: list[ImageObjectObservation] = Field(default_factory=list)
    visible_text: list[str] = Field(default_factory=list)
    visual_evidence: list[str] = Field(default_factory=list)
    study_visual_evidence: list[StudyVisualEvidence] = Field(default_factory=list)
    water_visual_evidence: list[WaterVisualEvidence] = Field(default_factory=list)
    exercise_visual_evidence: list[ExerciseVisualEvidence] = Field(default_factory=list)


class LocationInput(BaseModel):
    latitude: float
    longitude: float


class TimeContext(BaseModel):
    captured_at: Optional[str] = Field(None, description="ISO datetime from client")
    scheduled_at: Optional[str] = Field(None, description="ISO datetime for planned verification")


class ImageVerificationContext(BaseModel):
    location: Optional[LocationInput] = None
    target_location: Optional[LocationInput] = None
    time: TimeContext = Field(default_factory=TimeContext)
    exercise_activity_type: Optional[ExerciseActivityType] = None


class RuleScoreBreakdown(BaseModel):
    base_score: int = 0
    object_score: int = 0
    text_score: int = 0
    scene_score: int = 0
    gps_score: int = 0
    total_score: int = 0


class RuleEvidence(BaseModel):
    code: str
    message: str
    score_delta: int = 0


class ImageVerificationData(BaseModel):
    verification_type: VerificationType
    result: VerificationResult
    score: int
    mandatory_passed: bool
    score_breakdown: RuleScoreBreakdown
    vlm_analysis: VisionAnalysis
    rule_evidence: list[RuleEvidence] = Field(default_factory=list)
    # secondary_review 라우팅(orchestrator/API layer 에서 설정; Rule Engine core 미변경).
    # VLM-eligible visual scope 밖일 수 있는 verified(현재: water)는 자동 확정하지 않고 review 로 표시.
    review_required: bool = Field(
        default=False,
        description="verified 이지만 비시각 맥락 확인이 필요해 자동 확정 대신 secondary_review 로 보내야 하는지",
    )
    review_reason: str = Field(default="", description="review 사유(예: water_non_visual_context_risk)")


class ImageVerificationResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[ImageVerificationData] = None


class MockVisionAnalysisRequest(BaseModel):
    verification_type: VerificationType
    analysis: VisionAnalysis

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "verification_type": "study",
                "analysis": {
                    "quality": {"brightness": "normal", "blur": "low", "usable": True},
                    "scene": "desk",
                    "objects": [{"label": "book", "confidence": 0.9}],
                    "visible_text": ["chapter 1"],
                    "visual_evidence": ["book and notebook are visible"],
                },
            }
        }
    )


class WakeupSessionCreateRequest(BaseModel):
    scheduled_at: str
    allowed_early_minutes: int = Field(5, ge=0)
    allowed_late_minutes: int = Field(10, ge=0)
    session_ttl_seconds: int = Field(120, gt=0)
    max_retries: int = Field(2, ge=0)


class WakeupSessionData(BaseModel):
    session_id: str
    scheduled_at: str
    server_issued_at: str
    expires_at: str
    display_time: str
    max_retries: int


class WakeupVerificationData(BaseModel):
    decision: VerificationResult
    scheduled_at: str
    server_issued_at: str
    received_at: str
    difference_minutes: float
    session_expired: bool
    duplicate_image: bool
    image_quality_usable: bool
    reasons: list[str] = Field(default_factory=list)
    image_sha256: str
    retry_count: int = 0
    max_retries: int = 0
