"""backend 로컬 VLM analyzer 연결 + Qwen7B 범용 fallback 재판정 테스트 (경량, 모델 로딩 없음).

- 기본 provider 가 OpenAI 가 아니라 로컬(smolvlm)로 선택되는지
- 어댑터 정규화 dict → VisionAnalysis 변환(evidence 유지 / object allowed 필터 / _raw_text 제거)
- _smol_immediate_stop 판단 로직(오늘 production patch: study 전용 → 3-task 공용 라우팅으로 교체)
- verify_image_upload 의 fallback 재판정 경로(Smol 근거 부족/불확실 → Qwen7B 결과로 Rule Engine 재판정)

torch/모델 없이 동작: 1차 provider(로컬)는 이 환경에서 available()=False → unusable 로 안전 처리되고
("Local VLM 'smolvlm' is not loaded." 는 infra failure 마커에 해당해 fallback 을 강제 트리거한다),
fallback analyzer 는 테스트가 MockVisionAnalyzer 로 주입한다(fallback_analyzer= 또는 하위호환
study_fallback_analyzer=).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from backend.services.image_verification_rules_loader import allowed_labels
from backend.services.local_vlm_analyzer import LocalVLMVisionAnalyzer, _dict_to_vision_analysis
from backend.services.vision_analyzer import (
    MockVisionAnalyzer,
    OpenAIVisionAnalyzer,
    get_default_vision_analyzer,
    get_study_fallback_analyzer,
)
from backend.database.schema.image_verification_schema import (
    ImageObjectObservation,
    ImageQuality,
    VisionAnalysis,
)

ROOT = Path(__file__).resolve().parents[1]
STUDY_IMG = ROOT / "local_eval" / "study_verification_fixture_pack" / "images" / "study_02.png"


def test_default_provider_is_local_not_openai():
    analyzer = get_default_vision_analyzer()
    assert isinstance(analyzer, LocalVLMVisionAnalyzer)
    assert analyzer.provider_key == "smolvlm"
    assert not isinstance(analyzer, OpenAIVisionAnalyzer)


def test_study_fallback_provider_is_qwen_awq():
    fb = get_study_fallback_analyzer()
    assert isinstance(fb, LocalVLMVisionAnalyzer)
    assert fb.provider_key == "qwen_awq"


def test_dict_to_vision_analysis_keeps_evidence_filters_objects():
    d = {
        "quality": {"brightness": "normal", "blur": "low", "usable": True, "issues": []},
        "scene": None,
        "objects": [{"label": "notebook", "confidence": 0.6, "evidence": None},
                    {"label": "unicorn", "confidence": 0.6, "evidence": None}],
        "visible_text": [], "visual_evidence": [],
        "study_visual_evidence": ["open_textbook", "handwritten_notes"],
        "water_visual_evidence": [], "exercise_visual_evidence": [],
        "_raw_text": "an open textbook with handwritten notes",
    }
    va = _dict_to_vision_analysis(d, allowed_labels("study"))
    assert va.quality.usable is True
    assert va.study_visual_evidence == ["open_textbook", "handwritten_notes"]
    assert [o.label for o in va.objects] == ["notebook"]  # unicorn(비허용) 제거, _raw_text 무시


def test_dict_to_vision_analysis_bad_payload_is_unusable():
    va = _dict_to_vision_analysis("not-a-dict", allowed_labels("study"))
    assert va.quality.usable is False


def test_local_analyzer_unavailable_returns_unusable_no_openai_message():
    """이 환경에선 로컬 모델 미로딩 → OpenAI 메시지가 아니라 로컬 unusable 메시지."""
    analyzer = get_default_vision_analyzer()
    if analyzer.available():
        pytest.skip("로컬 모델이 이미 로딩된 환경 — 이 케이스는 미로딩 전제")
    va = analyzer.analyze(STUDY_IMG, "study", allowed_labels("study"))
    assert va.quality.usable is False
    assert not any("OpenAI API key" in i for i in va.quality.issues)


# --- _smol_immediate_stop 판단 로직 (3-task 공용 라우팅) ---

from backend.services.image_verification_service import _smol_immediate_stop, verify_image_upload
from backend.database.schema.image_verification_schema import ImageVerificationData, RuleEvidence, RuleScoreBreakdown


def _mk_result(task, result, codes, study_ev=None, quality_usable=True, quality_issues=None):
    data = ImageVerificationData(
        verification_type=task, result=result, score=0, mandatory_passed=False,
        score_breakdown=RuleScoreBreakdown(),
        vlm_analysis=VisionAnalysis(
            study_visual_evidence=study_ev or [],
            quality=ImageQuality(usable=quality_usable, issues=quality_issues or []),
        ),
        rule_evidence=[RuleEvidence(code=c, message="") for c in codes],
    )
    return data


@pytest.mark.parametrize("task,result,codes,quality_usable,quality_issues,expected_stop", [
    # verified 는 절대 즉시-정지 대상이 아님 -- Smol 단독 verified 는 항상 Qwen7B 로 escalate 된다.
    ("study", "verified", [], True, [], False),
    ("water", "verified", [], True, [], False),
    # 명확한 strong blocker -> 즉시 정지(추가 Qwen7B 호출 불필요)
    ("water", "rejected", ["water_priority:empty_container"], True, [], True),
    ("study", "rejected", ["study_priority:gaming_content"], True, [], True),
    ("exercise", "rejected", ["exercise_priority:unrelated_environment"], True, [], True),
    # 근거 부족/불확실(strong blocker 아님) -> escalate(정지 아님)
    ("study", "retake_required", ["study_pattern_missing"], True, [], False),
    ("water", "retake_required", ["water_pattern_missing"], True, [], False),
    # 진짜 이미지 품질 문제(quality_unusable, infra 실패 아님) -> 즉시 정지
    ("study", "retake_required", ["quality_unusable"], False, ["image is blurry"], True),
    # quality.usable=False 지만 "모델 미로딩" 같은 infra 실패 마커 -> 정지 아님, escalate 되어야 함
    ("study", "retake_required", ["quality_unusable"], False, ["Local VLM 'smolvlm' is not loaded."], False),
    ("water", "retake_required", ["quality_unusable"], False, ["Qwen7B inference error: RuntimeError"], False),
])
def test_smol_immediate_stop(task, result, codes, quality_usable, quality_issues, expected_stop):
    data = _mk_result(task, result, codes, quality_usable=quality_usable, quality_issues=quality_issues)
    stop, _reason = _smol_immediate_stop(task, data)
    assert stop is expected_stop


def test_verify_image_upload_fallback_reevaluates():
    """Smol(기본 로컬, 이 환경에서는 미로딩=infra 실패)이 근거 부족/미로딩이면
    주입된 fallback(Qwen7B 대역)의 evidence 와 병합해 Rule Engine 이 재판정한다."""
    if not STUDY_IMG.exists():
        pytest.skip("study fixture 이미지 없음")
    strong = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="notebook", confidence=0.7),
                 ImageObjectObservation(label="pen", confidence=0.7),
                 ImageObjectObservation(label="desk", confidence=0.7)],
        study_visual_evidence=["open_textbook", "handwritten_notes", "problem_solving_material"],
        model_name="qwen7b-mock",
    )
    fallback = MockVisionAnalyzer(strong)
    with STUDY_IMG.open("rb") as f:
        data = verify_image_upload(
            f, filename="study_02.png", content_type="image/png",
            verification_type="study", analyzer=None, fallback_analyzer=fallback,
        )
    # fallback 의 evidence 가 병합되어 채워져야 한다(OpenAI 메시지 없음).
    assert data.vlm_analysis.study_visual_evidence  # 비어있지 않음
    assert not any("OpenAI API key" in i for i in data.vlm_analysis.quality.issues)
    assert data.engine_used == "smol_plus_qwen7b"


def test_verify_image_upload_fallback_reevaluates_backward_compat_param_name():
    """하위호환: study_fallback_analyzer= 이름으로도 여전히 동작한다."""
    if not STUDY_IMG.exists():
        pytest.skip("study fixture 이미지 없음")
    strong = VisionAnalysis(
        quality=ImageQuality(usable=True),
        study_visual_evidence=["open_textbook", "handwritten_notes"],
        model_name="qwen7b-mock",
    )
    fallback = MockVisionAnalyzer(strong)
    with STUDY_IMG.open("rb") as f:
        data = verify_image_upload(
            f, filename="study_02.png", content_type="image/png",
            verification_type="study", analyzer=None, study_fallback_analyzer=fallback,
        )
    assert data.vlm_analysis.study_visual_evidence
