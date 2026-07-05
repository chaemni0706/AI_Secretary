import json
import re
from pathlib import Path

import torch
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
IMAGE_PATH = "local_eval/study_verification_fixture_pack/images/study_01.png"

PROMPT = """
You are a vision evidence extractor.

Return only one valid JSON object.
Do not use markdown.
Do not decide verified or rejected.
Use only evidence clearly visible in the image.
If there is no negative evidence, use an empty list.

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
gaming_content, entertainment_video, social_media, shopping_content

Allowed uncertain_evidence:
uncertain_screen_content, blurry_text, unclear_material

Return JSON only.
"""

def extract_json(text):
    text = text.strip()
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON found:\n" + text)
        return json.loads(match.group(0))

def main():
    image_path = Path(IMAGE_PATH).resolve()

    print("[INFO] image:", image_path)
    print("[INFO] cuda:", torch.cuda.is_available())

    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL_ID,
        torch_dtype="auto",
        device_map="auto",
    )
    processor = AutoProcessor.from_pretrained(MODEL_ID)

    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "image": str(image_path)},
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

    print("[INFO] running inference...")

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

    print("\n[RAW OUTPUT]")
    print(output_text)

    data = extract_json(output_text)

    output_path = Path("local_eval/qwen_vlm_eval/outputs/study_01_simple_qwen.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n[PARSED JSON]")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print("\n[INFO] saved:", output_path)

if __name__ == "__main__":
    main()
