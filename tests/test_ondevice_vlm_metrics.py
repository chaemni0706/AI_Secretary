"""On-device VLM 정량 지표 저장 구조 테스트 (실제 모델 없이 simulate).

- run 폴더에 파일들이 생성되는지
- metrics_summary.csv/json 생성 + 컬럼
- confusion matrix 계산
- false_positive 계산
- error_cases.csv 생성
- experiment_report.md 생성
- wakeup이 포함되지 않는지
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ONDEVICE = ROOT / "local_eval" / "ondevice_vlm_eval"
sys.path.insert(0, str(ONDEVICE))

import run_ondevice_eval as ov  # noqa: E402


@pytest.fixture
def run_dir(tmp_path):
    """simulate 모드로 전체 실험을 tmp 폴더에서 1회 실행."""
    result = ov.run_experiment(
        models_only=["mobilevlm", "qwen_awq"],
        types=["water", "exercise", "study"],
        simulate=True,
        base_dir=tmp_path,
    )
    return Path(result["run_dir"])


EXPECTED_FILES = [
    "per_image_report.csv",
    "predictions.jsonl",
    "metrics_summary.csv",
    "metrics_summary.json",
    "confusion_matrix.csv",
    "latency_summary.csv",
    "error_cases.csv",
    "experiment_report.md",
]


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# 파일 생성
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", EXPECTED_FILES)
def test_run_produces_file(run_dir, name):
    assert (run_dir / name).exists(), f"missing {name}"


def test_run_produces_output_dirs(run_dir):
    assert (run_dir / "raw_outputs").is_dir()
    assert (run_dir / "normalized_outputs").is_dir()
    # simulate 에서는 normalized_outputs 에 파일이 쌓인다
    assert list((run_dir / "normalized_outputs").glob("*.json"))


def test_run_id_encodes_models_and_types(run_dir):
    name = run_dir.name
    assert "mobilevlm" in name and "qwen_awq" in name
    assert "water" in name and "exercise" in name and "study" in name


# ---------------------------------------------------------------------------
# per_image_report 컬럼 / predictions
# ---------------------------------------------------------------------------

def test_per_image_columns(run_dir):
    rows = _read_csv(run_dir / "per_image_report.csv")
    assert rows
    for col in ("run_id", "timestamp", "model_name", "model_path", "verification_type",
                "false_positive", "false_negative", "latency_ms", "model_load_time_ms",
                "peak_gpu_memory_mb", "normalized_output_path", "error"):
        assert col in rows[0], f"per_image missing {col}"
    # 2 models × 40 items
    assert len(rows) == 80


def test_predictions_jsonl_parses(run_dir):
    lines = (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 80
    obj = json.loads(lines[0])
    assert "predicted_label" in obj and "verification_type" in obj


# ---------------------------------------------------------------------------
# metrics_summary
# ---------------------------------------------------------------------------

def test_metrics_summary_csv_and_json(run_dir):
    rows = _read_csv(run_dir / "metrics_summary.csv")
    assert rows
    for col in ov.METRICS_FIELDS:
        assert col in rows[0]
    js = json.loads((run_dir / "metrics_summary.json").read_text(encoding="utf-8"))
    assert isinstance(js, list) and js
    # 모델별 ALL 롤업이 포함되어야 한다
    assert any(m["verification_type"] == "ALL" for m in js)
    # 인증타입별 행도 존재
    assert any(m["verification_type"] == "water" for m in js)


def test_metrics_accuracy_and_fp_zero_in_simulate(run_dir):
    js = json.loads((run_dir / "metrics_summary.json").read_text(encoding="utf-8"))
    for m in js:
        # simulate=픽스처=완벽한 모델 → accuracy 1.0, false positive 0
        assert m["accuracy"] == 1.0, m
        assert m["fp"] == 0, m


# ---------------------------------------------------------------------------
# confusion matrix 계산
# ---------------------------------------------------------------------------

def test_confusion_matrix_counts(run_dir):
    rows = _read_csv(run_dir / "confusion_matrix.csv")
    # 2 models × 3 types
    assert len(rows) == 6
    water = [r for r in rows if r["verification_type"] == "water"][0]
    # water: PASS 기대 11장(tp), 비-PASS 7장(tn), fp/fn 0
    assert int(water["tp"]) == 11
    assert int(water["tn"]) == 7
    assert int(water["fp"]) == 0
    assert int(water["fn"]) == 0


def test_confusion_matches_num_samples(run_dir):
    for r in _read_csv(run_dir / "confusion_matrix.csv"):
        total = int(r["tp"]) + int(r["tn"]) + int(r["fp"]) + int(r["fn"])
        assert total > 0


# ---------------------------------------------------------------------------
# false_positive 계산 (직접 confusion 함수 단위 확인)
# ---------------------------------------------------------------------------

def test_confusion_function_fp_and_fn():
    rows = [
        {"expected_label": "FAIL", "predicted_label": "PASS"},   # fp
        {"expected_label": "PASS", "predicted_label": "FAIL"},   # fn
        {"expected_label": "PASS", "predicted_label": "PASS"},   # tp
        {"expected_label": "BORDERLINE", "predicted_label": "BORDERLINE_CASE"},  # tn
    ]
    cm = ov._confusion(rows)
    assert cm == {"tp": 1, "tn": 1, "fp": 1, "fn": 1}


# ---------------------------------------------------------------------------
# error_cases / experiment_report
# ---------------------------------------------------------------------------

def test_error_cases_file_exists_and_has_header(run_dir):
    path = run_dir / "error_cases.csv"
    assert path.exists()
    text = path.read_text(encoding="utf-8").splitlines()
    assert text[0].split(",")[0] == "run_id"  # 헤더 존재


def test_error_cases_includes_false_positives_when_present():
    # FP가 있는 인위적 rows에서 error_cases 가 FP를 포함하는지
    rows = [
        {**_blank(), "ok": True, "false_positive": False, "error": ""},
        {**_blank(), "ok": False, "false_positive": True, "error": ""},   # FP → 포함
        {**_blank(), "ok": False, "false_positive": False, "error": "boom"},  # error → 포함
    ]
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "error_cases.csv"
        err = ov.write_error_cases(rows, out)
        assert len(err) == 2
        assert any(r["false_positive"] for r in err)


def test_experiment_report_mentions_false_positive(run_dir):
    md = (run_dir / "experiment_report.md").read_text(encoding="utf-8")
    assert "false positive" in md.lower()
    assert "MobileVLM" in md or "Qwen" in md


# ---------------------------------------------------------------------------
# wakeup 제외
# ---------------------------------------------------------------------------

def test_wakeup_rejected_by_run_experiment(tmp_path):
    with pytest.raises(ValueError):
        ov.run_experiment(models_only=["mobilevlm"], types=["wakeup"], simulate=True, base_dir=tmp_path)


def test_wakeup_never_in_verification_types():
    assert "wakeup" not in ov.VERIFICATION_TYPES


def test_no_wakeup_rows_in_report(run_dir):
    rows = _read_csv(run_dir / "per_image_report.csv")
    assert all(r["verification_type"] in {"water", "exercise", "study"} for r in rows)


def _blank() -> dict:
    return {k: "" for k in ov.CSV_FIELDS}
