"""Unit tests for backend/services/image_verification_fp_guard.py.

Confirms the guard only ever downgrades verified -> retake_required, never
touches rejected/retake_required, and never reads anything beyond the
VisionAnalysis object it's given (no gt_label/manifest concept exists here
to accidentally depend on).
"""

from backend.database.schema.image_verification_schema import (
    ImageVerificationData,
    RuleScoreBreakdown,
    VisionAnalysis,
)
from backend.services.image_verification_fp_guard import apply_fp_guard


def _verified(task, evidence_field, evidence, blockers=None, uncertainty="low"):
    analysis = VisionAnalysis(**{evidence_field: evidence, "blockers": blockers or [], "uncertainty": uncertainty})
    return ImageVerificationData(
        verification_type=task, result="verified", score=80, mandatory_passed=True,
        score_breakdown=RuleScoreBreakdown(), vlm_analysis=analysis,
    )


def test_guard_passes_clean_verified_water():
    data = _verified("water", "water_visual_evidence", ["visible_water", "filled_container"])
    out = apply_fp_guard("water", data)
    assert out.result == "verified"
    assert out.guard_reason == ""


def test_guard_vetoes_water_with_contradictory_evidence_even_if_verified():
    data = _verified("water", "water_visual_evidence", ["visible_water", "filled_container", "empty_container"])
    out = apply_fp_guard("water", data)
    assert out.result == "retake_required"
    assert "empty_container" in out.guard_reason


def test_guard_vetoes_on_explicit_blockers_field_too():
    data = _verified("water", "water_visual_evidence", ["visible_water", "filled_container"],
                      blockers=["non_water_beverage"])
    out = apply_fp_guard("water", data)
    assert out.result == "retake_required"


def test_guard_vetoes_on_non_low_uncertainty():
    data = _verified("water", "water_visual_evidence", ["visible_water", "filled_container"],
                      uncertainty="medium")
    out = apply_fp_guard("water", data)
    assert out.result == "retake_required"
    assert "uncertainty" in out.guard_reason


def test_guard_passes_clean_verified_study():
    data = _verified("study", "study_visual_evidence", ["open_textbook"])
    out = apply_fp_guard("study", data)
    assert out.result == "verified"


def test_guard_vetoes_study_with_entertainment_contradiction():
    data = _verified("study", "study_visual_evidence", ["open_textbook", "gaming_content"])
    out = apply_fp_guard("study", data)
    assert out.result == "retake_required"


def test_guard_vetoes_exercise_with_unrelated_environment():
    data = _verified("exercise", "exercise_visual_evidence", ["gym_environment", "unrelated_environment"])
    out = apply_fp_guard("exercise", data)
    assert out.result == "retake_required"


def test_guard_never_touches_rejected():
    analysis = VisionAnalysis(water_visual_evidence=["empty_container"])
    data = ImageVerificationData(
        verification_type="water", result="rejected", score=0, mandatory_passed=False,
        score_breakdown=RuleScoreBreakdown(), vlm_analysis=analysis,
    )
    out = apply_fp_guard("water", data)
    assert out.result == "rejected"
    assert out.guard_reason == ""


def test_guard_never_touches_retake_required():
    analysis = VisionAnalysis(water_visual_evidence=[])
    data = ImageVerificationData(
        verification_type="water", result="retake_required", score=0, mandatory_passed=False,
        score_breakdown=RuleScoreBreakdown(), vlm_analysis=analysis,
    )
    out = apply_fp_guard("water", data)
    assert out.result == "retake_required"
