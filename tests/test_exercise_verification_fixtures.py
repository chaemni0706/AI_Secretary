"""운동 인증 테스트셋 pytest (gym + home_workout MVP).

물 인증(test_water_verification_fixtures.py)과 동일 구조.

검증:
1. 매니페스트 12장 + 필수 필드 + 이미지 존재
2. vision_analysis가 VisionAnalysis schema를 통과
3. evaluate_image_verification("exercise", analysis, ctx(exercise_activity_type))의 판정이 기대 라벨과 일치
4. office/bedroom/food/empty room → PASS 금지
5. shoes_only / water_bottle_only → PASS 금지
6. normalize_exercise_output (Qwen 증거 → VisionAnalysis) 정규화 검증

이미지 준비 (없으면 세션 시작 시 생성):
    python scripts/generate_exercise_test_images.py

실행:
    python -m pytest tests/test_exercise_verification_fixtures.py -v -s
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "local_eval" / "qwen_vlm_eval" / "scripts"
MANIFEST_PATH = ROOT / "data" / "test_images" / "exercise" / "exercise_manifest.json"
GEN_SCRIPT = ROOT / "scripts" / "generate_exercise_test_images.py"
REPORT_PATH = ROOT / "local_eval" / "qwen_vlm_eval" / "outputs" / "exercise_batch" / "exercise_verdict_report.csv"

sys.path.insert(0, str(SCRIPTS_DIR))
import normalize_exercise_output as neo  # noqa: E402

from backend.database.schema.image_verification_schema import (  # noqa: E402
    ImageObjectObservation,
    ImageVerificationContext,
    VisionAnalysis,
)
from backend.services.image_verification_rule_engine import evaluate_image_verification  # noqa: E402

MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
IMAGES = MANIFEST["images"]

ENGINE_TO_LABEL = {"verified": "PASS", "rejected": "FAIL", "retake_required": "BORDERLINE_CASE"}


def _evaluate(entry):
    analysis = VisionAnalysis.model_validate(entry["vision_analysis"])
    ctx = ImageVerificationContext(exercise_activity_type=entry.get("exercise_activity_type"))
    return evaluate_image_verification("exercise", analysis, ctx)


@pytest.fixture(scope="session", autouse=True)
def ensure_images():
    missing = [e for e in IMAGES if not (ROOT / e["image_path"]).exists()]
    if missing:
        subprocess.run([sys.executable, str(GEN_SCRIPT)], check=True, cwd=str(ROOT))
    yield


@pytest.fixture(scope="session")
def report_rows():
    rows = []
    yield rows
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = ["filename,exercise_activity_type,expected_label,predicted_label,match,score"]
    for r in rows:
        lines.append(f'{r["filename"]},{r["activity"]},{r["expected"]},{r["predicted"]},{r["match"]},{r["score"]}')
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. 매니페스트 무결성
# ---------------------------------------------------------------------------

def test_manifest_counts():
    assert MANIFEST["counts"]["total"] == 12
    assert len(IMAGES) == 12
    assert MANIFEST["verification_type"] == "exercise"


@pytest.mark.parametrize("entry", IMAGES, ids=[e["filename"] for e in IMAGES])
def test_manifest_entry_fields(entry):
    for field in ("filename", "image_path", "expected_label", "source", "exercise_activity_type", "reason", "difficulty"):
        assert entry.get(field), f"{entry.get('filename')} missing {field}"
    assert entry["expected_label"] in {"PASS", "FAIL", "BORDERLINE"}
    assert entry["source"] == "generated"
    assert entry["exercise_activity_type"] in {"gym", "home_workout"}
    assert entry["difficulty"] in {"easy", "medium", "hard"}


@pytest.mark.parametrize("entry", IMAGES, ids=[e["filename"] for e in IMAGES])
def test_image_file_exists(entry):
    assert (ROOT / entry["image_path"]).exists(), f"missing image: {entry['image_path']}"


@pytest.mark.parametrize("entry", IMAGES, ids=[e["filename"] for e in IMAGES])
def test_vision_analysis_schema_valid(entry):
    analysis = VisionAnalysis.model_validate(entry["vision_analysis"])
    assert isinstance(analysis, VisionAnalysis)
    # exercise 테스트셋이므로 물/공부 근거는 비어 있어야 한다
    assert analysis.water_visual_evidence == []
    assert analysis.study_visual_evidence == []


# ---------------------------------------------------------------------------
# 2. Rule Engine 판정이 기대 라벨과 일치
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entry", IMAGES, ids=[e["filename"] for e in IMAGES])
def test_exercise_verdict_matches_expected(entry, report_rows):
    data = _evaluate(entry)
    predicted = ENGINE_TO_LABEL.get(data.result, "UNKNOWN")
    expected = entry["expected_label"]
    match = (predicted != "PASS") if expected == "BORDERLINE" else (predicted == expected)
    report_rows.append({
        "filename": entry["filename"], "activity": entry["exercise_activity_type"],
        "expected": expected, "predicted": predicted, "match": match, "score": data.score,
    })
    print(f"{entry['filename']:<48} act={entry['exercise_activity_type']:<12} "
          f"expected={expected:<10} predicted={predicted:<15} score={data.score}")
    if expected == "BORDERLINE":
        assert predicted != "PASS", f"BORDERLINE 이미지가 PASS로 판정됨: {entry['filename']}"
    else:
        assert predicted == expected, f"{entry['filename']}: predicted {predicted}, expected {expected}"


def test_false_positive_zero():
    """어떤 FAIL/BORDERLINE 이미지도 PASS로 판정되면 안 된다 (false positive 0)."""
    fp = []
    for entry in IMAGES:
        if entry["expected_label"] == "PASS":
            continue
        if ENGINE_TO_LABEL.get(_evaluate(entry).result) == "PASS":
            fp.append(entry["filename"])
    assert fp == [], f"false positives: {fp}"


# ---------------------------------------------------------------------------
# 3. 특정 negative 케이스는 PASS 금지
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stem", [
    "generated_exercise_07_office_desk",
    "generated_exercise_08_bedroom_no_exercise",
    "generated_exercise_09_food_table",
    "generated_exercise_10_empty_room",
])
def test_non_exercise_scenes_not_pass(stem):
    entry = next(e for e in IMAGES if Path(e["filename"]).stem == stem)
    assert ENGINE_TO_LABEL.get(_evaluate(entry).result) != "PASS"


@pytest.mark.parametrize("stem", [
    "generated_exercise_11_shoes_only",
    "generated_exercise_12_water_bottle_only",
])
def test_shoes_or_bottle_only_not_pass(stem):
    entry = next(e for e in IMAGES if Path(e["filename"]).stem == stem)
    assert ENGINE_TO_LABEL.get(_evaluate(entry).result) != "PASS"


def test_equipment_without_environment_or_activity_type_not_verified():
    """activity_type이 없으면 운동 기구가 보여도 verified가 아니어야 한다."""
    analysis = VisionAnalysis(exercise_visual_evidence=["dumbbell_present"])
    data = evaluate_image_verification("exercise", analysis, ImageVerificationContext())
    assert data.result != "verified"


# ---------------------------------------------------------------------------
# 4. normalize_exercise_output 검증 (Qwen 증거 → VisionAnalysis)
# ---------------------------------------------------------------------------

def test_normalize_gym_dumbbell_pass():
    raw = {
        "objects": [{"name": "dumbbell", "description": "a pair of dumbbells"}],
        "scenes": [{"description": "a gym with weights"}],
        "visual_evidence": [{"description": "dumbbell on the floor of a gym"}],
    }
    normalized = neo.normalize_exercise_evidence(raw, "gym")
    ev = set(normalized["exercise_visual_evidence"])
    assert "dumbbell_present" in ev
    assert "gym_environment" in ev  # 기구 근거로 환경 보강
    analysis = VisionAnalysis.model_validate(normalized)
    data = evaluate_image_verification("exercise", analysis, ImageVerificationContext(exercise_activity_type="gym"))
    assert data.result == "verified"


def test_normalize_home_mat_pass():
    raw = {
        "objects": [{"name": "yoga mat"}],
        "visual_evidence": [{"description": "an exercise mat on the floor at home"}],
    }
    normalized = neo.normalize_exercise_evidence(raw, "home_workout")
    ev = set(normalized["exercise_visual_evidence"])
    assert "exercise_mat_present" in ev
    assert "home_workout_environment" in ev
    analysis = VisionAnalysis.model_validate(normalized)
    data = evaluate_image_verification("exercise", analysis, ImageVerificationContext(exercise_activity_type="home_workout"))
    assert data.result == "verified"


def test_normalize_office_desk_not_pass():
    raw = {
        "objects": [{"name": "desk"}, {"name": "laptop"}],
        "scenes": [{"description": "an office desk with a laptop"}],
        "visual_evidence": [{"description": "office workstation, no exercise equipment"}],
    }
    normalized = neo.normalize_exercise_evidence(raw, "gym")
    assert "unrelated_environment" in normalized["exercise_visual_evidence"]
    analysis = VisionAnalysis.model_validate(normalized)
    data = evaluate_image_verification("exercise", analysis, ImageVerificationContext(exercise_activity_type="gym"))
    assert ENGINE_TO_LABEL.get(data.result) != "PASS"


def test_normalize_shoes_only_not_pass():
    raw = {
        "objects": [{"name": "running shoes"}],
        "visual_evidence": [{"description": "running shoes only, no other equipment"}],
    }
    normalized = neo.normalize_exercise_evidence(raw, "gym")
    assert "insufficient_exercise_evidence" in normalized["exercise_visual_evidence"]
    analysis = VisionAnalysis.model_validate(normalized)
    data = evaluate_image_verification("exercise", analysis, ImageVerificationContext(exercise_activity_type="gym"))
    assert ENGINE_TO_LABEL.get(data.result) != "PASS"


def test_borderline_cases_recorded():
    borderline = MANIFEST.get("borderline_cases", [])
    labeled = {e["filename"] for e in IMAGES if e["expected_label"] == "BORDERLINE"}
    assert {b["filename"] for b in borderline} == labeled
    for b in borderline:
        assert b["predicted_label"] != "PASS"
