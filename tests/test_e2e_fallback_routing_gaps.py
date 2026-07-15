"""Targeted regression tests for the specific failure modes found during the
real-device (backend-only, curl-substituted) E2E smoke test session:

  - water task must escalate to Qwen7B fallback just like study/exercise
    (the old code only escalated for study; this repo's universal routing
    must not have silently regressed back to a task-specific path).
  - a local Smol *parser* failure (not just "not loaded") must also
    escalate, not dead-end as a terminal quality failure.

Stubs only -- no real Qwen7B model is loaded in these tests, matching this
task's instruction that stubs are for routing tests only, never reported as
performance results.
"""

from __future__ import annotations

from pathlib import Path

from backend.database.schema.image_verification_schema import (
    ImageObjectObservation,
    ImageQuality,
    VisionAnalysis,
)
from backend.services.image_verification_service import verify_image_upload
from backend.services.vision_analyzer import MockVisionAnalyzer, _unavailable_analysis

ROOT = Path(__file__).resolve().parents[1]
WATER_IMG = ROOT / "local_eval" / "real_validation_dataset_150_candidate" / "images" / "water" / "water_001.png"


def _weak_smol_analysis():
    """No positive evidence, no blocker -- exactly the case that must escalate."""
    return VisionAnalysis(quality=ImageQuality(usable=True))


def test_water_task_escalates_to_qwen7b_fallback(monkeypatch):
    """Regression guard: water must use the same universal fallback contract
    as study/exercise, not a task-restricted path."""
    if not WATER_IMG.exists():
        import pytest
        pytest.skip("water fixture image missing")

    monkeypatch.setattr(
        "backend.services.image_verification_service.get_default_vision_analyzer",
        lambda: MockVisionAnalyzer(_weak_smol_analysis()),
    )
    strong_water = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="glass", confidence=0.9)],
        water_visual_evidence=["visible_water", "filled_container"],
        model_name="qwen7b-mock",
    )
    with WATER_IMG.open("rb") as f:
        data = verify_image_upload(
            f, filename="water_001.png", content_type="image/png",
            verification_type="water", analyzer=None, fallback_analyzer=MockVisionAnalyzer(strong_water),
        )
    assert data.engine_used == "smol_plus_qwen7b"
    assert data.result == "verified"
    assert data.review_required is False  # clear evidence, low uncertainty -> no blanket review


def test_local_parser_failure_escalates_not_terminal(monkeypatch):
    """A Smol *parse* failure (schema mismatch/garbage output), distinct from
    'model not loaded', must still be treated as an infra failure that
    escalates to Qwen7B -- not silently treated as a genuine bad-photo
    quality failure that stops the pipeline."""
    if not WATER_IMG.exists():
        import pytest
        pytest.skip("water fixture image missing")

    parser_failure_analysis = _unavailable_analysis("Local VLM output could not be parsed.")

    monkeypatch.setattr(
        "backend.services.image_verification_service.get_default_vision_analyzer",
        lambda: MockVisionAnalyzer(parser_failure_analysis),
    )
    strong_water = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="glass", confidence=0.9)],
        water_visual_evidence=["visible_water", "filled_container"],
        model_name="qwen7b-mock",
    )
    with WATER_IMG.open("rb") as f:
        data = verify_image_upload(
            f, filename="water_001.png", content_type="image/png",
            verification_type="water", analyzer=None, fallback_analyzer=MockVisionAnalyzer(strong_water),
        )
    assert data.engine_used == "smol_plus_qwen7b"
    assert data.result == "verified"


def test_genuine_bad_photo_quality_does_not_escalate(monkeypatch):
    """Contrast case: a real photo-quality problem (not an infra failure)
    must still stop immediately without burning a Qwen7B call."""
    if not WATER_IMG.exists():
        import pytest
        pytest.skip("water fixture image missing")

    bad_photo = VisionAnalysis(quality=ImageQuality(usable=False, issues=["image is severely blurry"]))
    fallback_calls = {"count": 0}

    class CountingFallback(MockVisionAnalyzer):
        def analyze(self, *a, **kw):
            fallback_calls["count"] += 1
            return super().analyze(*a, **kw)

        def analyze_with_context(self, *a, **kw):
            fallback_calls["count"] += 1
            return super().analyze(*a, **kw)

    monkeypatch.setattr(
        "backend.services.image_verification_service.get_default_vision_analyzer",
        lambda: MockVisionAnalyzer(bad_photo),
    )
    with WATER_IMG.open("rb") as f:
        data = verify_image_upload(
            f, filename="water_001.png", content_type="image/png",
            verification_type="water", analyzer=None,
            fallback_analyzer=CountingFallback(VisionAnalysis(quality=ImageQuality(usable=True))),
        )
    assert data.result == "retake_required"
    assert data.engine_used.startswith("smol_only")
    assert fallback_calls["count"] == 0  # Qwen7B must never be called for a genuine bad photo
