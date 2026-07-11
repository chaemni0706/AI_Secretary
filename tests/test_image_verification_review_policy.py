"""secondary_review 라우팅 정책 smoke 테스트.

verified(water) → review_required=true(자동 확정 아님), exercise/study 는 기존 흐름 유지.
Rule Engine core 는 미수정; 정책은 orchestrator(service) layer 의 apply_secondary_review_policy.
"""

from backend.database.schema.image_verification_schema import (
    ImageObjectObservation,
    ImageVerificationContext,
    ImageVerificationData,
    RuleScoreBreakdown,
    VisionAnalysis,
)
from backend.services.image_verification_rule_engine import evaluate_image_verification
from backend.services.image_verification_service import apply_secondary_review_policy


def _verified_water():
    analysis = VisionAnalysis(
        objects=[ImageObjectObservation(label="cup", confidence=0.9)],
        water_visual_evidence=["visible_water", "filled_container"],
    )
    data = evaluate_image_verification("water", analysis, ImageVerificationContext())
    assert data.result == "verified"  # 전제: 룰 엔진이 verified
    return data


def test_verified_water_is_flagged_for_secondary_review():
    data = apply_secondary_review_policy(_verified_water())
    assert data.result == "verified"  # final_result enum 은 변경하지 않음
    assert data.review_required is True
    assert data.review_reason == "water_non_visual_context_risk"


def test_verified_water_response_contains_review_fields():
    dumped = apply_secondary_review_policy(_verified_water()).model_dump()
    assert dumped["review_required"] is True
    assert dumped["review_reason"] == "water_non_visual_context_risk"


def test_rejected_water_is_not_flagged():
    analysis = VisionAnalysis(water_visual_evidence=["empty_container"])
    data = evaluate_image_verification("water", analysis, ImageVerificationContext())
    assert data.result != "verified"
    out = apply_secondary_review_policy(data)
    assert out.review_required is False
    assert out.review_reason == ""


def test_verified_exercise_is_not_flagged():
    # 비-water verified 는 review 대상 아님(정책은 water 에만 적용).
    data = ImageVerificationData(
        verification_type="exercise", result="verified", score=70, mandatory_passed=True,
        score_breakdown=RuleScoreBreakdown(), vlm_analysis=VisionAnalysis(),
    )
    out = apply_secondary_review_policy(data)
    assert out.review_required is False
    assert out.review_reason == ""


def test_schema_defaults_backward_compatible():
    # review 필드는 기본값이 있어 기존 생성 코드/응답과 하위호환.
    data = ImageVerificationData(
        verification_type="study", result="rejected", score=0, mandatory_passed=False,
        score_breakdown=RuleScoreBreakdown(), vlm_analysis=VisionAnalysis(),
    )
    assert data.review_required is False
    assert data.review_reason == ""
