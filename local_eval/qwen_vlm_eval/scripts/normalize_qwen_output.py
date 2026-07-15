"""Qwen study 증거 → VisionAnalysis 정규화.

원래는 study_01 단건을 정규화하는 스크립트였으나, 공통 verification batch runner에서
import 할 수 있도록 `normalize_study_evidence(raw) -> dict` 함수를 제공하도록 정리했다.
스크립트로 직접 실행하면 기존처럼 study_01_simple_qwen.json을 정규화한다.

normalize_water_output / normalize_exercise_output 와 동일한 함수형 인터페이스를 맞춘다.
"""

import json
from pathlib import Path

INPUT = Path("local_eval/qwen_vlm_eval/outputs/study_01_simple_qwen.json")
OUTPUT = Path("local_eval/qwen_vlm_eval/outputs/study_01_normalized.json")


OBJECT_LABEL_MAP = {
    "open_textbook": "textbook",
    "open_workbook": "workbook",
    "handwritten_notes": "notebook",
    "highlighted_text": "textbook",
    "problem_solving_material": "printed_document",
    "study_content_on_screen": "monitor",
    "lecture_video": "monitor",
    "educational_document": "printed_document",
    "code_editor": "monitor",
    "study_timer": "study_timer",
}

STUDY_EVIDENCE = {
    "open_textbook",
    "open_workbook",
    "handwritten_notes",
    "highlighted_text",
    "problem_solving_material",
    "study_content_on_screen",
    "lecture_video",
    "educational_document",
    "code_editor",
    "study_timer",
    "gaming_content",
    "entertainment_video",
    "social_media",
    "shopping_content",
    "non_study_screen",
    "closed_study_materials",
    "uncertain_screen_content",
}

# 강한 긍정/부정 study 근거 (leakage drop 판정용)
_POSITIVE_CORE = {
    "open_textbook", "open_workbook", "handwritten_notes", "highlighted_text",
    "problem_solving_material", "study_content_on_screen", "lecture_video",
    "educational_document", "code_editor",
}
_NEGATIVE_CORE = {
    "gaming_content", "entertainment_video", "social_media", "shopping_content", "non_study_screen",
}


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def unique(items):
    result, seen = [], set()
    for item in items:
        if item is None:
            continue
        item = str(item)
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def scene_to_string(value):
    """scene/scenes 값을 str 또는 None으로 강제 변환 (dict/list 대응)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        for key in ("name", "label", "type", "description"):
            picked = value.get(key)
            if isinstance(picked, str) and picked:
                return picked
        return json.dumps(value, ensure_ascii=False) if value else None
    if isinstance(value, list):
        return scene_to_string(value[0]) if value else None
    return str(value)


def _evidence_token(item):
    """evidence 항목(str 또는 dict)에서 study 토큰 후보 문자열을 추출."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("name") or item.get("label") or item.get("type") or item.get("value") or ""
    return str(item)


def normalize_objects(raw_objects, confidence, evidence=None):
    """raw objects + (선택) evidence에서 유도한 object를 VisionAnalysis object 리스트로."""
    result = []
    seen = set()
    for obj in as_list(raw_objects):
        if isinstance(obj, str):
            label, desc = obj, None
        elif isinstance(obj, dict):
            label = obj.get("label") or obj.get("type") or obj.get("name")
            desc = obj.get("evidence") or obj.get("description")
            if obj.get("position") and not desc:
                desc = "position=" + str(obj.get("position"))
        else:
            continue
        if not label:
            continue
        mapped = OBJECT_LABEL_MAP.get(str(label), str(label))
        if mapped not in seen:
            seen.add(mapped)
            result.append({"label": mapped, "confidence": float(confidence), "evidence": desc})

    # study 근거로부터 종이/화면 object를 보강 (mandatory 판정 도움)
    for ev in evidence or []:
        mapped = OBJECT_LABEL_MAP.get(ev)
        if mapped and mapped not in seen:
            seen.add(mapped)
            result.append({"label": mapped, "confidence": float(confidence), "evidence": "mapped_from_evidence:" + ev})
    return result


def normalize_study_evidence(raw: dict) -> dict:
    """Qwen study raw output → VisionAnalysis 호환 dict.

    - visual/negative/uncertain evidence(문자열 또는 dict)를 study enum 토큰으로 변환
    - 강한 긍정 다수 + 부정 다수면 후보 누출(negative leakage)로 보고 제거
    - scene은 str/None, visible_text는 list[str]
    - water/exercise evidence는 빈 리스트
    """
    confidence = float(raw.get("confidence", 0.8) or 0.8)

    raw_tokens = []
    for key in ("visual_evidence", "negative_evidence", "uncertain_evidence"):
        for item in as_list(raw.get(key)):
            tok = str(_evidence_token(item)).strip().lower().replace(" ", "_").replace("-", "_")
            if tok:
                raw_tokens.append(tok)
    evidence = [t for t in unique(raw_tokens) if t in STUDY_EVIDENCE]

    positive_count = len([x for x in evidence if x in _POSITIVE_CORE])
    negative_count = len([x for x in evidence if x in _NEGATIVE_CORE])
    if positive_count >= 2 and negative_count >= 4:
        evidence = [x for x in evidence if x not in _NEGATIVE_CORE and x != "uncertain_screen_content"]

    scene = scene_to_string(raw.get("scene"))
    if scene is None:
        scene = scene_to_string(raw.get("scenes"))

    return {
        "quality": {
            "brightness": "normal",
            "blur": "low",
            "usable": bool(raw.get("image_quality_usable", (raw.get("image_quality") or {}).get("usable", True))),
            "issues": [],
        },
        "scene": scene,
        "objects": normalize_objects(raw.get("objects", []), confidence, evidence),
        "visible_text": [str(t) for t in as_list(raw.get("text_observed"))],
        "visual_evidence": [],
        "study_visual_evidence": [x for x in evidence if x in STUDY_EVIDENCE],
        "water_visual_evidence": [],
        "exercise_visual_evidence": [],
    }


def _main() -> None:
    raw = json.loads(INPUT.read_text(encoding="utf-8"))
    normalized = normalize_study_evidence(raw)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(normalized, ensure_ascii=False, indent=2))
    print("[INFO] saved:", OUTPUT)


if __name__ == "__main__":
    _main()
