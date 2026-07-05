import argparse
import json
import re
from pathlib import Path

import torch
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info


DEFAULT_MODEL = "Qwen/Qwen2.5-VL-3B-Instruct"


EVIDENCE_PROMPT = """
You are a vision evidence extractor for an AI schedule verification app.

Your job:
- Look only at visible evidence in the image.
- Do NOT decide final verification.
- Do NOT output verified, rejected, or retake_required.
- Extract objects, scenes, text, positive evidence, negative evidence, uncertain evidence, and image quality.
- Return ONLY valid JSON.
- No markdown.
- No explanation outside JSON.

Allowed verification_type values:
- water
- study
- exercise

For water verification, focus on:
- containers: cup, glass, tumbler, water_bottle, pet_bottle, water_container
- positive evidence: visible_water, visible_clear_liquid, filled_container, sealed_water_bottle
- negative evidence: empty_container, non_water_beverage
- uncertain evidence: opaque_closed_container, uncertain_liquid

Water verification principles (MVP, follow strictly):
- Use these exact snake_case evidence tokens (e.g. visible_water), not free-form sentences.
- A transparent glass containing clear liquid MUST produce visible_water or visible_clear_liquid.
- If a cup/glass visibly contains clear liquid, ALSO include filled_container.
- Do NOT output only "glass" or "cup" as evidence when clear liquid is visible; always add the liquid evidence.
- If the glass has clear transparent liquid, treat it as water evidence for MVP (visible_clear_liquid + filled_container). Do NOT label it non_water_beverage or opaque_closed_container.
- An empty glass/cup MUST output empty_container.
- Coffee or any colored/opaque beverage MUST output non_water_beverage.
- Only use opaque_closed_container / uncertain_liquid when the liquid genuinely cannot be seen; never together with clearly visible clear liquid.
- A water dispenser/purifier pouring into a container MUST output water_stream and receiving_water.

Be conservative about the AMOUNT of liquid (avoid false positives):
- Do NOT output filled_container unless a meaningful amount of clear liquid is visibly present.
- If the cup/glass looks empty, almost empty, has only a tiny amount, a few drops, or liquid only at the bottom, output empty_container or uncertain_liquid, NOT filled_container.
- Reflections, transparent glass edges, or background color must NOT be interpreted as water.
- If the amount of liquid is unclear, prefer uncertain_liquid instead of filled_container.
- A false positive is worse than a false negative for verification. For borderline transparent cups, be conservative.
- Also report the observed amount in the "water_amount" field: one of none, tiny, partial, filled, uncertain.
  Use "none" for empty, "tiny" for a few drops / only at the bottom, "partial" for clearly some but not full,
  "filled" for a clearly filled container, "uncertain" if the amount cannot be judged.

For study verification, focus on:
- paper study evidence: open_textbook, open_workbook, handwritten_notes, highlighted_text, problem_solving_material
- digital study evidence: study_content_on_screen, lecture_video, educational_document, code_editor
- negative evidence: gaming_content, entertainment_video, social_media, shopping_content
- uncertain evidence: uncertain_screen_content

For exercise verification, focus on:
- gym: gym_environment, treadmill, dumbbell, barbell, weight_machine, bench
- running: running_track, treadmill, outdoor_running_path, sports_field
- swimming: swimming_pool, lane_rope, swim_cap, goggles
- yoga: yoga_mat, yoga_studio, yoga_pose
- pilates: reformer, pilates_equipment, pilates_studio
- home_workout: exercise_mat, resistance_band, dumbbell, kettlebell, pullup_bar, home_workout_pose
- negative evidence: unrelated_room, desk_environment, office_environment, clearly_wrong_activity_environment

Return JSON with this exact schema:
{
  "verification_type": "<water|study|exercise>",
  "activity_type": "<gym|running|swimming|yoga|pilates|home_workout|null>",
  "water_amount": "<none|tiny|partial|filled|uncertain>",
  "image_quality": {
    "usable": true,
    "issues": []
  },
  "objects": [],
  "scenes": [],
  "visual_evidence": [],
  "negative_evidence": [],
  "uncertain_evidence": [],
  "text_observed": [],
  "confidence": 0.0
}
"""


def extract_json(text: str) -> dict:
    text = text.strip()

    # Remove common markdown fences if the model accidentally emits them.
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: extract the first JSON-looking object.
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model output:\n{text}")

    return json.loads(match.group(0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Path to image file")
    parser.add_argument("--verification-type", required=True, choices=["water", "study", "exercise"])
    parser.add_argument(
        "--activity-type",
        default=None,
        choices=["gym", "running", "swimming", "yoga", "pilates", "home_workout"],
        help="Required only for exercise",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    image_path = Path(args.image).expanduser().resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    if args.verification_type == "exercise" and not args.activity_type:
        raise ValueError("--activity-type is required when --verification-type exercise")

    user_prompt = (
        EVIDENCE_PROMPT
        + f"\n\nCurrent verification_type: {args.verification_type}\n"
        + f"Current activity_type: {args.activity_type if args.activity_type else 'null'}\n"
    )

    print(f"[INFO] Loading model: {args.model}")
    print(f"[INFO] Image: {image_path}")
    print(f"[INFO] CUDA available: {torch.cuda.is_available()}")

    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        args.model,
        torch_dtype="auto",
        device_map="auto",
    )

    processor = AutoProcessor.from_pretrained(args.model)

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": str(image_path)},
                {"type": "text", "text": user_prompt},
            ],
        }
    ]

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
    )

    inputs = inputs.to(model.device)

    print("[INFO] Running inference...")
    with torch.inference_mode():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
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

    print("\n[RAW OUTPUT]")
    print(output_text)

    data = extract_json(output_text)

    # Force caller-provided type to prevent model drift.
    data["verification_type"] = args.verification_type
    if args.verification_type != "exercise":
        data["activity_type"] = None
    else:
        data["activity_type"] = args.activity_type

    print("\n[PARSED JSON]")
    print(json.dumps(data, ensure_ascii=False, indent=2))

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        output_path = Path("local_eval/qwen_vlm_eval/outputs") / f"{image_path.stem}_qwen_evidence.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[INFO] Saved: {output_path}")


if __name__ == "__main__":
    main()
