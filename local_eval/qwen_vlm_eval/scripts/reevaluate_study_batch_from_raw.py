import csv
import json
from pathlib import Path

from backend.database.schema.image_verification_schema import (
    VisionAnalysis,
    ImageVerificationContext,
)
from backend.services.image_verification_rule_engine import evaluate_image_verification


RAW_DIR = Path("local_eval/qwen_vlm_eval/outputs/study_batch")
REPORT_PATH = RAW_DIR / "study_batch_report_v2.csv"

EXPECTED = {
    "study_01": "verified",
    "study_02": "verified",
    "study_03": "verified",
    "study_04": "verified",
    "study_05": "verified",
    "study_06": "verified",
    "study_07": "verified",
    "study_08": "rejected",
    "study_09": "rejected",
    "study_10": "rejected",
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


def flatten(value):
    if value is None:
        return []
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(flatten(item))
        return out
    return [value]


def label_of(item):
    if isinstance(item, dict):
        return item.get("label") or item.get("type") or item.get("name")
    if isinstance(item, str):
        return item
    return None


def text_to_labels(text):
    t = str(text).lower()
    labels = []

    if "open_textbook" in t or "open textbook" in t or "textbook" in t:
        labels.append("open_textbook")
    if "open_workbook" in t or "open workbook" in t or "workbook" in t:
        labels.append("open_workbook")
    if "handwritten_notes" in t or "handwritten" in t or "notes" in t or "holding a pen" in t:
        labels.append("handwritten_notes")
    if "highlighted_text" in t or "highlight" in t:
        labels.append("highlighted_text")
    if "problem_solving_material" in t or "problem" in t or "solving" in t or "diagram" in t:
        labels.append("problem_solving_material")
    if "study_content_on_screen" in t or "study content" in t:
        labels.append("study_content_on_screen")
    if "lecture_video" in t or "lecture video" in t:
        labels.append("lecture_video")
    if "educational_document" in t or "educational document" in t or "pdf" in t:
        labels.append("educational_document")
    if "code_editor" in t or "code editor" in t:
        labels.append("code_editor")
    if "study_timer" in t or "timer" in t:
        labels.append("study_timer")

    if "gaming_content" in t or "game" in t:
        labels.append("gaming_content")
    if "entertainment_video" in t or "entertainment" in t:
        labels.append("entertainment_video")
    if "social_media" in t or "social media" in t:
        labels.append("social_media")
    if "shopping_content" in t or "shopping" in t:
        labels.append("shopping_content")
    if "non_study_screen" in t or "non-study" in t:
        labels.append("non_study_screen")
    if "uncertain_screen_content" in t:
        labels.append("uncertain_screen_content")

    return labels


def evidence_from(value):
    labels = []

    for item in flatten(value):
        if item is None or item == []:
            continue

        lb = label_of(item)
        if lb:
            if lb in STUDY_EVIDENCE:
                labels.append(lb)
            else:
                labels.extend(text_to_labels(lb))

        if isinstance(item, str) and item not in STUDY_EVIDENCE:
            labels.extend(text_to_labels(item))

    return labels


def unique(items):
    out = []
    seen = set()
    for x in items:
        if not x or x == "[]":
            continue
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def scene_to_string(raw):
    scene = raw.get("scene")
    scenes = raw.get("scenes")

    target = scene if scene else scenes
    for item in flatten(target):
        lb = label_of(item)
        if lb:
            return str(lb)
    return None


def normalize(raw):
    confidence = float(raw.get("confidence", 0.8))

    evidence = []
    evidence += evidence_from(raw.get("objects"))
    evidence += evidence_from(raw.get("scene"))
    evidence += evidence_from(raw.get("scenes"))
    evidence += evidence_from(raw.get("visual_evidence"))
    evidence += evidence_from(raw.get("negative_evidence"))
    evidence += evidence_from(raw.get("uncertain_evidence"))
    evidence = unique(evidence)

    positive_core = {
        "open_textbook",
        "open_workbook",
        "handwritten_notes",
        "highlighted_text",
        "problem_solving_material",
        "study_content_on_screen",
        "lecture_video",
        "educational_document",
        "code_editor",
    }
    negative_core = {
        "gaming_content",
        "entertainment_video",
        "social_media",
        "shopping_content",
        "non_study_screen",
    }

    positive_count = len([x for x in evidence if x in positive_core])
    negative_count = len([x for x in evidence if x in negative_core])

    if positive_count >= 2 and negative_count >= 4:
        evidence = [x for x in evidence if x not in negative_core and x != "uncertain_screen_content"]

    objects = []
    existing = set()

    for item in flatten(raw.get("objects")):
        lb = label_of(item)
        if not lb:
            continue
        mapped = OBJECT_LABEL_MAP.get(str(lb), str(lb))
        if mapped not in STUDY_EVIDENCE and mapped not in existing:
            objects.append({"label": mapped, "confidence": confidence, "evidence": None})
            existing.add(mapped)
        elif mapped in OBJECT_LABEL_MAP.values() and mapped not in existing:
            objects.append({"label": mapped, "confidence": confidence, "evidence": None})
            existing.add(mapped)

    for ev in evidence:
        mapped = OBJECT_LABEL_MAP.get(ev)
        if mapped and mapped not in existing:
            objects.append({"label": mapped, "confidence": confidence, "evidence": "mapped_from_evidence:" + ev})
            existing.add(mapped)

    normalized = {
        "quality": {
            "brightness": "normal",
            "blur": "low",
            "usable": bool(raw.get("image_quality_usable", True)),
            "issues": [],
        },
        "scene": scene_to_string(raw),
        "objects": objects,
        "visible_text": flatten(raw.get("text_observed")),
        "visual_evidence": evidence,
        "study_visual_evidence": [x for x in evidence if x in STUDY_EVIDENCE],
        "water_visual_evidence": [],
        "exercise_visual_evidence": [],
    }
    return normalized


def main():
    rows = []

    for i in range(1, 11):
        stem = f"study_{i:02d}"
        raw_path = RAW_DIR / f"{stem}_raw.json"
        expected = EXPECTED[stem]

        try:
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
            normalized = normalize(raw)

            analysis = VisionAnalysis(**normalized)
            result = evaluate_image_verification("study", analysis, ImageVerificationContext())

            actual = result.result
            ok = actual == expected
            evidence = ",".join(normalized["study_visual_evidence"])

            (RAW_DIR / f"{stem}_normalized_v2.json").write_text(
                json.dumps(normalized, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            print(f"[RESULT] {stem}: expected={expected} actual={actual} score={result.score} ok={ok} evidence={evidence}")

            rows.append({
                "image": stem,
                "expected": expected,
                "actual": actual,
                "ok": ok,
                "score": result.score,
                "mandatory_passed": result.mandatory_passed,
                "study_visual_evidence": evidence,
            })

        except Exception as e:
            print(f"[ERROR] {stem}: {e}")
            rows.append({
                "image": stem,
                "expected": expected,
                "actual": "ERROR",
                "ok": False,
                "score": "",
                "mandatory_passed": "",
                "study_visual_evidence": "",
            })

    with REPORT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["image", "expected", "actual", "ok", "score", "mandatory_passed", "study_visual_evidence"],
        )
        writer.writeheader()
        writer.writerows(rows)

    correct = sum(1 for r in rows if r["ok"] is True)
    print(f"\n[SUMMARY] correct={correct}/{len(rows)}")
    print("[INFO] report:", REPORT_PATH)


if __name__ == "__main__":
    main()
