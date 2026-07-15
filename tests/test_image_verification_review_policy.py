"""secondary_review 라우팅 정책 smoke 테스트.

정책 변경(오늘 production patch): "water verified 는 무조건 review_required=true"
블랭킷 정책을 제거했다. 이제는 evidence/uncertainty 기반이다 -- 모델이
uncertainty="low" 로 명확한 positive evidence 를 보고하면 그대로 verified 로
확정되고(clear water 인증 가능), 모델 스스로 uncertainty!="low" 를 보고한
경우에만 review 로 보낸다. exercise/study 는 여전히 review 대상이 아니다.
Rule Engine core 는 미수정; 정책은 orchestrator(service) layer 의
apply_secondary_review_policy 뿐이다.
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


def _verified_water(uncertainty="low"):
    analysis = VisionAnalysis(
        objects=[ImageObjectObservation(label="cup", confidence=0.9)],
        water_visual_evidence=["visible_water", "filled_container"],
        uncertainty=uncertainty,
    )
    data = evaluate_image_verification("water", analysis, ImageVerificationContext())
    assert data.result == "verified"  # 전제: 룰 엔진이 verified
    return data


def test_clear_water_verified_is_not_blocked_by_review():
    """명확한 positive evidence + uncertainty=low(모델 기본값) -> review 없이 그대로 verified."""
    data = apply_secondary_review_policy(_verified_water(uncertainty="low"))
    assert data.result == "verified"
    assert data.review_required is False
    assert data.review_reason == ""


def test_uncertain_water_verified_is_flagged_for_review():
    """모델 스스로 uncertainty!=low 를 보고한 verified water 만 review 로 보낸다."""
    data = apply_secondary_review_policy(_verified_water(uncertainty="medium"))
    assert data.result == "verified"  # final_result enum 은 변경하지 않음
    assert data.review_required is True
    assert "water_model_uncertainty" in data.review_reason


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
