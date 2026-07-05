"""Water 인증 테스트셋에 대한 pytest.

무엇을 검증하나
--------------
1. 매니페스트 무결성: 18장(uploaded 8 + generated 10), 필수 필드, 이미지 파일 존재.
2. 견고한 판정 파서(water_verdict): "PASS/FAIL", "true/false", "물 있음/물 없음",
   "인증 가능/인증 불가", dict/bool/VisionAnalysis 등 어떤 출력이 와도 표준 라벨로 정규화.
3. VLM 판독 흐름(Qwen 증거 → normalize_water_output → Rule Engine)의 PASS/FAIL 판정이
   각 이미지의 기대 라벨과 일치하는지.
4. "컵이 있다"는 이유만으로 PASS하지 않는지(빈 컵/색 음료/근거 부족은 FAIL).
5. BORDERLINE(닫힌/불투명 병 등)은 PASS/FAIL과 분리해 borderline_cases로 기록.

이미지 준비 (테스트 실행 전 자동 처리)
-----------------------------------
generated/ 이미지가 없으면 세션 시작 시 아래를 자동 실행한다:
    python scripts/generate_water_test_images.py --uploaded-placeholders
수동 생성도 가능:
    python scripts/generate_water_test_images.py --uploaded-placeholders

uploaded/ 에는 사용자가 제공한 실제 인증사진(water_test_01.png ~ _08.png)이 들어간다.
실제 사진이 없는 슬롯만 placeholder로 채워지며, 기존 파일은 절대 덮어쓰지 않는다.

실행:
    python -m pytest tests/test_water_verification_fixtures.py -v -s
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "local_eval" / "qwen_vlm_eval" / "scripts"
MANIFEST_PATH = ROOT / "data" / "test_images" / "water" / "water_manifest.json"
GEN_SCRIPT = ROOT / "scripts" / "generate_water_test_images.py"
REPORT_PATH = ROOT / "local_eval" / "qwen_vlm_eval" / "outputs" / "water_verdict_report.csv"

# water_verdict / normalize_water_output 는 scripts 디렉터리에 있다 (패키지 아님).
sys.path.insert(0, str(SCRIPTS_DIR))
import water_verdict as wv  # noqa: E402
import normalize_water_output as nwo  # noqa: E402

from backend.database.schema.image_verification_schema import (  # noqa: E402
    ImageObjectObservation,
    ImageVerificationContext,
    VisionAnalysis,
)
from backend.services.image_verification_rule_engine import (  # noqa: E402
    evaluate_image_verification,
)


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


MANIFEST = _load_manifest()
IMAGES = MANIFEST["images"]


@pytest.fixture(scope="session", autouse=True)
def ensure_images():
    """generated/ 이미지가 없으면 생성 스크립트를 먼저 실행한다."""
    missing = [
        e for e in IMAGES
        if e["source"] == "generated" and not (ROOT / e["image_path"]).exists()
    ]
    if missing:
        subprocess.run(
            [sys.executable, str(GEN_SCRIPT), "--uploaded-placeholders"],
            check=True,
            cwd=str(ROOT),
        )
    yield


@pytest.fixture(scope="session")
def report_rows():
    rows: list[dict] = []
    yield rows
    # 세션 종료 시 filename, predicted_label, expected_label, confidence, reason 리포트 저장
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = ["filename,expected_label,predicted_label,match,confidence,reason"]
    for r in rows:
        reason = str(r["reason"]).replace(",", ";").replace("\n", " ")
        conf = "" if r["confidence"] is None else f"{r['confidence']:.2f}"
        lines.append(
            f'{r["filename"]},{r["expected_label"]},{r["predicted_label"]},'
            f'{r["match"]},{conf},"{reason}"'
        )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n[report] wrote {REPORT_PATH.relative_to(ROOT)} ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# 1. 매니페스트 무결성
# ---------------------------------------------------------------------------

def test_manifest_counts():
    assert MANIFEST["counts"]["total"] == 18
    assert MANIFEST["counts"]["uploaded"] == 8
    assert MANIFEST["counts"]["generated"] == 10
    assert len(IMAGES) == 18
    assert sum(1 for e in IMAGES if e["source"] == "uploaded") == 8
    assert sum(1 for e in IMAGES if e["source"] == "generated") == 10


@pytest.mark.parametrize("entry", IMAGES, ids=[e["filename"] for e in IMAGES])
def test_manifest_entry_fields(entry):
    for field in ("filename", "image_path", "expected_label", "source", "reason", "difficulty"):
        assert entry.get(field), f"{entry.get('filename')} missing {field}"
    assert entry["expected_label"] in {"PASS", "FAIL", "BORDERLINE"}
    assert entry["source"] in {"uploaded", "generated"}
    assert entry["difficulty"] in {"easy", "medium", "hard"}


@pytest.mark.parametrize("entry", IMAGES, ids=[e["filename"] for e in IMAGES])
def test_image_file_exists(entry):
    assert (ROOT / entry["image_path"]).exists(), f"missing image: {entry['image_path']}"


# ---------------------------------------------------------------------------
# 2. 견고한 판정 파서 (요구사항 7)
# ---------------------------------------------------------------------------

PARSER_CASES = [
    # 문자열 PASS/FAIL
    ("PASS", wv.PASS), ("pass", wv.PASS), ("PASS.", wv.PASS),
    ("FAIL", wv.FAIL), ("Fail!", wv.FAIL), ("fail", wv.FAIL),
    # true/false
    ("true", wv.PASS), ("True", wv.PASS), ("false", wv.FAIL), ("FALSE", wv.FAIL),
    # 물 있음/물 없음
    ("물 있음", wv.PASS), ("물있음", wv.PASS), ("물이 있습니다", wv.PASS),
    ("물 없음", wv.FAIL), ("물없음", wv.FAIL), ("물이 없습니다", wv.FAIL),
    # 인증 가능/인증 불가
    ("인증 가능", wv.PASS), ("인증가능", wv.PASS),
    ("인증 불가", wv.FAIL), ("인증 불가능", wv.FAIL),
    # rule engine 결과 문자열
    ("verified", wv.PASS), ("rejected", wv.FAIL),
    ("retake_required", wv.BORDERLINE),
    # 기타 자연어
    ("빈 컵입니다", wv.FAIL), ("통과", wv.PASS), ("실패", wv.FAIL),
    ("yes", wv.PASS), ("no", wv.FAIL),
    # dict 형태
    ({"result": "verified"}, wv.PASS),
    ({"label": "FAIL"}, wv.FAIL),
    ({"verdict": True}, wv.PASS),
    ({"pass": False}, wv.FAIL),
    ({"is_water": True}, wv.PASS),
    ({"decision": "물 없음"}, wv.FAIL),
    # bool
    (True, wv.PASS), (False, wv.FAIL),
]


@pytest.mark.parametrize("raw,expected", PARSER_CASES)
def test_parser_robustness(raw, expected):
    verdict = wv.normalize_verdict(raw)
    assert verdict.label == expected, f"{raw!r} -> {verdict.label} (expected {expected}) [{verdict.reason}]"


def test_parser_confidence_passthrough():
    v = wv.normalize_verdict({"result": "rejected", "confidence": 0.9})
    assert v.label == wv.FAIL
    assert v.confidence == pytest.approx(0.9)


def test_parser_unknown_for_gibberish():
    assert wv.normalize_verdict("banana pancakes").label == wv.UNKNOWN


# ---------------------------------------------------------------------------
# 3. VLM 판독 흐름의 PASS/FAIL 판정 (요구사항 5, 6)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entry", IMAGES, ids=[e["filename"] for e in IMAGES])
def test_water_verdict_matches_expected(entry, report_rows):
    # entry["vision_analysis"] 는 (Qwen 증거를 사람이 검수한) 정규화 VisionAnalysis 픽스처.
    verdict = wv.normalize_verdict(entry["vision_analysis"])
    predicted = verdict.label
    expected = entry["expected_label"]

    match = (predicted != wv.PASS) if expected == "BORDERLINE" else (predicted == expected)
    report_rows.append({
        "filename": entry["filename"],
        "expected_label": expected,
        "predicted_label": predicted,
        "confidence": verdict.confidence,
        "reason": verdict.reason,
        "match": match,
    })
    print(
        f"{entry['filename']:<45} expected={expected:<10} predicted={predicted:<6} "
        f"conf={verdict.confidence} :: {verdict.reason}"
    )

    if expected == "BORDERLINE":
        assert predicted != wv.PASS, f"BORDERLINE 이미지가 PASS로 판정됨: {entry['filename']}"
    else:
        assert predicted == expected, (
            f"{entry['filename']}: predicted {predicted}, expected {expected} ({verdict.reason})"
        )


# ---------------------------------------------------------------------------
# 4. "컵이 있다"는 이유만으로 PASS하지 않는지
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label", ["cup", "glass", "tumbler", "water_bottle"])
def test_container_alone_is_not_pass(label):
    """물 근거 없이 용기만 보이면 절대 PASS가 아니어야 한다."""
    analysis = VisionAnalysis(objects=[ImageObjectObservation(label=label, confidence=0.99)])
    data = evaluate_image_verification("water", analysis, ImageVerificationContext())
    assert data.result != "verified"
    assert wv.RESULT_LABEL_MAP[data.result] == wv.FAIL


def test_empty_container_is_fail():
    analysis = VisionAnalysis(
        objects=[ImageObjectObservation(label="glass", confidence=0.99)],
        water_visual_evidence=["empty_container"],
    )
    assert wv.verdict_from_vision_analysis(analysis).label == wv.FAIL


def test_colored_beverage_is_fail():
    analysis = VisionAnalysis(
        objects=[ImageObjectObservation(label="cup", confidence=0.99)],
        water_visual_evidence=["non_water_beverage"],
    )
    assert wv.verdict_from_vision_analysis(analysis).label == wv.FAIL


def test_visible_water_without_filled_container_is_not_pass():
    """물이 아주 조금만 보이고 채워진 근거가 없으면 PASS가 아니어야 한다."""
    analysis = VisionAnalysis(
        objects=[ImageObjectObservation(label="glass", confidence=0.99)],
        water_visual_evidence=["visible_water"],
    )
    assert wv.verdict_from_vision_analysis(analysis).label == wv.FAIL


# ---------------------------------------------------------------------------
# 5. normalize_water_output (Qwen 증거 → VisionAnalysis) 판독 함수 검증
# ---------------------------------------------------------------------------

def test_normalize_water_output_full_glass_pass():
    raw = {
        "verification_type": "water",
        "image_quality": {"usable": True, "issues": []},
        "objects": [{"label": "glass"}],
        "scenes": ["table"],
        "visual_evidence": ["water", "filled_container"],  # 별칭 water -> visible_water
        "negative_evidence": [],
        "uncertain_evidence": [],
        "text_observed": [],
        "confidence": 0.9,
    }
    normalized = nwo.normalize_water_evidence(raw)
    assert set(normalized["water_visual_evidence"]) == {"visible_water", "filled_container"}
    assert {o["label"] for o in normalized["objects"]} == {"glass"}
    assert wv.normalize_verdict(normalized).label == wv.PASS


def test_normalize_water_output_dispenser_alias_pass():
    raw = {
        "verification_type": "water",
        "objects": ["water_purifier", "cup"],  # water_purifier -> water_dispenser
        "visual_evidence": ["pouring_water", "receiving_water"],  # pouring_water -> water_stream
        "confidence": 0.8,
    }
    normalized = nwo.normalize_water_evidence(raw)
    assert {o["label"] for o in normalized["objects"]} == {"water_dispenser", "cup"}
    assert wv.normalize_verdict(normalized).label == wv.PASS


@pytest.mark.parametrize("scene_value,expected", [
    ("kitchen", "kitchen"),                                   # str 그대로
    ({"name": "kitchen", "description": "sink"}, "kitchen"),   # dict name 우선
    ({"label": "desk"}, "desk"),                              # label
    ({"type": "table"}, "table"),                             # type
    ({"description": "on a book"}, "on a book"),              # description
    (None, None),                                             # 없음
])
def test_normalize_scene_dict_coercion(scene_value, expected):
    raw = {"scene": scene_value, "objects": [{"label": "glass"}],
           "visual_evidence": ["visible_water", "filled_container"]}
    normalized = nwo.normalize_water_evidence(raw)
    assert normalized["scene"] == expected
    assert normalized["scene"] is None or isinstance(normalized["scene"], str)
    # str/None 이면 VisionAnalysis 검증을 통과해야 한다 (원래 버그 재현 방지)
    VisionAnalysis.model_validate(normalized)


def test_normalize_scene_dict_without_known_keys_falls_back_to_json():
    raw = {"scene": {"foo": "bar"}, "objects": [{"label": "cup"}]}
    normalized = nwo.normalize_water_evidence(raw)
    assert isinstance(normalized["scene"], str)
    assert "foo" in normalized["scene"]
    VisionAnalysis.model_validate(normalized)


@pytest.mark.parametrize("scenes_value,expected", [
    (["kitchen", "sink"], "kitchen"),                              # list[str] → 첫 원소
    ([{"name": "dispenser_area"}], "dispenser_area"),              # list[dict] → name 추출
    ([], None),                                                    # 빈 list
])
def test_normalize_scenes_list_coercion(scenes_value, expected):
    raw = {"scenes": scenes_value, "objects": [{"label": "glass"}],
           "visual_evidence": ["visible_water", "filled_container"]}
    normalized = nwo.normalize_water_evidence(raw)
    assert normalized["scene"] == expected
    assert normalized["scene"] is None or isinstance(normalized["scene"], str)
    VisionAnalysis.model_validate(normalized)


def test_normalize_scene_dict_end_to_end_pass():
    """scene이 dict로 와도 (원래 ERROR 나던 케이스) 정상 PASS까지 흘러가야 한다."""
    raw = {
        "verification_type": "water",
        "scene": {"name": "kitchen", "description": "a glass of water on the counter"},
        "objects": [{"label": "glass"}],
        "visual_evidence": ["visible_water", "filled_container"],
        "confidence": 0.9,
    }
    normalized = nwo.normalize_water_evidence(raw)
    assert normalized["scene"] == "kitchen"
    assert wv.normalize_verdict(normalized).label == wv.PASS


@pytest.mark.parametrize("phrase,expected_tokens", [
    ("liquid visible", {"visible_clear_liquid"}),
    ("water in glass", {"visible_water", "filled_container"}),
    ("clear liquid in glass", {"visible_clear_liquid", "filled_container"}),
    ("partially filled glass", {"filled_container"}),
    ("transparent liquid", {"visible_clear_liquid"}),
    ("drinkable water", {"visible_water"}),
])
def test_phrase_alias_mapping(phrase, expected_tokens):
    """요구사항 3의 자연어 구 → 표준 토큰 매핑."""
    assert set(nwo.match_water_phrases(phrase)) >= expected_tokens


def test_dict_form_evidence_is_extracted():
    """Qwen이 evidence를 dict(name/description)로 내놓아도 물 근거를 놓치지 않아야 한다.

    (원래 false negative의 근본 원인: dict 항목이 통째로 버려졌음)
    """
    raw = {
        "objects": [{"name": "glass", "description": "A clear glass cup."}],
        "visual_evidence": [{"name": "clear liquid in cup",
                             "description": "A clear liquid is visible in the cup."}],
    }
    normalized = nwo.normalize_water_evidence(raw)
    assert set(normalized["water_visual_evidence"]) == {"visible_clear_liquid", "filled_container"}
    assert {o["label"] for o in normalized["objects"]} == {"glass"}
    assert wv.normalize_verdict(normalized).label == wv.PASS


def test_leakage_drop_keeps_water_pass_despite_spurious_negatives():
    """실제 water_test_01 (최신 raw): object는 'hand holding glass'(설명 없음), negative/opaque는
    이름만(설명 없음). object fallback으로 glass를 복구하고, 이름만 있는 모순 근거는 제거되어 PASS."""
    raw = {
        "water_amount": "partial",
        "objects": [{"name": "hand holding glass", "position": [1, 78, 146, 139]}],
        "scenes": [{"name": "hand holding glass with lemon slice"}],
        "visual_evidence": [{"name": "clear liquid in glass", "position": [74, 52, 188, 220]}],
        "negative_evidence": [{"name": "non-water beverage", "position": [134, 78, 163, 110]}],
        "uncertain_evidence": [{"name": "opaque closed container", "position": [134, 78, 163, 110]}],
        "confidence": 0.85,
    }
    normalized = nwo.normalize_water_evidence(raw)
    assert {o["label"] for o in normalized["objects"]} == {"glass"}  # fallback 복구
    assert "non_water_beverage" not in normalized["water_visual_evidence"]  # 이름만 → 제거
    assert "opaque_closed_container" not in normalized["water_visual_evidence"]  # 이름만 → 제거
    assert {"visible_clear_liquid", "filled_container"}.issubset(normalized["water_visual_evidence"])
    assert wv.normalize_verdict(normalized).label == wv.PASS


# ----- 요구사항 7: object fallback + 이름만 모순 근거 제거 + 확정 negative 유지 -----

def test_object_fallback_from_description():
    """object name이 컵/유리컵이 아니어도 description에 glass가 있으면 glass fallback."""
    raw = {
        "objects": [{"name": "hand", "description": "hand holding a glass filled with clear liquid"}],
        "visual_evidence": [{"name": "clear liquid in glass"}],
    }
    normalized = nwo.normalize_water_evidence(raw)
    assert "glass" in {o["label"] for o in normalized["objects"]}


def test_fallback_glass_with_strong_positive_passes():
    """visible_clear_liquid + filled_container + fallback glass → PASS."""
    raw = {
        "objects": [{"name": "hand holding glass"}],
        "visual_evidence": [{"name": "clear liquid in glass"}],
    }
    assert wv.normalize_verdict(nwo.normalize_water_evidence(raw)).label == wv.PASS


def test_name_only_negatives_with_fallback_glass_pass():
    """clear liquid + filled + non_water(name only) + opaque(name only) + fallback glass → PASS 가능."""
    raw = {
        "objects": [{"name": "hand holding glass"}],
        "visual_evidence": [{"name": "clear liquid in glass"}],
        "negative_evidence": [{"name": "non_water_beverage"}],
        "uncertain_evidence": [{"name": "opaque_closed_container"}],
    }
    normalized = nwo.normalize_water_evidence(raw)
    assert wv.normalize_verdict(normalized).label == wv.PASS


def test_empty_container_from_no_liquid_phrase_is_removed():
    """empty 근거가 'no liquid is visible'뿐이면 강한 긍정 앞에서 제거된다."""
    raw = {
        "objects": [{"name": "glass"}],
        "visual_evidence": [
            {"name": "visible_water", "description": "clear liquid visible inside the glass"},
            {"name": "filled_container", "description": "glass filled with water"},
        ],
        "uncertain_evidence": [{"name": "opaque_closed_container",
                                "description": "no liquid is visible"}],
    }
    normalized = nwo.normalize_water_evidence(raw)
    assert "empty_container" not in normalized["water_visual_evidence"]
    assert wv.normalize_verdict(normalized).label == wv.PASS


def test_confirmed_colored_beverage_stays_fail():
    """설명이 명확한 색 음료(coffee)면 clear liquid가 있어도 FAIL."""
    raw = {
        "objects": [{"name": "cup"}],
        "visual_evidence": [{"name": "clear liquid in cup"}],
        "negative_evidence": [{"name": "non_water_beverage",
                               "description": "the cup contains coffee, a brown colored beverage"}],
    }
    normalized = nwo.normalize_water_evidence(raw)
    assert "non_water_beverage" in normalized["water_visual_evidence"]
    assert wv.normalize_verdict(normalized).label == wv.FAIL


@pytest.mark.parametrize("desc", [
    "a glass with a tiny amount of liquid",
    "a glass with a small amount of liquid",
    "nearly empty glass",
])
def test_insufficient_amount_without_amount_field_not_pass(desc):
    """water_amount 필드가 없을 때, tiny/small/nearly empty 표현은 PASS 금지."""
    raw = {"objects": [{"name": "glass"}], "visual_evidence": [{"name": "glass", "description": desc}]}
    assert wv.normalize_verdict(nwo.normalize_water_evidence(raw)).label != wv.PASS


def test_small_amount_of_liquid_stays_fail():
    """소량 액체는 empty_container(hard negative)로 매핑되어 FAIL 유지되어야 한다."""
    raw = {
        "objects": [{"name": "cup", "description": "A clear glass cup."}],
        "visual_evidence": [{"name": "cup",
                             "description": "A clear glass cup containing a small amount of liquid."}],
        "confidence": 0.8,
    }
    normalized = nwo.normalize_water_evidence(raw)
    assert "filled_container" not in normalized["water_visual_evidence"]
    assert "empty_container" in normalized["water_visual_evidence"]
    assert wv.normalize_verdict(normalized).label == wv.FAIL


def _norm_tokens(**raw):
    return set(nwo.normalize_water_evidence(raw)["water_visual_evidence"])


# ----- 요구사항 8: negation / contradiction / amount 보수화 -----

def test_no_other_beverages_is_not_mapped_negative():
    """'no other beverages or liquids visible'는 non_water/empty로 매핑되면 안 된다."""
    tokens = _norm_tokens(
        objects=[{"name": "glass"}],
        negative_evidence=[{"name": "non_water_beverage",
                            "description": "no other beverages or liquids visible in the glass"}],
    )
    assert "non_water_beverage" not in tokens
    assert "empty_container" not in tokens


def test_closed_but_strong_positive_removes_empty_and_passes():
    """'glass appears to be closed but no liquid is visible'가 있어도
    visible_water + filled_container가 있으면 모순 근거가 제거되어 PASS 가능."""
    raw = {
        "objects": [{"name": "glass"}],
        "visual_evidence": [
            {"name": "visible_water", "description": "clear liquid visible inside the glass"},
            {"name": "filled_container", "description": "glass filled with water"},
        ],
        "uncertain_evidence": [{"name": "opaque_closed_container",
                                "description": "glass appears to be closed but no liquid is visible"}],
    }
    normalized = nwo.normalize_water_evidence(raw)
    assert "empty_container" not in normalized["water_visual_evidence"]
    assert "opaque_closed_container" not in normalized["water_visual_evidence"]
    assert wv.normalize_verdict(normalized).label == wv.PASS


def test_transparent_not_opaque_is_not_mapped_opaque():
    """'glass is transparent, so it's not opaque'는 opaque_closed_container로 매핑되면 안 된다."""
    tokens = _norm_tokens(
        objects=[{"name": "glass"}],
        uncertain_evidence=[{"name": "opaque_closed_container",
                             "description": "the glass is transparent, so it's not opaque"}],
    )
    assert "opaque_closed_container" not in tokens


def test_clear_liquid_and_filled_is_pass():
    """'clear liquid visible inside the glass' + 'glass filled with water' → PASS."""
    raw = {
        "objects": [{"name": "glass"}],
        "visual_evidence": [
            {"name": "visible_water", "description": "clear liquid visible inside the glass"},
            {"name": "filled_container", "description": "glass filled with water"},
        ],
    }
    assert wv.normalize_verdict(nwo.normalize_water_evidence(raw)).label == wv.PASS


@pytest.mark.parametrize("desc", [
    "clear glass cup containing a small amount of liquid",
    "glass with a tiny amount of liquid at the bottom",
    "almost empty glass",
])
def test_insufficient_liquid_is_not_pass(desc):
    """소량/거의 빈 표현은 PASS가 되면 안 된다 (false positive 방지)."""
    raw = {"objects": [{"name": "glass"}],
           "visual_evidence": [{"name": "cup", "description": desc}]}
    normalized = nwo.normalize_water_evidence(raw)
    assert "filled_container" not in normalized["water_visual_evidence"]
    assert wv.normalize_verdict(normalized).label != wv.PASS


@pytest.mark.parametrize("amount,should_pass", [
    ("filled", True),
    ("partial", True),
    ("tiny", False),
    ("none", False),
    ("uncertain", False),
])
def test_water_amount_field_gates_pass(amount, should_pass):
    """water_amount 힌트: none/tiny/uncertain은 PASS 금지, partial/filled는 PASS 가능."""
    raw = {
        "objects": [{"name": "glass"}],
        "water_amount": amount,
        "visual_evidence": [
            {"name": "visible_water", "description": "clear liquid visible inside the glass"},
            {"name": "filled_container", "description": "glass filled with water"},
        ],
    }
    normalized = nwo.normalize_water_evidence(raw)
    is_pass = wv.normalize_verdict(normalized).label == wv.PASS
    assert is_pass == should_pass


def test_water_amount_absent_is_backward_compatible():
    """water_amount가 없으면 기존 동작 그대로 (강한 긍정 → PASS)."""
    raw = {
        "objects": [{"name": "glass"}],
        "visual_evidence": [
            {"name": "visible_water", "description": "clear liquid visible inside the glass"},
            {"name": "filled_container", "description": "glass filled with water"},
        ],
    }
    assert wv.normalize_verdict(nwo.normalize_water_evidence(raw)).label == wv.PASS


def test_dispenser_phrase_mapping_pass():
    raw = {
        "objects": [{"name": "water dispenser"}, {"name": "cup"}],
        "visual_evidence": [{"name": "pouring water",
                             "description": "Water is pouring from the dispenser into the cup."}],
    }
    normalized = nwo.normalize_water_evidence(raw)
    assert {"water_stream", "receiving_water"}.issubset(normalized["water_visual_evidence"])
    assert {"water_dispenser", "cup"} == {o["label"] for o in normalized["objects"]}
    assert wv.normalize_verdict(normalized).label == wv.PASS


def test_normalize_water_output_empty_cup_fail():
    raw = {
        "verification_type": "water",
        "objects": [{"type": "mug"}],  # mug -> cup
        "negative_evidence": ["empty_cup"],  # empty_cup -> empty_container
        "confidence": 0.7,
    }
    normalized = nwo.normalize_water_evidence(raw)
    assert normalized["water_visual_evidence"] == ["empty_container"]
    assert wv.normalize_verdict(normalized).label == wv.FAIL


# ---------------------------------------------------------------------------
# 6. BORDERLINE 케이스 기록 (요구사항: borderline_cases 분리)
# ---------------------------------------------------------------------------

def test_borderline_cases_recorded():
    borderline = MANIFEST.get("borderline_cases", [])
    assert borderline, "borderline_cases가 비어 있음"
    # 매니페스트의 BORDERLINE 라벨 이미지와 borderline_cases가 일치해야 한다.
    labeled = {e["filename"] for e in IMAGES if e["expected_label"] == "BORDERLINE"}
    recorded = {b["filename"] for b in borderline}
    assert labeled == recorded
    # 기록된 borderline 은 PASS로 판정되면 안 된다.
    for b in borderline:
        assert b["predicted_label"] != wv.PASS
