"""On-device VLM 평가 구조 테스트 (실제 모델 없이 통과).

- 후보 로딩 / adapter registry
- 실제 adapter는 available()=False, analyze()는 ModelNotAvailable
- MockAdapter는 픽스처를 반환
- water/exercise/study 평가 아이템 로딩 (wakeup 제외)
- simulate 모드 evaluate_model → CSV 컬럼/ok/false_positive
- no-simulate 모드 → SKIPPED
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ONDEVICE = ROOT / "local_eval" / "ondevice_vlm_eval"
sys.path.insert(0, str(ONDEVICE))

import run_ondevice_eval as ov  # noqa: E402
from adapters import (  # noqa: E402
    ADAPTER_REGISTRY,
    MiniCPMVAdapter,
    MockAdapter,
    ModelNotAvailable,
    build_adapter,
    empty_vision_analysis,
)


# ---------------------------------------------------------------------------
# 후보 / adapter
# ---------------------------------------------------------------------------

def test_load_candidates_has_four_models():
    candidates = ov.load_candidates()
    assert len(candidates) == 4
    adapters = {c["adapter"] for c in candidates}
    assert adapters == {"minicpm_v", "mobilevlm", "smolvlm", "qwen_awq"}
    for c in candidates:
        for field in ("model_name", "family", "parameter_size", "quantization_plan",
                      "android_feasibility", "notes", "model_size_mb", "runtime_target"):
            assert field in c, f"{c.get('model_name')} missing {field}"


def test_adapter_registry_keys():
    assert set(ADAPTER_REGISTRY) == {"minicpm_v", "mobilevlm", "smolvlm", "qwen_awq", "mock"}


@pytest.mark.parametrize("key", ["minicpm_v", "mobilevlm", "smolvlm", "qwen_awq"])
def test_real_adapters_not_available_and_raise(key):
    adapter = build_adapter(key, meta={"model_name": key})
    assert adapter.available() is False
    with pytest.raises(ModelNotAvailable):
        adapter.analyze(Path("x.png"), "water", None)


def test_mock_adapter_returns_fixture():
    fixture = {"quality": {"usable": True}, "objects": [], "water_visual_evidence": ["visible_water"]}
    adapter = build_adapter("mock", meta={"model_name": "mock"},
                            fixture_lookup=lambda k: fixture if k == "a.png" else None)
    assert adapter.available() is True
    assert adapter.analyze(Path("/tmp/a.png"), "water", None)["water_visual_evidence"] == ["visible_water"]
    # 없는 파일 → 빈 분석
    assert adapter.analyze(Path("/tmp/none.png"), "water", None) == empty_vision_analysis()


def test_build_mock_requires_fixture_lookup():
    with pytest.raises(ValueError):
        build_adapter("mock", meta={})


def test_unknown_adapter_key_raises():
    with pytest.raises(KeyError):
        build_adapter("nope")


# ---------------------------------------------------------------------------
# 평가 아이템 로딩 (wakeup 제외)
# ---------------------------------------------------------------------------

def test_load_eval_items_counts():
    items = ov.load_eval_items(["water", "exercise", "study"])
    by_type = {}
    for it in items:
        by_type.setdefault(it["verification_type"], 0)
        by_type[it["verification_type"]] += 1
    assert by_type == {"water": 18, "exercise": 12, "study": 10}
    # 각 아이템은 fixture(vision_analysis)와 expected_label을 가진다
    for it in items:
        assert it["fixture"] is not None
        assert it["expected_label"] in {"PASS", "FAIL", "BORDERLINE"}


def test_wakeup_is_not_a_verification_type():
    assert "wakeup" not in ov.VERIFICATION_TYPES


# ---------------------------------------------------------------------------
# evaluate_model
# ---------------------------------------------------------------------------

def _candidate(adapter="minicpm_v"):
    return next(c for c in ov.load_candidates() if c["adapter"] == adapter)


def test_evaluate_model_simulate_produces_rows_with_all_columns():
    items = ov.load_eval_items(["water"])
    fixture_lookup = {it["filename"]: it["fixture"] for it in items}.get
    rows = ov.evaluate_model(_candidate("mobilevlm"), items, fixture_lookup, simulate=True)
    assert len(rows) == len(items)
    for r in rows:
        assert set(r.keys()) >= set(ov.CSV_FIELDS)
        assert r["model_name"] == "MobileVLM-V2-1.7B"
        assert r["predicted_label"] in {"PASS", "FAIL", "BORDERLINE_CASE"}
    # 픽스처 = '완벽한 모델' → water는 전부 기대와 일치, false positive 0
    assert all(r["ok"] for r in rows)
    assert not any(r["false_positive"] for r in rows)


def test_evaluate_model_simulate_water_04_empty_glasses_not_pass():
    """빈 컵 2개(false positive 위험)는 시뮬레이션에서도 PASS가 아니어야 한다."""
    items = [it for it in ov.load_eval_items(["water"]) if it["filename"] == "water_test_04.png"]
    fixture_lookup = {it["filename"]: it["fixture"] for it in items}.get
    rows = ov.evaluate_model(_candidate("qwen_awq"), items, fixture_lookup, simulate=True)
    assert rows[0]["predicted_label"] != "PASS"
    assert rows[0]["false_positive"] is False


def test_evaluate_model_no_simulate_marks_skipped():
    items = ov.load_eval_items(["study"])[:2]
    fixture_lookup = {it["filename"]: it["fixture"] for it in items}.get
    rows = ov.evaluate_model(_candidate("smolvlm"), items, fixture_lookup, simulate=False)
    assert all(r["predicted_label"] == "SKIPPED" for r in rows)
    assert all(r["engine_result"] == "model_not_available" for r in rows)


def test_write_report_header(tmp_path):
    items = ov.load_eval_items(["exercise"])[:3]
    fixture_lookup = {it["filename"]: it["fixture"] for it in items}.get
    rows = ov.evaluate_model(_candidate("minicpm_v"), items, fixture_lookup, simulate=True)
    out = tmp_path / "report.csv"
    ov.write_report(rows, out)
    header = out.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == ov.CSV_FIELDS
