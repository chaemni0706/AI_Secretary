"""Qwen 물 인증 증거 → VisionAnalysis 정규화.

`normalize_qwen_output.py`(study용)의 물 버전. Qwen VLM(run_qwen_single.py)이 뽑은
raw evidence JSON을 Rule Engine이 먹을 수 있는 VisionAnalysis 호환 dict로 변환한다.
torch 등 무거운 의존성 없이 순수 파이썬만 사용하므로 pytest에서 직접 검증할 수 있다.

핵심 방어 로직 (false positive/negative 모두 줄이기):
1. evidence 항목이 dict(name/description)면 name+description을 합쳐 처리한다.
2. object 이름/설명 또는 scene/evidence에 glass/cup 표현이 있으면 object를 복구한다(fallback).
3. 부정문("no other beverages", "not opaque", "does not appear to be water")은 negative로 보지 않는다.
4. negative 근거는 "확정(hard)"과 "이름만/근거약함(soft)"으로 구분한다.
   - non_water_beverage: 설명에 coffee/colored/juice 등 실제 색 음료 근거가 있어야 hard.
   - opaque_closed_container: 설명에 opaque/cannot-see 근거가 있어야 hard.
   - empty_container: 명시적 빈/소량 표현 또는 water_amount none/tiny면 hard.
5. 강한 긍정(glass/cup + 투명 액체 + filled + hard negative 없음)이면 soft 모순 근거를 제거한다.
6. water_amount(none|tiny|partial|filled|uncertain): none/tiny/uncertain은 PASS 금지,
   partial/filled + 투명 액체면 filled_container를 보강해 PASS를 허용한다. (필드 없으면 하위호환)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# WaterVisualEvidence enum (image_verification_schema.py와 일치)
WATER_EVIDENCE = {
    "visible_water",
    "visible_clear_liquid",
    "filled_container",
    "sealed_water_bottle",
    "water_stream",
    "container_under_dispenser",
    "receiving_water",
    "empty_container",
    "opaque_closed_container",
    "non_water_beverage",
    "uncertain_liquid",
}

POSITIVE_TOKENS = {
    "visible_water",
    "visible_clear_liquid",
    "filled_container",
    "sealed_water_bottle",
    "water_stream",
    "container_under_dispenser",
    "receiving_water",
}

# 단일 토큰 표현 별칭 (공백/하이픈을 _로 치환한 단일 토큰 매칭용)
WATER_EVIDENCE_ALIASES = {
    "water": "visible_water",
    "visible_liquid": "visible_clear_liquid",
    "clear_liquid": "visible_clear_liquid",
    "filled": "filled_container",
    "full_container": "filled_container",
    "sealed_bottle": "sealed_water_bottle",
    "pouring_water": "water_stream",
    "receiving": "receiving_water",
    "dispensing_water": "water_stream",
    "empty_cup": "empty_container",
    "colored_beverage": "non_water_beverage",
    "coffee": "non_water_beverage",
    "juice": "non_water_beverage",
    "closed_opaque": "opaque_closed_container",
    "unclear_liquid": "uncertain_liquid",
}

# --- 긍정 자연어 구 → 토큰 (다중 매핑, 부분 문자열) ---
POSITIVE_PHRASES: list[tuple[str, tuple[str, ...]]] = [
    ("water in glass", ("visible_water", "filled_container")),
    ("water in the glass", ("visible_water", "filled_container")),
    ("water in cup", ("visible_water", "filled_container")),
    ("water in the cup", ("visible_water", "filled_container")),
    ("glass of water", ("visible_water", "filled_container")),
    ("cup of water", ("visible_water", "filled_container")),
    ("filled with water", ("visible_water", "filled_container")),
    ("containing water", ("visible_water", "filled_container")),
    ("full of water", ("visible_water", "filled_container")),
    ("clear liquid in glass", ("visible_clear_liquid", "filled_container")),
    ("clear liquid in the glass", ("visible_clear_liquid", "filled_container")),
    ("clear liquid in cup", ("visible_clear_liquid", "filled_container")),
    ("clear liquid in the cup", ("visible_clear_liquid", "filled_container")),
    ("clear liquid in a", ("visible_clear_liquid", "filled_container")),
    # 강한 fill 단서 (filled_container 부여)
    ("floating in", ("filled_container",)),
    ("meaningful amount", ("filled_container",)),
    ("water line", ("filled_container",)),
    ("partially filled", ("filled_container",)),
    ("half full", ("filled_container",)),
    ("half-full", ("filled_container",)),
    ("half filled", ("filled_container",)),
    # 약한 단서: 투명 유리/맑은 액체 '만'으로는 filled 부여 금지 (visible_clear_liquid만)
    ("clear transparent liquid", ("visible_clear_liquid",)),
    ("liquid visible", ("visible_clear_liquid",)),
    ("visible liquid", ("visible_clear_liquid",)),
    ("transparent liquid", ("visible_clear_liquid",)),
    ("clear liquid", ("visible_clear_liquid",)),
    ("clear water", ("visible_water",)),
    ("drinkable water", ("visible_water",)),
    ("water is visible", ("visible_water",)),
    ("water visible", ("visible_water",)),
    # 정수기 / 물줄기
    ("pouring", ("water_stream", "receiving_water")),
    ("dispensing water", ("water_stream", "receiving_water")),
    ("water being dispensed", ("water_stream", "receiving_water")),
    ("being dispensed", ("water_stream", "receiving_water")),
    ("being filled with water", ("water_stream", "receiving_water")),
    ("stream of water", ("water_stream", "receiving_water")),
    ("water flowing", ("water_stream", "receiving_water")),
    ("dispenser pouring", ("water_stream", "receiving_water")),
    ("purifier pouring", ("water_stream", "receiving_water")),
    ("pouring into a cup", ("water_stream", "receiving_water")),
    ("pouring into a glass", ("water_stream", "receiving_water")),
    ("filling the glass", ("water_stream", "receiving_water")),
    ("filling the cup", ("water_stream", "receiving_water")),
    ("cup under dispenser", ("container_under_dispenser", "receiving_water")),
    ("glass under dispenser", ("container_under_dispenser", "receiving_water")),
    ("under the dispenser", ("container_under_dispenser",)),
    ("cup receiving water", ("receiving_water",)),
    ("glass receiving water", ("receiving_water",)),
    ("receiving water", ("receiving_water",)),
    # 밀봉 물병
    ("sealed water bottle", ("sealed_water_bottle",)),
    ("sealed bottle", ("sealed_water_bottle",)),
    ("unopened bottle", ("sealed_water_bottle",)),
]

# --- 소량 표현 → empty_container (water_amount가 partial/filled면 무시 = 과소평가 보정) ---
AMOUNT_EMPTY_PHRASES: tuple[str, ...] = (
    "tiny amount",
    "small amount",
    "few drops",
    "only at the bottom",
    "little liquid",
    "trace of liquid",
)

# --- 명시적 빈/반사/유리표면 표현 → empty_container (water_amount와 무관, 항상 hard) ---
# 반사·유리 광택·빈 유리는 물이 아니므로 water_amount=partial 이어도 FAIL로 본다 (false positive 방지).
HARD_EMPTY_PHRASES: tuple[str, ...] = (
    "empty cup",
    "empty glass",
    "empty cups",
    "empty glasses",
    "glass is empty",
    "cup is empty",
    "nearly empty",
    "almost empty",
    "no water in the cup",
    "no water in the glass",
    "no water",
    "no liquid",
    "no visible water",
    "no visible liquid",
    "without water",
    "no water line",
    "reflection",
    "glass reflection",
    "glass shine",
    "light reflection",
    "transparent glass only",
    "clear glass only",
    "glass surface",
    "only the glass",
    "just the glass",
    "just glasses",
)

# --- 여러 개의 컵/유리컵 → 단일 섭취 인증 불가 (BORDERLINE로 강등) ---
MULTI_CONTAINER_PHRASES: tuple[str, ...] = (
    "two glasses",
    "three glasses",
    "four glasses",
    "multiple glasses",
    "several glasses",
    "pair of glasses",
    "both glasses",
    "two cups",
    "three cups",
    "multiple cups",
    "several cups",
    "glasses on a tray",
    "cups on a tray",
)

# --- 부정문 검사를 거치는 negative 자연어 구 → 토큰 ---
NON_WATER_PHRASES: tuple[str, ...] = (
    "non-water beverage",
    "non water beverage",
    "colored beverage",
    "colored liquid",
    "coffee",
    "juice",
    "soda",
)
OPAQUE_PHRASES: tuple[str, ...] = (
    "opaque",
    "closed container",
    "cannot see inside",
    "can't see inside",
)
UNCERTAIN_PHRASES: tuple[str, ...] = (
    "uncertain liquid",
    "unclear liquid",
    "cannot tell if",
    "cannot determine",
    "unable to determine",
)

# non_water_beverage를 hard(확정)로 볼 수 있는, 설명 속 실제 색 음료 근거
CONFIRMED_COLORED: tuple[str, ...] = (
    "coffee",
    "colored beverage",
    "colored liquid",
    "brown liquid",
    "dark liquid",
    "juice",
    "soda",
    "alcohol",
    "beer",
    "wine",
    "latte",
    "cola",
    "cocoa",
    "milk",
)
# opaque_closed_container를 hard(확정)로 볼 수 있는, 설명 속 근거 ("closed"만으로는 부족)
CONFIRMED_OPAQUE: tuple[str, ...] = (
    "opaque",
    "cannot see inside",
    "can't see inside",
    "cannot see the liquid",
    "not see-through",
    "not transparent",
    "contents are not visible",
)

# 가정/조건문 단서: 실제 관측이 아니라 "would/could/if ... " 형태의 가상 진술.
# negative 근거와 empty 근거 양쪽에서 무효화한다.
HYPOTHETICAL_CUES: tuple[str, ...] = (
    "would indicate",
    "could indicate",
    "which could indicate",
    "could potentially",
    "potentially contain",
    "the presence of",
    "if the glass",
    "if the cup",
    "if it were",
    "if ",
    "may appear",
    "might appear",
    "may look",
    "could appear",
    "would appear",
    "suggests that",
    "due to reflection",
    "due to reflections",
    "due to transparency",
    "may be empty",
    "might be empty",
    "could be empty",
)

# 부정문 단서: negative 근거를 무효화한다.
NEGATION_CUES: tuple[str, ...] = (
    "no other",
    "no indication",
    "not ",
    "n't",
    "isn't",
    "aren't",
    "without",
    "does not",
    "doesn't",
    "transparent",
    "see-through",
    "no non",
    "appears to be water",
    "is water",
) + HYPOTHETICAL_CUES

# 물 인증 관련 허용 object label (water.yaml allowed_labels)
WATER_OBJECT_LABELS = {
    "cup",
    "glass",
    "tumbler",
    "water_bottle",
    "pet_bottle",
    "water_container",
    "water_dispenser",
}
# 물을 담는 '용기' (dispenser 제외)
CONTAINER_LABELS = {"cup", "glass", "tumbler", "water_bottle", "pet_bottle", "water_container"}
# 모순 제거(soft drop) 판정에 쓰는 컵/유리컵
CUP_GLASS_LABELS = {"glass", "cup", "tumbler"}

WATER_OBJECT_ALIASES = {
    "bottle": "water_bottle",
    "plastic_bottle": "pet_bottle",
    "mug": "cup",
    "pitcher": "water_container",
    "jug": "water_container",
    "dispenser": "water_dispenser",
    "water_purifier": "water_dispenser",
    "purifier": "water_dispenser",
}


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _dedupe(items) -> list:
    seen, out = set(), []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def scene_to_string(value):
    """scene/scenes 값을 str 또는 None으로 강제 변환.

    - str → 그대로
    - dict → name > label > type > description 우선순위, 없으면 json.dumps
    - list → 첫 번째 원소를 같은 규칙으로 변환
    - 그 외/추출 실패 → None
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        for key in ("name", "label", "type", "description"):
            picked = value.get(key)
            if isinstance(picked, str) and picked:
                return picked
        if value:
            return json.dumps(value, ensure_ascii=False)
        return None
    if isinstance(value, list):
        return scene_to_string(value[0]) if value else None
    return None


def resolve_scene(raw: dict):
    """raw dict에서 scene → scenes 순으로 문자열 scene을 결정 (없으면 None)."""
    scene = scene_to_string(raw.get("scene"))
    if scene is None:
        scene = scene_to_string(raw.get("scenes"))
    return scene


def _canon_object(label: str) -> str | None:
    key = str(label).strip().lower().replace(" ", "_").replace("/", "_").replace("-", "_")
    key = WATER_OBJECT_ALIASES.get(key, key)
    if key in WATER_OBJECT_LABELS:
        return key
    # "water dispenser/purifier", "water_purifier", "dispenser/purifier" 등 변형 흡수
    if "dispenser" in key or "purifier" in key:
        return "water_dispenser"
    return None


def normalize_objects(raw_objects, confidence):
    result = []
    seen = set()
    for obj in as_list(raw_objects):
        if isinstance(obj, str):
            label, evidence = obj, None
        elif isinstance(obj, dict):
            label = obj.get("label") or obj.get("type") or obj.get("name")
            evidence = obj.get("evidence") or obj.get("description")
        else:
            continue
        if not label:
            continue
        canon = _canon_object(label)
        if canon and canon not in seen:
            seen.add(canon)
            result.append({"label": canon, "confidence": float(confidence), "evidence": evidence})
    return result


def _canon_evidence_token(token: str) -> str | None:
    """단일 토큰(예: 'empty_cup', 'visible_water')을 표준 water evidence로 정규화."""
    key = str(token).strip().lower().replace(" ", "_").replace("-", "_")
    key = WATER_EVIDENCE_ALIASES.get(key, key)
    return key if key in WATER_EVIDENCE else None


def _evidence_item_text(item) -> tuple[str, str, str]:
    """evidence 항목(str 또는 dict)에서 (토큰 후보, 설명, 전체 텍스트)를 뽑는다."""
    if isinstance(item, str):
        return item, "", item
    if isinstance(item, dict):
        token = item.get("name") or item.get("label") or item.get("type") or ""
        desc = item.get("description") or item.get("evidence") or ""
        return str(token), str(desc), f"{token} {desc}"
    return "", "", str(item)


def _looks_negated(text: str) -> bool:
    """negative 근거를 무효화하는 부정문/모순/가정 표현이 있는지."""
    low = str(text).lower()
    return any(cue in low for cue in NEGATION_CUES)


def _is_hypothetical(text: str) -> bool:
    """'would/could/if/may appear/due to reflections' 같은 가정·조건 표현인지 (empty 판정 방어용)."""
    low = str(text).lower()
    return any(cue in low for cue in HYPOTHETICAL_CUES)


def _match_phrases(text: str, table: list[tuple[str, tuple[str, ...]]]) -> list[str]:
    low = str(text).lower()
    out: list[str] = []
    for phrase, tokens in table:
        if phrase in low:
            out.extend(tokens)
    return out


def match_water_phrases(text: str) -> list[str]:
    """자유 텍스트에서 '긍정' 자연어 구를 찾아 표준 water evidence 토큰으로 변환 (요구사항 3)."""
    return _match_phrases(text, POSITIVE_PHRASES)


def _has_any(text: str, phrases) -> bool:
    low = str(text).lower()
    return any(p in low for p in phrases)


def _container_from_text(text: str) -> str | None:
    low = str(text).lower()
    if "glass" in low:
        return "glass"
    if "mug" in low or "cup" in low:
        return "cup"
    if "tumbler" in low:
        return "tumbler"
    return None


def _object_text(raw: dict) -> str:
    parts = []
    for obj in as_list(raw.get("objects")):
        _, _, full = _evidence_item_text(obj)
        parts.append(full)
    return " ".join(parts)


def _text_units(raw: dict) -> list[str]:
    """가정문 판정을 문장 단위로 하기 위해 scene/evidence/object 텍스트를 개별 단위로 반환."""
    units = []
    for scene in as_list(raw.get("scenes")):
        _, _, full = _evidence_item_text(scene)
        units.append(full.lower())
    if raw.get("scene"):
        units.append(str(scene_to_string(raw.get("scene")) or "").lower())
    for key in ("visual_evidence", "negative_evidence", "uncertain_evidence"):
        for item in as_list(raw.get(key)):
            _, _, full = _evidence_item_text(item)
            units.append(full.lower())
    for obj in as_list(raw.get("objects")):
        _, _, full = _evidence_item_text(obj)
        units.append(full.lower())
    return units


def _scene_and_evidence_text(raw: dict) -> str:
    parts = []
    for scene in as_list(raw.get("scenes")):
        _, _, full = _evidence_item_text(scene)
        parts.append(full)
    if raw.get("scene"):
        parts.append(str(scene_to_string(raw.get("scene")) or ""))
    for key in ("visual_evidence", "negative_evidence", "uncertain_evidence"):
        for item in as_list(raw.get(key)):
            _, _, full = _evidence_item_text(item)
            parts.append(full)
    return " ".join(parts)


def _resolve_objects(raw: dict, confidence: float, has_liquid: bool, has_filled: bool) -> list[dict]:
    """object 복구(fallback) 포함 object 리스트."""
    base = normalize_objects(raw.get("objects", []), confidence)
    labels = {o["label"] for o in base}
    if labels & CONTAINER_LABELS:
        return base

    # 요구사항 1: object 이름/설명에 glass/cup 표현이 있으면 복구
    fallback = _container_from_text(_object_text(raw))
    # 요구사항 2: object가 비어도 투명 액체+filled가 있고 scene/evidence에 glass/cup이 보이면 복구 (water 전용)
    if not fallback and has_liquid and has_filled:
        fallback = _container_from_text(_scene_and_evidence_text(raw))

    if fallback and fallback not in labels:
        base = base + [{"label": fallback, "confidence": confidence, "evidence": "fallback_from_description"}]
    return base


def build_water_evidence(raw: dict) -> tuple[list[dict], list[str]]:
    """raw → (정규화 objects, water_visual_evidence tokens)."""
    confidence = float(raw.get("confidence", 0.8) or 0.8)
    amount = str(raw.get("water_amount") or "").strip().lower()
    # water_amount="partial"은 filled_container를 스스로 부여하지 못하는 '보조 신호'다.
    # filled는 명시적 강한 fill 단서(glass of water / filled with water / water_amount=filled 등)에서만 온다.
    amount_filled = amount == "filled"
    amount_insufficient = amount in {"none", "tiny"}
    amount_uncertain = amount == "uncertain"

    items = (
        as_list(raw.get("visual_evidence"))
        + as_list(raw.get("negative_evidence"))
        + as_list(raw.get("uncertain_evidence"))
    )

    positives: list[str] = []
    soft: list[str] = []
    hard: list[str] = []

    for item in items:
        name, desc, full = _evidence_item_text(item)
        low_full = full.lower()
        low_desc = desc.lower()
        canon = _canon_evidence_token(name)

        # 긍정 토큰/구
        if canon in POSITIVE_TOKENS:
            positives.append(canon)
        positives.extend(_match_phrases(low_full, POSITIVE_PHRASES))

        # 소량 표현 → empty_container (water_amount가 충분이면 과소평가로 보고 무시)
        if not amount_filled and (_has_any(low_full, AMOUNT_EMPTY_PHRASES) or canon == "empty_container"):
            hard.append("empty_container")

        # 부정문이면 negative 근거로 보지 않음
        negated = _looks_negated(low_full)

        if not negated and (canon == "non_water_beverage" or _has_any(low_full, NON_WATER_PHRASES)):
            if _has_any(low_full, CONFIRMED_COLORED):
                hard.append("non_water_beverage")  # 실제 색 음료 근거 → 확정
            else:
                soft.append("non_water_beverage")  # 이름만 → 제거 가능

        if not negated and (canon == "opaque_closed_container" or _has_any(low_full, OPAQUE_PHRASES)):
            # opaque_closed_container는 hard negative가 아니다 (hard는 empty/색음료/여러컵/reflection뿐).
            # 항상 soft로 두어, 강한 긍정(glass/cup + 투명 액체 + filled) 앞에서는 제거되고
            # filled가 없으면(예: 닫힌 불투명 병) 그대로 남아 BORDERLINE(retake)로 간다.
            soft.append("opaque_closed_container")

        if not negated and (canon == "uncertain_liquid" or _has_any(low_full, UNCERTAIN_PHRASES)):
            soft.append("uncertain_liquid")

    positives = _dedupe(positives)

    # 전체 텍스트(scene+evidence+object) 기반 신호
    all_text = (_scene_and_evidence_text(raw) + " " + _object_text(raw)).lower()

    # 명시적 빈/반사/유리표면 → hard empty. 단, 문장 단위로 검사해 가정문
    # ("may appear to be empty due to reflections")은 제외한다 (false negative 방지).
    for unit in _text_units(raw):
        if _has_any(unit, HARD_EMPTY_PHRASES) and not _is_hypothetical(unit):
            hard.append("empty_container")
            break

    # 여러 개의 컵/유리컵 → 단일 섭취 인증 불가 → filled 제거 + uncertain (BORDERLINE)
    multi_container = _has_any(all_text, MULTI_CONTAINER_PHRASES)

    # water_amount 힌트 반영 (partial은 filled를 스스로 부여하지 않음)
    if amount_insufficient:
        positives = [p for p in positives if p != "filled_container"]
        hard.append("empty_container")
    elif amount_uncertain:
        positives = [p for p in positives if p != "filled_container"]
        soft.append("uncertain_liquid")
    elif amount_filled:
        if {"visible_water", "visible_clear_liquid"}.intersection(positives) and "filled_container" not in positives:
            positives.append("filled_container")

    # 여러 컵/유리컵: 명시적 empty가 없더라도 단일 섭취를 확정할 수 없으므로
    # filled_container를 제거하고 uncertain_liquid로 강등한다 (→ PASS 불가, BORDERLINE).
    if multi_container and "empty_container" not in hard:
        positives = [p for p in positives if p != "filled_container"]
        soft.append("uncertain_liquid")

    hard = _dedupe(hard)
    soft = _dedupe(soft)

    has_liquid = bool({"visible_water", "visible_clear_liquid"}.intersection(positives))
    has_filled = "filled_container" in positives

    objects = _resolve_objects(raw, confidence, has_liquid, has_filled)
    obj_labels = {o["label"] for o in objects}

    # 정수기/물 받는 컨텍스트: opaque_closed_container 환각 완화
    # (정수기에서 물을 받는 장면인데 Qwen이 'opaque closed'를 붙여도 PASS 가능해야 함)
    # 단, empty/색음료 같은 진짜 disqualifying hard negative가 있으면 완화하지 않는다.
    dispenser_ctx = ("water_dispenser" in obj_labels) or ("dispenser" in all_text) or ("purifier" in all_text)
    flow_present = bool(
        {"water_stream", "receiving_water", "container_under_dispenser", "filled_container"}.intersection(positives)
    )
    container_present = bool(CONTAINER_LABELS.intersection(obj_labels))
    disqualifying = ("empty_container" in hard) or ("non_water_beverage" in hard)
    if dispenser_ctx and flow_present and container_present and not disqualifying:
        # 정수기/물 받는 장면: 이름만 있는 soft 모순 근거(opaque, uncertain, name-only non_water)를 모두 제거.
        # (confirmed empty/색음료 hard negative는 disqualifying으로 이미 걸러져 여기 오지 않는다.)
        soft = []
        # req4: water_stream이 있으면 receiving_water를 보강해 Rule Engine의 dispenser 패턴이 작동하게 함
        if "water_stream" in positives and "receiving_water" not in positives:
            positives.append("receiving_water")

    # 강한 긍정 + hard negative 없음 → soft 모순 근거 제거
    has_container = bool(CUP_GLASS_LABELS.intersection(obj_labels))
    if has_container and has_liquid and has_filled and not hard:
        soft = []

    tokens = _dedupe(positives + hard + soft)
    return objects, tokens


def collect_water_evidence(raw: dict) -> list[str]:
    """raw → water_visual_evidence 토큰 리스트."""
    return build_water_evidence(raw)[1]


def normalize_water_evidence(raw: dict) -> dict:
    """Qwen raw water evidence dict → VisionAnalysis 호환 dict."""
    quality = raw.get("image_quality", {}) or {}
    scene = resolve_scene(raw)
    objects, tokens = build_water_evidence(raw)

    return {
        "quality": {
            "brightness": "normal",
            "blur": "low",
            "usable": bool(quality.get("usable", True)),
            "issues": as_list(quality.get("issues")),
        },
        "scene": scene,
        "objects": objects,
        "visible_text": [str(t) for t in as_list(raw.get("text_observed"))],
        "visual_evidence": [],
        "study_visual_evidence": [],
        "water_visual_evidence": tokens,
        "exercise_visual_evidence": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Qwen water evidence to VisionAnalysis JSON.")
    parser.add_argument("--input", required=True, help="Qwen raw evidence JSON path")
    parser.add_argument("--output", required=True, help="Normalized VisionAnalysis JSON path")
    args = parser.parse_args()

    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    normalized = normalize_water_evidence(raw)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(normalized, ensure_ascii=False, indent=2))
    print("[INFO] saved:", out)


if __name__ == "__main__":
    main()
