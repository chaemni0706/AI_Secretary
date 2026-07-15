"""공통 Qwen verification batch runner 테스트 (torch/모델 로드 없음).

run_qwen_verification_batch 의 config/manifest/normalizer/label-mapping/process_entry 로직을
무거운 Qwen 모델 없이 검증한다. process_entry에는 가짜 raw 텍스트를 직접 주입한다.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "local_eval" / "qwen_vlm_eval" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import run_qwen_verification_batch as rb  # noqa: E402
import normalize_qwen_output as nqo  # noqa: E402

OUT = ROOT / "local_eval" / "qwen_vlm_eval" / "outputs" / "_common_test"


@pytest.fixture(autouse=True)
def _clean_out():
    yield
    shutil.rmtree(OUT, ignore_errors=True)


def _entry(vt: str, index: int = 0) -> dict:
    cfg = rb.get_config(vt)
    return rb.load_entries(cfg, cfg.default_manifest)[index]


# ---------------------------------------------------------------------------
# config / manifest 로딩
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("vt", ["water", "exercise", "study"])
def test_config_loads(vt):
    cfg = rb.get_config(vt)
    assert cfg.verification_type == vt
    assert cfg.default_manifest.exists()
    assert callable(cfg.normalize) and callable(cfg.build_context)


def test_unknown_type_raises():
    with pytest.raises(ValueError):
        rb.get_config("sleep")


def test_water_json_manifest_load():
    entries = rb.load_entries(rb.get_config("water"), rb.get_config("water").default_manifest)
    assert len(entries) == 18
    assert entries[0]["verification_type"] == "water"
    assert entries[0]["filename"].endswith(".png")


def test_exercise_json_manifest_load():
    entries = rb.load_entries(rb.get_config("exercise"), rb.get_config("exercise").default_manifest)
    assert len(entries) == 12
    assert all(e["exercise_activity_type"] in {"gym", "home_workout"} for e in entries)


def test_study_jsonl_manifest_load():
    cfg = rb.get_config("study")
    entries = rb.load_entries(cfg, cfg.default_manifest)
    assert len(entries) == 10
    e = entries[0]
    assert e["verification_type"] == "study"
    assert e["source"] == "fixture"
    assert e["filename"] == e["image_id"] + ".png"
    assert e["expected_decision"] in {"verified", "rejected", "retake_required"}
    # decision → label 매핑
    assert e["expected_label"] in {"PASS", "FAIL", "BORDERLINE"}


def test_study_decision_label_mapping():
    assert rb.STUDY_DECISION_TO_LABEL["verified"] == "PASS"
    assert rb.STUDY_DECISION_TO_LABEL["rejected"] == "FAIL"
    assert rb.STUDY_DECISION_TO_LABEL["retake_required"] == "BORDERLINE"


def test_engine_predicted_mapping():
    assert rb.ENGINE_TO_PREDICTED == {
        "verified": "PASS", "rejected": "FAIL", "retake_required": "BORDERLINE_CASE"
    }


# ---------------------------------------------------------------------------
# normalizer 선택 (config별로 알맞은 evidence field를 채우는지)
# ---------------------------------------------------------------------------

def test_water_normalizer_selected():
    cfg = rb.get_config("water")
    raw = {"objects": [{"name": "glass"}],
           "visual_evidence": [{"name": "visible_water", "description": "a glass of water, clear liquid"},
                               {"name": "filled_container", "description": "glass filled with water"}]}
    norm = cfg.normalize(raw, {})
    assert norm["water_visual_evidence"]
    assert norm["exercise_visual_evidence"] == [] and norm["study_visual_evidence"] == []


def test_exercise_normalizer_selected():
    cfg = rb.get_config("exercise")
    raw = {"objects": [{"name": "dumbbell"}], "scenes": [{"description": "a gym"}],
           "visual_evidence": [{"description": "dumbbell in a gym"}]}
    norm = cfg.normalize(raw, {"exercise_activity_type": "gym"})
    assert "dumbbell_present" in norm["exercise_visual_evidence"]
    assert norm["water_visual_evidence"] == [] and norm["study_visual_evidence"] == []


def test_study_normalizer_selected():
    cfg = rb.get_config("study")
    raw = {"visual_evidence": ["open_textbook", "handwritten_notes"]}
    norm = cfg.normalize(raw, {})
    assert "open_textbook" in norm["study_visual_evidence"]
    assert norm["water_visual_evidence"] == [] and norm["exercise_visual_evidence"] == []


# ---------------------------------------------------------------------------
# output path 생성
# ---------------------------------------------------------------------------

def test_default_output_dirs():
    assert rb.get_config("water").default_output_dir.name == "water_batch"
    assert rb.get_config("exercise").default_output_dir.name == "exercise_batch"
    assert rb.get_config("study").default_output_dir.name == "study_batch"


# ---------------------------------------------------------------------------
# process_entry smoke (torch 없음)
# ---------------------------------------------------------------------------

def test_process_entry_water_pass():
    cfg = rb.get_config("water")
    raw = json.dumps({"objects": [{"name": "glass"}],
                      "visual_evidence": [{"name": "visible_water", "description": "a glass of water, clear liquid visible"},
                                          {"name": "filled_container", "description": "glass filled with water"}]})
    rec = rb.process_entry(_entry("water"), raw, cfg, OUT)
    assert rec["verification_type"] == "water"
    assert rec["predicted_label"] == "PASS"
    assert (OUT / (Path(_entry("water")["filename"]).stem + "_result.json")).exists()


def test_process_entry_exercise_gym_pass():
    cfg = rb.get_config("exercise")
    raw = json.dumps({"objects": [{"name": "dumbbell"}], "scenes": [{"description": "a gym"}],
                      "visual_evidence": [{"description": "dumbbell in a gym"}]})
    rec = rb.process_entry(_entry("exercise", 0), raw, cfg, OUT)
    assert rec["predicted_label"] == "PASS"
    assert rec["exercise_activity_type"] == "gym"


def test_process_entry_exercise_unrelated_fail():
    cfg = rb.get_config("exercise")
    office = json.dumps({"objects": [{"name": "desk"}, {"name": "laptop"}],
                         "scenes": [{"description": "an office desk with a laptop"}]})
    rec = rb.process_entry(_entry("exercise", 6), office, cfg, OUT)  # office_desk entry
    assert rec["predicted_label"] != "PASS"


def test_process_entry_study_pass():
    cfg = rb.get_config("study")
    raw = json.dumps({"visual_evidence": ["open_textbook", "open_workbook", "handwritten_notes"],
                      "objects": ["textbook", "desk"], "image_quality_usable": True})
    rec = rb.process_entry(_entry("study", 0), raw, cfg, OUT)
    assert rec["predicted_label"] == "PASS"
    assert rec["image_id"] == "study_01"
    assert "open_textbook" in rec["visual_evidence"]


def test_process_entry_study_gaming_fail():
    cfg = rb.get_config("study")
    raw = json.dumps({"visual_evidence": ["gaming_content"], "scenes": [{"name": "screen"}]})
    rec = rb.process_entry(_entry("study", 0), raw, cfg, OUT)
    assert rec["predicted_label"] != "PASS"


def test_process_entry_borderline_ok_when_not_pass():
    """expected=BORDERLINE 이면 predicted가 PASS만 아니면 ok=True."""
    cfg = rb.get_config("study")
    entry = dict(_entry("study", 0))
    entry["expected_label"] = "BORDERLINE"
    raw = json.dumps({"visual_evidence": ["gaming_content"]})  # → FAIL
    rec = rb.process_entry(entry, raw, cfg, OUT)
    assert rec["predicted_label"] != "PASS"
    assert rec["ok"] is True


def test_process_entry_water_lemon_empty_hallucination_pass():
    """water_test_01 형태(레몬물 + 'empty container' 환각)가 공통 runner로 PASS 되는지."""
    cfg = rb.get_config("water")
    raw = json.dumps({
        "water_amount": "partial",
        "objects": [{"name": "hand holding glass"}],
        "scenes": [{"name": "hand holding glass with lemon slice"}],
        "visual_evidence": [
            {"name": "glass with lemon slice",
             "description": "A glass containing a clear liquid with a lemon slice floating in it."}],
        "negative_evidence": [{"name": "empty container", "description": "The glass appears to be empty."}],
        "uncertain_evidence": [{"name": "uncertain liquid", "description": "The liquid inside the glass is not clearly visible."}],
    })
    rec = rb.process_entry(_entry("water"), raw, cfg, OUT)
    assert "empty_container" not in rec["visual_evidence"]
    assert rec["predicted_label"] == "PASS"


def test_process_entry_json_parse_failure_is_error_row():
    cfg = rb.get_config("water")
    rec = rb.process_entry(_entry("water"), "this is not json at all", cfg, OUT)
    assert rec["predicted_label"] == "ERROR"
    assert rec["engine_result"] == "parse_error"
    assert rec["error"]
    # raw_text는 저장되어야 하고 result.json도 생성되어야 한다
    stem = Path(_entry("water")["filename"]).stem
    assert (OUT / f"{stem}_raw_text.txt").exists()
    assert (OUT / f"{stem}_result.json").exists()


def test_write_report_has_common_and_type_columns(tmp_path):
    cfg = rb.get_config("study")
    raw = json.dumps({"visual_evidence": ["open_textbook", "open_workbook"]})
    rec = rb.process_entry(_entry("study", 0), raw, cfg, OUT)
    report = tmp_path / "study_qwen_batch_report.csv"
    rb.write_report([rec], report)
    header = report.read_text(encoding="utf-8").splitlines()[0].split(",")
    for col in ("filename", "verification_type", "predicted_label", "visual_evidence",
                "exercise_activity_type", "image_id", "expected_decision", "expected_study_evidence",
                "result_output_path", "error"):
        assert col in header


# ---------------------------------------------------------------------------
# study scene dict/list 정규화
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scene,expected", [
    ("desk", "desk"),
    ({"name": "study_desk"}, "study_desk"),
    ({"description": "a desk with books"}, "a desk with books"),
    ([{"name": "library"}], "library"),
    (["reading_room", "x"], "reading_room"),
    (None, None),
])
def test_study_scene_dict_list_normalization(scene, expected):
    raw = {"scene": scene, "visual_evidence": ["open_textbook"]}
    norm = nqo.normalize_study_evidence(raw)
    assert norm["scene"] == expected
    assert norm["scene"] is None or isinstance(norm["scene"], str)
    # VisionAnalysis 통과
    from backend.database.schema.image_verification_schema import VisionAnalysis
    VisionAnalysis.model_validate(norm)


def test_study_dict_evidence_extracted():
    raw = {"visual_evidence": [{"name": "open_textbook", "description": "an open textbook"}]}
    norm = nqo.normalize_study_evidence(raw)
    assert "open_textbook" in norm["study_visual_evidence"]
