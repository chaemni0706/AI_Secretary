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

def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]

def normalize_objects(raw_objects, confidence):
    result = []
    for obj in as_list(raw_objects):
        if isinstance(obj, str):
            label = obj
            evidence = None
        elif isinstance(obj, dict):
            label = obj.get("label") or obj.get("type") or obj.get("name")
            evidence = obj.get("evidence") or obj.get("description")
            if obj.get("position") and not evidence:
                evidence = "position=" + str(obj.get("position"))
        else:
            continue

        if label:
            result.append({
                "label": OBJECT_LABEL_MAP.get(str(label), str(label)),
                "confidence": float(confidence),
                "evidence": evidence,
            })
    return result

def unique(items):
    result = []
    seen = set()
    for item in items:
        if item is None:
            continue
        item = str(item)
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result

raw = json.loads(INPUT.read_text(encoding="utf-8"))
confidence = float(raw.get("confidence", 0.8))

evidence = []
evidence += as_list(raw.get("visual_evidence"))
evidence += as_list(raw.get("negative_evidence"))
evidence += as_list(raw.get("uncertain_evidence"))
evidence = unique(evidence)

scene = raw.get("scene")
if not scene and isinstance(raw.get("scenes"), list) and raw["scenes"]:
    scene = raw["scenes"][0]

normalized = {
    "quality": {
        "brightness": "normal",
        "blur": "low",
        "usable": bool(raw.get("image_quality_usable", True)),
        "issues": [],
    },
    "scene": scene,
    "objects": normalize_objects(raw.get("objects", []), confidence),
    "visible_text": as_list(raw.get("text_observed")),
    "visual_evidence": evidence,
    "study_visual_evidence": [x for x in evidence if x in STUDY_EVIDENCE],
    "water_visual_evidence": [],
    "exercise_visual_evidence": [],
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(normalized, ensure_ascii=False, indent=2))
print("[INFO] saved:", OUTPUT)
