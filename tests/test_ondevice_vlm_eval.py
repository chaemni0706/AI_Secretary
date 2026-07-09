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

def test_load_candidates_has_expected_models():
    candidates = ov.load_candidates()
    assert len(candidates) == 8
    adapters = {c["adapter"] for c in candidates}
    assert adapters == {"minicpm_v", "minicpm_v2", "mobilevlm", "smolvlm", "smolvlm2_2b",
                        "qwen2vl_2b", "qwen_awq", "magicvl_2b"}
    for c in candidates:
        for field in ("model_name", "family", "parameter_size", "quantization_plan",
                      "android_feasibility", "notes", "model_size_mb", "runtime_target"):
            assert field in c, f"{c.get('model_name')} missing {field}"


def test_smolvlm2_candidate_registered():
    """SmolVLM2-2.2B 후보가 yaml 에서 로딩되고 필수 필드를 가진다."""
    cand = next(c for c in ov.load_candidates() if c["adapter"] == "smolvlm2_2b")
    assert cand["model_name"] == "SmolVLM2-2.2B-Instruct"
    assert cand["family"] == "SmolVLM2"
    assert cand["parameter_size"] == "2.2B"
    assert cand["model_id"] == "HuggingFaceTB/SmolVLM2-2.2B-Instruct"
    assert cand["model_path"] == "/data/models/SmolVLM2-2.2B-Instruct"
    assert int(cand["max_new_tokens"]) >= 64


def test_adapter_registry_keys():
    assert set(ADAPTER_REGISTRY) == {
        "minicpm_v", "minicpm_v2", "mobilevlm", "smolvlm", "smolvlm2_2b", "qwen2vl_2b",
        "qwen_awq", "magicvl_2b", "mock"}


def test_minicpm_v2_candidate_and_adapter():
    """MiniCPM-V 2.0 후보 로딩 + 레지스트리/서브클래스(모델 로딩 없음)."""
    cand = next(c for c in ov.load_candidates() if c["adapter"] == "minicpm_v2")
    assert cand["model_name"] == "MiniCPM-V-2.0"
    assert cand["model_id"] == "openbmb/MiniCPM-V-2"
    assert cand["parameter_size"] == "2.8B"
    from adapters.minicpm_v_adapter import MiniCPMV2Adapter, MiniCPMVAdapter
    assert ADAPTER_REGISTRY["minicpm_v2"] is MiniCPMV2Adapter
    assert issubclass(MiniCPMV2Adapter, MiniCPMVAdapter)
    assert (ONDEVICE / "smoke_test_minicpm_v2.py").exists()
    assert (ONDEVICE / "MINICPM_V2_RUNBOOK.md").exists()


def test_minicpm_and_magicvl_candidates_registered():
    cands = {c["adapter"]: c for c in ov.load_candidates()}
    m = cands["minicpm_v"]
    assert m["model_name"] == "MiniCPM-V-2.6" and m["family"] == "MiniCPM-V"
    assert m["model_id"] == "openbmb/MiniCPM-V-2_6"
    mv = cands["magicvl_2b"]
    assert mv["model_name"] == "MagicVL-2B" and mv["parameter_size"] == "2B"


def test_minicpm_magicvl_registry_and_files():
    from adapters.magicvl_adapter import MagicVLAdapter
    from adapters.minicpm_v_adapter import MiniCPMVAdapter
    assert ADAPTER_REGISTRY["minicpm_v"] is MiniCPMVAdapter
    assert ADAPTER_REGISTRY["magicvl_2b"] is MagicVLAdapter
    for f in ("smoke_test_minicpm_v.py", "smoke_test_magicvl.py", "MINICPM_MAGICVL_RUNBOOK.md"):
        assert (ONDEVICE / f).exists()


def test_qwen2vl_2b_candidate_registered():
    """Qwen2-VL-2B-AWQ 후보가 yaml 에서 로딩되고 필수 필드를 가진다."""
    cand = next(c for c in ov.load_candidates() if c["adapter"] == "qwen2vl_2b")
    assert cand["model_name"] == "Qwen2-VL-2B-AWQ"
    assert cand["family"] == "Qwen2-VL"
    assert cand["parameter_size"] == "2B"
    assert cand["model_id"] == "Qwen/Qwen2-VL-2B-Instruct-AWQ"
    assert cand["model_path"] == "/data/models/Qwen2-VL-2B-Instruct-AWQ"


def test_qwen2vl_2b_registry_maps_to_subclass():
    """qwen2vl_2b → Qwen2VL2BAdapter(QwenAWQAdapter 상속). 인스턴스화하지 않아 모델 로딩 없음."""
    from adapters.qwen_awq_adapter import Qwen2VL2BAdapter, QwenAWQAdapter
    assert ADAPTER_REGISTRY["qwen2vl_2b"] is Qwen2VL2BAdapter
    assert issubclass(Qwen2VL2BAdapter, QwenAWQAdapter)
    # 3B 기본값과 분리 확인(로딩 없이 클래스 속성만)
    assert Qwen2VL2BAdapter.HF_MODEL_ID == "Qwen/Qwen2-VL-2B-Instruct-AWQ"
    assert ADAPTER_REGISTRY["qwen_awq"].HF_MODEL_ID == "Qwen/Qwen2.5-VL-3B-Instruct-AWQ"


def test_qwen2vl_2b_smoke_and_runbook_exist():
    assert (ONDEVICE / "smoke_test_qwen2vl_2b.py").exists()
    assert (ONDEVICE / "QWEN2VL_2B_RUNBOOK.md").exists()


def test_smolvlm2_registry_maps_to_subclass():
    """smolvlm2_2b → SmolVLM2Adapter(SmolVLMAdapter 상속). 인스턴스화하지 않아 모델 로딩 없음."""
    from adapters.smolvlm_adapter import SmolVLM2Adapter, SmolVLMAdapter
    assert ADAPTER_REGISTRY["smolvlm2_2b"] is SmolVLM2Adapter
    assert issubclass(SmolVLM2Adapter, SmolVLMAdapter)
    # 기존 500M 매핑은 유지
    assert ADAPTER_REGISTRY["smolvlm"] is SmolVLMAdapter


def test_smolvlm2_smoke_script_exists():
    assert (ONDEVICE / "smoke_test_smolvlm2.py").exists()
    assert (ONDEVICE / "SMOLVLM2_RUNBOOK.md").exists()
    assert (ONDEVICE / "MODEL_SELECTION.md").exists()


def test_qwen_awq_candidate_registered():
    """Qwen2.5-VL-3B-AWQ 후보가 yaml 에서 로딩되고 model_id/path 를 가진다."""
    cand = next(c for c in ov.load_candidates() if c["adapter"] == "qwen_awq")
    assert cand["model_name"] == "Qwen2.5-VL-3B-AWQ"
    assert cand["family"] == "Qwen2.5-VL"
    assert cand["parameter_size"] == "3B"
    assert cand["model_id"] == "Qwen/Qwen2.5-VL-3B-Instruct-AWQ"
    assert cand["model_path"] == "/data/models/Qwen2.5-VL-3B-Instruct-AWQ"
    assert int(cand["max_new_tokens"]) >= 64


def test_qwen_awq_registry_maps_to_adapter():
    """qwen_awq → QwenAWQAdapter. 인스턴스화하지 않아 모델 로딩 없음."""
    from adapters.qwen_awq_adapter import QwenAWQAdapter
    assert ADAPTER_REGISTRY["qwen_awq"] is QwenAWQAdapter


def test_qwen_awq_smoke_script_exists():
    assert (ONDEVICE / "smoke_test_qwen_awq.py").exists()
    assert (ONDEVICE / "QWEN_AWQ_RUNBOOK.md").exists()


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


# ---------------------------------------------------------------------------
# SmolVLM 2차 evidence 추출 (복수 label / 문구 매핑; 모델 로드 없이)
# ---------------------------------------------------------------------------

from adapters.smolvlm_adapter import (  # noqa: E402
    extract_water_labels,
    normalize_water_label,
    to_vision_analysis,
)
from backend.database.schema.image_verification_schema import (  # noqa: E402
    ImageVerificationContext,
    VisionAnalysis,
)
from backend.services.image_verification_rule_engine import evaluate_image_verification  # noqa: E402


def _verdict(raw_text: str) -> str:
    va = VisionAnalysis.model_validate(to_vision_analysis(raw_text, "water"))
    return evaluate_image_verification("water", va, ImageVerificationContext()).result


@pytest.mark.parametrize("raw,expected", [
    ("visible_water.", "visible_water"),
    ("Assistant: visible_water.", "visible_water"),
    ("Empty container", "empty_container"),
    ("unknown", "insufficient_evidence"),
])
def test_smolvlm_single_label_parser_backward_compat(raw, expected):
    # normalize_water_label(단답 1개) 유틸은 유지된다.
    assert normalize_water_label(raw) == expected


@pytest.mark.parametrize("raw,must_have", [
    ("full glass of water", {"container_present", "visible_water", "filled_container"}),
    ("half glass of water", {"container_present", "visible_water", "filled_container"}),
    ("clear liquid in glass", {"container_present", "visible_clear_liquid", "filled_container"}),
    ("water bottle with water", {"container_present", "visible_water", "filled_container"}),
    ("container_present, visible_water, filled_container", {"container_present", "visible_water", "filled_container"}),
    ("empty glass", {"empty_container"}),
    ("a cup of coffee", {"non_water_beverage"}),
])
def test_smolvlm_multi_label_extraction(raw, must_have):
    labels, _ = extract_water_labels(raw)
    assert must_have.issubset(labels)


@pytest.mark.parametrize("raw,expected", [
    ("empty", []),                                                    # 단독 empty → 라벨 없음
    ("empty glass", ["empty_container"]),                             # 명확한 빈 상태만 empty
    ("water bottle with water", ["visible_water", "filled_container"]),  # 물 존재 명시 → positive
    ("clear glass filled with water", ["visible_water", "filled_container"]),
])
def test_smolvlm_water_empty_mapping_fixed(raw, expected):
    """단독 'empty' 는 매핑되지 않고, 명확한 빈 상태 표현에서만 empty_container 가 나온다."""
    ev = to_vision_analysis(raw, "water")["water_visual_evidence"]
    assert set(ev) == set(expected)


@pytest.mark.parametrize("raw", [
    "water bottle",          # 용기 '이름'만 → 물 근거 아님
    "water glass",
    "a glass for water",
    "an empty water bottle",  # 이름에 water 가 있어도 empty 면 물 근거 아님
    "transparent glass",
    "clear container",
    "glass on table",
    "a bottle",
])
def test_smolvlm_water_container_name_alone_is_not_water(raw):
    """용기 존재/이름만으로 water_visual_evidence 를 만들지 않는다(FP 방지)."""
    ev = to_vision_analysis(raw, "water")["water_visual_evidence"]
    assert "visible_water" not in ev and "filled_container" not in ev


# 실제 물 인식 파이프라인(파서→Rule Engine)의 FP=0 회귀 방지: positive→verified, negative→not verified.
@pytest.mark.parametrize("raw", [
    "a glass of water", "clear glass filled with water", "water bottle with water",
    "bottle of water", "person holding water",
])
def test_water_positive_verifies(raw):
    assert _verdict(raw) == "verified"


@pytest.mark.parametrize("raw", [
    "empty glass", "empty bottle", "an empty water bottle", "a cup of coffee", "a mug of tea",
    "a glass of juice", "transparent empty container", "water bottle", "water glass", "glass on table",
])
def test_water_negative_never_verifies(raw):
    """FP=0: 빈 용기/타 음료/용기 이름만 있는 경우 절대 verified 금지."""
    assert _verdict(raw) != "verified"


def test_smolvlm_water_prompt_has_no_negative_injection():
    """water 프롬프트에 'empty' 부정어를 주입하지 않는다(소형 모델 parroting 방지)."""
    from adapters.smolvlm_adapter import build_prompt
    prompt = build_prompt("water").lower()
    assert "empty" not in prompt
    assert "partly full" not in prompt
    # 프롬프트 전체가 그대로 echo 되어도 empty_container 가 생기지 않아야 한다.
    assert "empty_container" not in to_vision_analysis(build_prompt("water"), "water")["water_visual_evidence"]


def test_smolvlm_standalone_container_words_are_not_empty():
    """bottle/cup/container 단독은 empty 로도 positive 로도 매핑되지 않는다."""
    for raw in ("bottle", "cup", "container", "a transparent bottle"):
        assert to_vision_analysis(raw, "water")["water_visual_evidence"] == []


def test_smolvlm_to_vision_analysis_multi_evidence_schema_valid():
    va = to_vision_analysis("full glass of water", "water")
    assert {"visible_water", "filled_container"}.issubset(set(va["water_visual_evidence"]))
    assert va["objects"] and va["objects"][0]["label"] in {"glass", "cup", "water_bottle", "tumbler"}
    VisionAnalysis.model_validate(va)


def test_smolvlm_insufficient_maps_to_empty_evidence():
    va = to_vision_analysis("unknown", "water")
    assert va["water_visual_evidence"] == []  # insufficient → 빈 리스트
    VisionAnalysis.model_validate(va)


def test_smolvlm_2nd_gen_recovers_pass_but_blocks_negatives():
    """2차: 복합 근거로 실제 물컵은 PASS 복구, 빈 컵/커피는 PASS 금지 (FP=0 유지). 최종 판정은 Rule Engine."""
    assert _verdict("full glass of water") == "verified"
    assert _verdict("filled_container") == "verified"        # filled → 컨테이너+물 함의
    assert _verdict("empty glass") == "rejected"             # 빈 컵 → PASS 아님
    assert _verdict("a cup of coffee") == "rejected"         # 색 음료 → PASS 아님
    assert _verdict("unknown") != "verified"                  # 근거 부족 → PASS 아님


def test_smolvlm_container_only_is_not_pass():
    """컨테이너만 있고 물 근거가 없으면 PASS 금지."""
    va = VisionAnalysis.model_validate(to_vision_analysis("container_present", "water"))
    assert evaluate_image_verification("water", va, ImageVerificationContext()).result != "verified"


# ---------------------------------------------------------------------------
# SmolVLM exercise 서술 → gym/home evidence 추출 (모델 로드 없이)
# ---------------------------------------------------------------------------

def _ex_verdict(raw_text: str, activity: str) -> str:
    va = VisionAnalysis.model_validate(
        to_vision_analysis(raw_text, "exercise", {"exercise_activity_type": activity})
    )
    return evaluate_image_verification(
        "exercise", va, ImageVerificationContext(exercise_activity_type=activity)
    ).result


def test_smolvlm_exercise_gym_equipment_pass():
    # 기구가 보이면 gym_environment 를 보강해 PASS (Rule Engine 판정)
    assert _ex_verdict("dumbbells in a gym", "gym") == "verified"
    assert _ex_verdict("a treadmill", "gym") == "verified"
    assert _ex_verdict("a weight bench with a barbell", "gym") == "verified"


def test_smolvlm_exercise_home_pass():
    assert _ex_verdict("a yoga mat on the floor", "home_workout") == "verified"
    assert _ex_verdict("a resistance band", "home_workout") == "verified"
    assert _ex_verdict("a person doing a squat", "home_workout") == "verified"


def test_smolvlm_exercise_unrelated_and_insufficient_not_pass():
    assert _ex_verdict("an office desk with a laptop", "gym") != "verified"
    assert _ex_verdict("a bedroom", "gym") != "verified"
    assert _ex_verdict("a plate of food", "gym") != "verified"
    assert _ex_verdict("running shoes only", "home_workout") != "verified"
    assert _ex_verdict("a water bottle", "gym") != "verified"
    assert _ex_verdict("an empty room", "home_workout") != "verified"


def test_smolvlm_exercise_gym_env_only_is_not_pass():
    # "Gym." 처럼 환경만 있고 기구가 없으면 PASS 금지 (기구 근거 필요)
    assert _ex_verdict("gym", "gym") != "verified"


# ---------------------------------------------------------------------------
# SmolVLM study 서술 → study evidence 추출 (모델 로드 없이)
# ---------------------------------------------------------------------------

def _st_verdict(raw_text: str) -> str:
    va = VisionAnalysis.model_validate(to_vision_analysis(raw_text, "study"))
    return evaluate_image_verification("study", va, ImageVerificationContext()).result


def test_smolvlm_study_content_pass():
    assert _st_verdict("an open textbook with handwritten notes") == "verified"
    assert _st_verdict("a coding screen") == "verified"
    assert _st_verdict("a lecture video on a laptop") == "verified"
    assert _st_verdict("a highlighted textbook") == "verified"


def test_smolvlm_study_non_study_rejected():
    assert _st_verdict("playing a video game") == "rejected"
    assert _st_verdict("watching YouTube") == "rejected"
    assert _st_verdict("Instagram social media") == "rejected"
    assert _st_verdict("online shopping") == "rejected"


def test_smolvlm_study_device_only_not_pass():
    # 노트북/모니터만/닫힌 책 → PASS 금지 (retake 쪽)
    assert _st_verdict("just a closed laptop") != "verified"
    assert _st_verdict("a blank monitor") != "verified"
    assert _st_verdict("a textbook") != "verified"  # 단일 근거만으론 점수 부족 → 미verified
