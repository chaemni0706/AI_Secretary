import json
from pathlib import Path

import pytest

from backend.database.schema.image_verification_schema import (
    ImageObjectObservation,
    ImageVerificationContext,
    ImageQuality,
    VisionAnalysis,
)
from backend.services.image_verification_rule_engine import evaluate_image_verification


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "local_eval" / "study_verification_fixture_pack"


def _load_fixture(image_id: str) -> VisionAnalysis:
    payload = json.loads((FIXTURE_DIR / "fixtures" / f"{image_id}.json").read_text(encoding="utf-8"))
    return VisionAnalysis.model_validate(payload)


def _ground_truth() -> dict[str, str]:
    expected = {}
    for line in (FIXTURE_DIR / "study_ground_truth.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        expected[item["image_id"]] = item["expected_decision"]
    return expected


@pytest.mark.parametrize("image_id,expected", sorted(_ground_truth().items()))
def test_study_fixture_decisions(image_id, expected):
    analysis = _load_fixture(image_id)

    data = evaluate_image_verification("study", analysis, ImageVerificationContext())

    assert data.result == expected


@pytest.mark.parametrize("image_id", [f"study_{i:02d}" for i in range(1, 11)])
def test_study_fixture_json_matches_pydantic_schema(image_id):
    analysis = _load_fixture(image_id)

    assert isinstance(analysis, VisionAnalysis)
    assert analysis.water_visual_evidence == []


def test_gaming_content_rejects_even_with_desk_and_monitor():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[
            ImageObjectObservation(label="monitor", confidence=0.99),
            ImageObjectObservation(label="keyboard", confidence=0.99),
            ImageObjectObservation(label="desk", confidence=0.99),
        ],
        study_visual_evidence=["gaming_content", "study_content_on_screen"],
    )

    data = evaluate_image_verification("study", analysis, ImageVerificationContext())

    assert data.result == "rejected"


@pytest.mark.parametrize("label", ["laptop", "monitor"])
def test_laptop_or_monitor_alone_cannot_be_verified(label):
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label=label, confidence=0.99)],
    )

    data = evaluate_image_verification("study", analysis, ImageVerificationContext())

    assert data.result != "verified"
    assert data.result == "rejected"


def test_duplicate_study_evidence_scores_once():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[
            ImageObjectObservation(label="book", confidence=0.99),
            ImageObjectObservation(label="desk", confidence=0.99),
            ImageObjectObservation(label="pen", confidence=0.99),
        ],
        study_visual_evidence=[
            "open_textbook",
            "open_textbook",
            "handwritten_notes",
            "handwritten_notes",
        ],
    )

    data = evaluate_image_verification("study", analysis, ImageVerificationContext())

    assert data.result == "verified"
    assert data.score_breakdown.object_score == 55


def test_uncertain_screen_content_alone_requires_retake():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="monitor", confidence=0.99)],
        study_visual_evidence=["uncertain_screen_content"],
    )

    data = evaluate_image_verification("study", analysis, ImageVerificationContext())

    assert data.result == "retake_required"
