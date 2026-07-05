"""Qwen2.5-VL-3B 운동 인증 배치 평가 (gym + home_workout MVP).

run_qwen_water_batch.py의 운동 버전. exercise_manifest.json의 이미지를 순회하며
run_qwen_single.py와 동일한 방식으로 Qwen을 실행하고, 각 이미지의 exercise_activity_type
컨텍스트로 Rule Engine 판정을 낸다.

    image → Qwen 증거 추출(raw) → normalize_exercise_output → VisionAnalysis
          → evaluate_image_verification("exercise", ..., ctx(exercise_activity_type)) → PASS/FAIL

산출물 (기본 local_eval/qwen_vlm_eval/outputs/exercise_batch/):
    {stem}_raw.json / {stem}_raw_text.txt / {stem}_normalized.json / {stem}_result.json
    exercise_qwen_batch_report.csv

라벨 매핑: verified → PASS, rejected → FAIL, retake_required → BORDERLINE_CASE.
expected_label이 BORDERLINE이면 predicted가 PASS만 아니면 ok=True.

실행:
    python local_eval/qwen_vlm_eval/scripts/run_qwen_exercise_batch.py --limit 3
    python local_eval/qwen_vlm_eval/scripts/run_qwen_exercise_batch.py
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parents[2]

for p in (str(ROOT), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from normalize_exercise_output import normalize_exercise_evidence  # noqa: E402

from backend.database.schema.image_verification_schema import (  # noqa: E402
    ImageVerificationContext,
    VisionAnalysis,
)
from backend.services.image_verification_rule_engine import (  # noqa: E402
    evaluate_image_verification,
)

DEFAULT_MODEL = "Qwen/Qwen2.5-VL-3B-Instruct"
DEFAULT_MANIFEST = ROOT / "data" / "test_images" / "exercise" / "exercise_manifest.json"
DEFAULT_OUTPUT_DIR = ROOT / "local_eval" / "qwen_vlm_eval" / "outputs" / "exercise_batch"

ENGINE_TO_PREDICTED = {
    "verified": "PASS",
    "rejected": "FAIL",
    "retake_required": "BORDERLINE_CASE",
}

CSV_FIELDS = [
    "filename",
    "source",
    "exercise_activity_type",
    "expected_label",
    "predicted_label",
    "engine_result",
    "score",
    "mandatory_passed",
    "ok",
    "exercise_visual_evidence",
    "objects",
    "raw_output_path",
    "normalized_output_path",
    "result_output_path",
    "error",
]
RESULT_FIELDS = CSV_FIELDS[:-2] + ["rule_evidence", "result_output_path", "error"]


def extract_json(text: str) -> dict:
    text = text.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    candidate = match.group(0) if match else text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        try:
            from json_repair import repair_json

            return json.loads(repair_json(candidate))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Could not parse JSON from model output: {exc}")


def load_model(model_id: str):
    import torch  # noqa: F401
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    print(f"[INFO] loading model: {model_id}")
    print(f"[INFO] cuda available: {torch.cuda.is_available()}")
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_id, torch_dtype="auto", device_map="auto"
    )
    processor = AutoProcessor.from_pretrained(model_id)
    return model, processor


def build_prompt(activity_type: str) -> str:
    from run_qwen_single import EVIDENCE_PROMPT

    return (
        EVIDENCE_PROMPT
        + "\n\nCurrent verification_type: exercise\n"
        + f"Current activity_type: {activity_type}\n"
    )


def generate_raw_text(model, processor, image_path: Path, activity_type: str, max_new_tokens: int) -> str:
    import torch
    from qwen_vl_utils import process_vision_info

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": str(image_path.resolve())},
                {"type": "text", "text": build_prompt(activity_type)},
            ],
        }
    ]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt"
    ).to(model.device)
    with torch.inference_mode():
        generated_ids = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated_ids)]
    return processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]


def _empty_cuda_cache() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001
        pass
    gc.collect()


def _rel(path: Path) -> str:
    """ROOT 하위면 상대경로, 아니면 절대경로."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _write_result_json(output_dir: Path, stem: str, record: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / f"{stem}_result.json"
    record["result_output_path"] = _rel(result_path)
    payload = {k: record.get(k) for k in RESULT_FIELDS}
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def process_entry(entry: dict, output_text: str, output_dir: Path) -> dict:
    stem = Path(entry["filename"]).stem
    source = entry.get("source", "generated")
    expected = entry["expected_label"]
    activity = entry.get("exercise_activity_type")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_text_path = output_dir / f"{stem}_raw_text.txt"
    raw_json_path = output_dir / f"{stem}_raw.json"
    normalized_path = output_dir / f"{stem}_normalized.json"

    raw_text_path.write_text(output_text, encoding="utf-8")

    parse_error = None
    try:
        raw = extract_json(output_text)
        raw["verification_type"] = "exercise"
        raw["activity_type"] = activity
        raw_json_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        raw_output_path = raw_json_path
    except Exception as exc:  # noqa: BLE001
        parse_error = str(exc)
        raw = {}
        raw_output_path = raw_text_path
        print(f"[WARN] {stem}: JSON 파싱 실패 → {raw_text_path.name} 만 저장 ({parse_error})")

    normalized = normalize_exercise_evidence(raw, activity)
    normalized_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    analysis = VisionAnalysis.model_validate(normalized)
    ctx = ImageVerificationContext(exercise_activity_type=activity)
    result = evaluate_image_verification("exercise", analysis, ctx)

    engine_result = result.result
    predicted = ENGINE_TO_PREDICTED.get(engine_result, "UNKNOWN")
    if expected == "BORDERLINE":
        ok = predicted != "PASS"
    else:
        ok = (expected == "PASS") == (predicted == "PASS")

    record = {
        "filename": entry["filename"],
        "source": source,
        "exercise_activity_type": activity,
        "expected_label": expected,
        "predicted_label": predicted,
        "engine_result": engine_result,
        "score": result.score,
        "mandatory_passed": result.mandatory_passed,
        "ok": ok,
        "exercise_visual_evidence": list(normalized.get("exercise_visual_evidence", [])),
        "objects": [o["label"] for o in normalized.get("objects", [])],
        "rule_evidence": [e.model_dump() for e in result.rule_evidence],
        "raw_output_path": _rel(raw_output_path),
        "normalized_output_path": _rel(normalized_path),
        "error": parse_error or "",
    }
    _write_result_json(output_dir, stem, record)
    print(
        f"[RESULT] {entry['filename']:<48} act={str(activity):<12} expected={expected:<10} "
        f"predicted={predicted:<15} engine={engine_result:<16} score={result.score} ok={ok}"
    )
    return record


def make_error_record(entry: dict, error: str, engine_result: str, output_dir: Path) -> dict:
    stem = Path(entry["filename"]).stem
    record = {
        "filename": entry["filename"], "source": entry.get("source", "generated"),
        "exercise_activity_type": entry.get("exercise_activity_type"),
        "expected_label": entry.get("expected_label", ""), "predicted_label": "ERROR",
        "engine_result": engine_result, "score": "", "mandatory_passed": "", "ok": False,
        "exercise_visual_evidence": [], "objects": [], "rule_evidence": [],
        "raw_output_path": "", "normalized_output_path": "", "error": error,
    }
    _write_result_json(output_dir, stem, record)
    return record


def load_manifest_images(manifest_path: Path, limit, start_index) -> list[dict]:
    images = json.loads(manifest_path.read_text(encoding="utf-8"))["images"]
    if start_index:
        images = images[start_index:]
    if limit is not None:
        images = images[:limit]
    return images


def _csv_value(value):
    return ";".join(str(v) for v in value) if isinstance(value, list) else value


def write_report(rows: list[dict], report_path: Path) -> None:
    with report_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _csv_value(row.get(k, "")) for k in CSV_FIELDS})
    print(f"\n[report] wrote {_rel(report_path)} ({len(rows)} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch Qwen2.5-VL exercise verification eval (gym + home_workout).")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=None, help="처음 N장만 처리")
    parser.add_argument("--start-index", type=int, default=0, help="앞에서 N장 건너뛰기")
    parser.add_argument("--skip-existing", action="store_true", help="result.json이 이미 있으면 건너뜀")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    output_dir = Path(args.output_dir)
    report_path = output_dir / "exercise_qwen_batch_report.csv"
    output_dir.mkdir(parents=True, exist_ok=True)

    images = load_manifest_images(manifest_path, args.limit, args.start_index)
    print(f"[INFO] manifest images to process: {len(images)}")

    model, processor = load_model(args.model)

    rows: list[dict] = []
    for entry in images:
        stem = Path(entry["filename"]).stem
        if args.skip_existing and (output_dir / f"{stem}_result.json").exists():
            print(f"[SKIP] {entry['filename']} (result.json exists)")
            continue
        image_path = ROOT / entry["image_path"]
        print(f"\n[RUN] {entry['filename']} (activity={entry.get('exercise_activity_type')}, expected={entry['expected_label']})")
        if not image_path.exists():
            print(f"[ERROR] image not found: {image_path}")
            rows.append(make_error_record(entry, f"image not found: {image_path}", "image_not_found", output_dir))
            continue
        try:
            output_text = generate_raw_text(
                model, processor, image_path, entry.get("exercise_activity_type"), args.max_new_tokens
            )
            rows.append(process_entry(entry, output_text, output_dir))
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {entry['filename']}: {exc}")
            rows.append(make_error_record(entry, str(exc), "exception", output_dir))
        finally:
            _empty_cuda_cache()

    write_report(rows, report_path)

    considered = [r for r in rows if r["predicted_label"] != "ERROR"]
    correct = sum(1 for r in considered if r["ok"])
    fp = sum(1 for r in considered if r["predicted_label"] == "PASS" and r["expected_label"] != "PASS")
    print(f"\n[SUMMARY] ok={correct}/{len(considered)} false_positive(PASS)={fp} errors={len(rows) - len(considered)}")


if __name__ == "__main__":
    main()
