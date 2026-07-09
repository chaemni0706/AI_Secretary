"""backend 로컬 VLM analyzer 연결 + study fallback 재판정 테스트 (경량, 모델 로딩 없음).

- 기본 provider 가 OpenAI 가 아니라 로컬(smolvlm)로 선택되는지
- 어댑터 정규화 dict → VisionAnalysis 변환(evidence 유지 / object allowed 필터 / _raw_text 제거)
- _should_study_fallback 판단 로직
- verify_image_upload 의 study fallback 재판정 경로(1차 근거 부족 → fallback 결과로 Rule Engine 재판정)

torch/모델 없이 동작: 1차 provider(로컬)는 이 환경에서 available()=False → unusable 로 안전 처리되고,
fallback analyzer 는 테스트가 MockVisionAnalyzer 로 주입한다.
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


# --- _should_study_fallback 판단 로직 ---

from backend.services.image_verification_service import _should_study_fallback, verify_image_upload
from backend.database.schema.image_verification_schema import ImageVerificationData, RuleEvidence, RuleScoreBreakdown


def _mk_result(result, codes, study_ev):
    data = ImageVerificationData(
        verification_type="study", result=result, score=0, mandatory_passed=False,
        score_breakdown=RuleScoreBreakdown(),
        vlm_analysis=VisionAnalysis(study_visual_evidence=study_ev),
        rule_evidence=[RuleEvidence(code=c, message="") for c in codes],
    )
    return data, data.vlm_analysis


@pytest.mark.parametrize("result,codes,study_ev,expected", [
    ("verified", [], ["open_textbook"], False),                       # 통과 → fallback 불필요
    ("verified", [], ["open_textbook", "handwritten_notes"], False),  # 통과 → fallback 불필요
    ("retake_required", ["study_pattern_missing"], [], True),         # 근거 없음
    ("retake_required", ["quality_unusable"], ["open_textbook"], True),   # 트리거 코드
    ("retake_required", ["study_priority:uncertain_screen_content"], ["uncertain_screen_content"], True),
    # 근거가 2개 미만이면(예: handwritten_notes 1개만) 비트리거 코드여도 상위 모델로 재확인
    ("retake_required", ["gps"], ["open_textbook"], True),
    ("rejected", ["study_pattern_missing"], ["open_textbook"], True),
    # 근거 2개 이상 + 비트리거 코드 → fallback 안함(불필요한 Qwen 호출 방지)
    ("rejected", ["gps"], ["open_textbook", "handwritten_notes"], False),
    ("retake_required", ["gps"], ["open_textbook", "lecture_video"], False),
])
def test_should_study_fallback(result, codes, study_ev, expected):
    res, analysis = _mk_result(result, codes, study_ev)
    assert _should_study_fallback(res, analysis) is expected


def test_verify_image_upload_study_fallback_reevaluates():
    """1차(기본 로컬)가 근거 부족이면 주입된 fallback 결과로 Rule Engine 재판정한다."""
    if not STUDY_IMG.exists():
        pytest.skip("study fixture 이미지 없음")
    strong = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="notebook", confidence=0.7),
                 ImageObjectObservation(label="pen", confidence=0.7),
                 ImageObjectObservation(label="desk", confidence=0.7)],
        study_visual_evidence=["open_textbook", "handwritten_notes", "problem_solving_material"],
    )
    fallback = MockVisionAnalyzer(strong)
    with STUDY_IMG.open("rb") as f:
        data = verify_image_upload(
            f, filename="study_02.png", content_type="image/png",
            verification_type="study", analyzer=None, study_fallback_analyzer=fallback,
        )
    # fallback 의 VisionAnalysis 로 재판정되어 study 근거가 채워져야 한다(OpenAI 메시지 없음).
    assert data.vlm_analysis.study_visual_evidence  # 비어있지 않음
    assert not any("OpenAI API key" in i for i in data.vlm_analysis.quality.issues)
