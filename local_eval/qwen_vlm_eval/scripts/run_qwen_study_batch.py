import csv
import json
import re
from pathlib import Path

import torch
from json_repair import repair_json
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

from backend.database.schema.image_verification_schema import (
    VisionAnalysis,
    ImageVerificationContext,
)
from backend.services.image_verification_rule_engine import evaluate_image_verification


MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
IMAGE_DIR = Path("local_eval/study_verification_fixture_pack/images")
OUTPUT_DIR = Path("local_eval/qwen_vlm_eval/outputs/study_batch")
REPORT_PATH = OUTPUT_DIR / "study_batch_report.csv"

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
    "gaming_content": "monitor",
    "entertainment_video": "monitor",
    "social_media": "monitor",
    "shopping_content": "monitor",
    "non_study_screen": "monitor",
    "uncertain_screen_content": "monitor",
}

PROMPT = """
You are a vision evidence extractor for study verification.

Return only one valid JSON object.
Do not use markdown.
Do not decide verified, rejected, or retake_required.
Use only evidence clearly visible in the image.
Do not copy candidate labels unless they are visible.

Important:
- If the image shows a textbook, workbook, notes, study PDF, lecture, coding screen, or problem-solving material, include the matching study evidence.
- If the image shows a game, entertainment video, social media, shopping, or a non-study screen, include the matching negative evidence.
- If no negative evidence is visible, negative_evidence must be [].
- If the screen exists but content is unclear, use uncertain_screen_content.

JSON schema:
{
  "verification_type": "study",
  "image_quality_usable": true,
  "objects": [],
  "scenes": [],
  "visual_evidence": [],
  "negative_evidence": [],
  "uncertain_evidence": [],
  "text_observed": [],
  "confidence": 0.0
}

Allowed visual_evidence:
open_textbook, open_workbook, handwritten_notes, highlighted_text,
problem_solving_material, study_content_on_screen, lecture_video,
educational_document, code_editor, study_timer

Allowed negative_evidence:
gaming_content, entertainment_video, social_media, shopping_content, non_study_screen, closed_study_materials

Allowed uncertain_evidence:
uncertain_screen_content

Return JSON only.
"""


def extract_json(text):
    text = text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    candidate = match.group(0) if match else text

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        repaired = repair_json(candidate)
        return json.loads(repaired)


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


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


def normalize_objects(raw_objects, evidence, confidence):
    result = []

    for obj in as_list(raw_objects):
        if isinstance(obj, str):
            label = obj
            desc = None
        elif isinstance(obj, dict):
            label = obj.get("label") or obj.get("type") or obj.get("name")
            desc = obj.get("evidence") or obj.get("description")
            if obj.get("position") and not desc:
                desc = "position=" + str(obj.get("position"))
        else:
            continue

        if label:
            result.append({
                "label": OBJECT_LABEL_MAP.get(str(label), str(label)),
                "confidence": float(confidence),
                "evidence": desc,
            })

    existing = {x["label"] for x in result}
    for ev in evidence:
        mapped = OBJECT_LABEL_MAP.get(ev)
        if mapped and mapped not in existing:
            result.append({
                "label": mapped,
                "confidence": float(confidence),
                "evidence": "mapped_from_evidence:" + ev,
            })
            existing.add(mapped)

    return result



def scene_to_string(value):
    if value is None:
        return None

    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        return value.get("label") or value.get("type") or value.get("name") or "study"

    if isinstance(value, list) and value:
        return scene_to_string(value[0])

    return str(value)

def normalize(raw):
    confidence = float(raw.get("confidence", 0.8))

    evidence = []
    evidence += as_list(raw.get("visual_evidence"))
    evidence += as_list(raw.get("negative_evidence"))
    evidence += as_list(raw.get("uncertain_evidence"))
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

    # Qwen sometimes copies many negative candidate labels together even for study images.
    # If strong positive study evidence is present and most negative labels appear together,
    # treat the negative labels as candidate-list leakage rather than visible evidence.
    if positive_count >= 2 and negative_count >= 4:
        evidence = [
            x for x in evidence
            if x not in negative_core and x != "uncertain_screen_content"
        ]

    scene = scene_to_string(raw.get("scene"))
    if not scene and raw.get("scenes"):
        scene = scene_to_string(raw.get("scenes"))

    return {
        "quality": {
            "brightness": "normal",
            "blur": "low",
            "usable": bool(raw.get("image_quality_usable", True)),
            "issues": [],
        },
        "scene": scene,
        "objects": normalize_objects(raw.get("objects", []), evidence, confidence),
        "visible_text": as_list(raw.get("text_observed")),
        "visual_evidence": evidence,
        "study_visual_evidence": [x for x in evidence if x in STUDY_EVIDENCE],
        "water_visual_evidence": [],
        "exercise_visual_evidence": [],
    }


def run_one(model, processor, image_path):
    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "image": str(image_path.resolve())},
            {"type": "text", "text": PROMPT},
        ],
    }]

    text = processor.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    image_inputs, video_inputs = process_vision_info(messages)

    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(model.device)

    with torch.inference_mode():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=False,
        )

    generated_ids_trimmed = [
        out_ids[len(in_ids):]
        for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]

    output_text = processor.batch_decode(
        generated_ids_trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0]

    raw = extract_json(output_text)
    normalized = normalize(raw)

    analysis = VisionAnalysis(**normalized)
    context = ImageVerificationContext()
    result = evaluate_image_verification("study", analysis, context)

    return output_text, raw, normalized, result


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("[INFO] loading model:", MODEL_ID)
    print("[INFO] cuda:", torch.cuda.is_available())
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL_ID,
        torch_dtype="auto",
        device_map="auto",
    )
    processor = AutoProcessor.from_pretrained(MODEL_ID)

    rows = []

    for i in range(1, 11):
        stem = f"study_{i:02d}"
        image_path = IMAGE_DIR / f"{stem}.png"
        expected = EXPECTED[stem]

        print(f"\n[RUN] {stem} expected={expected}")

        try:
            output_text, raw, normalized, result = run_one(model, processor, image_path)
            actual = result.result
            ok = actual == expected

            (OUTPUT_DIR / f"{stem}_raw_text.txt").write_text(output_text, encoding="utf-8")
            (OUTPUT_DIR / f"{stem}_raw.json").write_text(
                json.dumps(raw, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (OUTPUT_DIR / f"{stem}_normalized.json").write_text(
                json.dumps(normalized, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (OUTPUT_DIR / f"{stem}_result.json").write_text(
                json.dumps(result.model_dump(), ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )

            evidence = ",".join(normalized.get("study_visual_evidence", []))
            print(f"[RESULT] {stem}: actual={actual} score={result.score} ok={ok} evidence={evidence}")

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
            fieldnames=[
                "image",
                "expected",
                "actual",
                "ok",
                "score",
                "mandatory_passed",
                "study_visual_evidence",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    correct = sum(1 for r in rows if r["ok"] is True)
    print("\n[SUMMARY]")
    print(f"correct={correct}/{total}")
    print("[INFO] report:", REPORT_PATH)


if __name__ == "__main__":
    main()
