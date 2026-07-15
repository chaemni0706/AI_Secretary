"""Qwen2.5-VL-3B 물 인증 배치 평가.

water_manifest.json의 18장(uploaded 8 + generated 10)을 순회하며, run_qwen_single.py와
동일한 방식으로 Qwen2.5-VL-3B-Instruct를 실행한다. 각 이미지에 대해:

    image → Qwen 증거 추출(raw) → normalize_water_output → VisionAnalysis → Rule Engine → PASS/FAIL

산출물 (local_eval/qwen_vlm_eval/outputs/water_batch/):
    {stem}_raw.json          파싱된 Qwen raw output (파싱 성공 시)
    {stem}_raw_text.txt      Qwen 원본 텍스트 (항상 저장; 파싱 실패 진단용)
    {stem}_normalized.json   VisionAnalysis 호환 정규화 결과
    water_qwen_batch_report.csv  전체 비교 리포트

라벨 매핑: verified → PASS, rejected → FAIL, retake_required → BORDERLINE_CASE.
`ok`는 "PASS 게이팅 일치"로 계산한다 (기대/예측이 둘 다 PASS이거나 둘 다 non-PASS이면 True).
MVP 기준상 retake_required(BORDERLINE_CASE)와 rejected(FAIL)는 모두 "PASS 아님"으로 동일하게 취급.

실행:
    python local_eval/qwen_vlm_eval/scripts/run_qwen_water_batch.py
    python local_eval/qwen_vlm_eval/scripts/run_qwen_water_batch.py --limit 3
    python local_eval/qwen_vlm_eval/scripts/run_qwen_water_batch.py --model Qwen/Qwen2.5-VL-3B-Instruct

무거운 의존성(torch/transformers/qwen_vl_utils)은 실제 추론 시점에만 lazy import 하므로,
모델 없이도 이 모듈을 import 해 로직을 점검할 수 있다.
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
ROOT = SCRIPTS_DIR.parents[2]  # scripts -> qwen_vlm_eval -> local_eval -> <repo root>

# 저장소 루트(backend import용) + scripts 디렉터리(형제 모듈 import용)를 경로에 추가
for p in (str(ROOT), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from normalize_water_output import normalize_water_evidence  # noqa: E402

from backend.database.schema.image_verification_schema import (  # noqa: E402
    ImageVerificationContext,
    VisionAnalysis,
)
from backend.services.image_verification_rule_engine import (  # noqa: E402
    evaluate_image_verification,
)

DEFAULT_MODEL = "Qwen/Qwen2.5-VL-3B-Instruct"
MANIFEST_PATH = ROOT / "data" / "test_images" / "water" / "water_manifest.json"
OUTPUT_DIR = ROOT / "local_eval" / "qwen_vlm_eval" / "outputs" / "water_batch"
REPORT_PATH = OUTPUT_DIR / "water_qwen_batch_report.csv"

# engine result -> predicted label
ENGINE_TO_PREDICTED = {
    "verified": "PASS",
    "rejected": "FAIL",
    "retake_required": "BORDERLINE_CASE",
}

CSV_FIELDS = [
    "filename",
    "source",
    "expected_label",
    "predicted_label",
    "engine_result",
    "score",
    "mandatory_passed",
    "ok",
    "water_visual_evidence",
    "objects",
    "raw_output_path",
    "normalized_output_path",
    "result_output_path",
    "error",
]

# result.json 에 담는 필드 (CSV_FIELDS + rule_evidence)
RESULT_FIELDS = CSV_FIELDS[:-2] + ["rule_evidence", "result_output_path", "error"]


# ---------------------------------------------------------------------------
# JSON 추출 (run_qwen_single와 동일 전략 + json_repair 폴백)
# ---------------------------------------------------------------------------

def extract_json(text: str) -> dict:
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
        try:
            from json_repair import repair_json

            return json.loads(repair_json(candidate))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Could not parse JSON from model output: {exc}")


# ---------------------------------------------------------------------------
# 모델 로딩 / 추론 (torch 등은 여기서만 lazy import)
# ---------------------------------------------------------------------------

def load_model(model_id: str):
    import torch  # noqa: F401
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    print(f"[INFO] loading model: {model_id}")
    print(f"[INFO] cuda available: {torch.cuda.is_available()}")
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_id,
        torch_dtype="auto",
        device_map="auto",
    )
    processor = AutoProcessor.from_pretrained(model_id)
    return model, processor


def build_prompt() -> str:
    """run_qwen_single.py의 EVIDENCE_PROMPT를 그대로 재사용 (drift 방지). verification_type=water 고정."""
    from run_qwen_single import EVIDENCE_PROMPT

    return (
        EVIDENCE_PROMPT
        + "\n\nCurrent verification_type: water\n"
        + "Current activity_type: null\n"
    )


def generate_raw_text(model, processor, image_path: Path, max_new_tokens: int) -> str:
    import torch
    from qwen_vl_utils import process_vision_info

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": str(image_path.resolve())},
                {"type": "text", "text": build_prompt()},
            ],
        }
    ]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(model.device)

    with torch.inference_mode():
        generated_ids = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)

    trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated_ids)]
    return processor.batch_decode(
        trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0]


def _empty_cuda_cache() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001
        pass
    gc.collect()


# ---------------------------------------------------------------------------
# 이미지 1장 처리 (추론 → 정규화 → Rule Engine → row). generate_fn 주입으로 테스트 가능.
# ---------------------------------------------------------------------------

def process_entry(entry: dict, output_text: str) -> dict:
    """Qwen 원본 텍스트 → raw/normalized 저장 → Rule Engine → CSV row(dict)."""
    stem = Path(entry["filename"]).stem
    source = entry["source"]
    expected = entry["expected_label"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_text_path = OUTPUT_DIR / f"{stem}_raw_text.txt"
    raw_json_path = OUTPUT_DIR / f"{stem}_raw.json"
    normalized_path = OUTPUT_DIR / f"{stem}_normalized.json"

    # 원본 텍스트는 항상 저장 (진단용)
    raw_text_path.write_text(output_text, encoding="utf-8")

    parse_error = None
    try:
        raw = extract_json(output_text)
        raw["verification_type"] = "water"
        raw["activity_type"] = None
        raw_json_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        raw_output_path = raw_json_path
    except Exception as exc:  # noqa: BLE001
        parse_error = str(exc)
        raw = {}  # 파싱 실패 → 빈 증거 → Rule Engine이 FAIL/BORDERLINE로 처리
        raw_output_path = raw_text_path
        print(f"[WARN] {stem}: JSON 파싱 실패 → {raw_text_path.name} 만 저장 ({parse_error})")

    normalized = normalize_water_evidence(raw)
    normalized_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    analysis = VisionAnalysis.model_validate(normalized)
    result = evaluate_image_verification("water", analysis, ImageVerificationContext())

    engine_result = result.result
    predicted = ENGINE_TO_PREDICTED.get(engine_result, "UNKNOWN")
    # PASS 게이팅 일치: 둘 다 PASS이거나 둘 다 non-PASS이면 ok
    ok = (expected == "PASS") == (predicted == "PASS")

    record = {
        "filename": entry["filename"],
        "source": source,
        "expected_label": expected,
        "predicted_label": predicted,
        "engine_result": engine_result,
        "score": result.score,
        "mandatory_passed": result.mandatory_passed,
        "ok": ok,
        "water_visual_evidence": list(normalized.get("water_visual_evidence", [])),
        "objects": [o["label"] for o in normalized.get("objects", [])],
        "rule_evidence": [e.model_dump() for e in result.rule_evidence],
        "raw_output_path": str(raw_output_path.relative_to(ROOT)),
        "normalized_output_path": str(normalized_path.relative_to(ROOT)),
        "error": parse_error or "",
    }
    _write_result_json(stem, record)
    print(
        f"[RESULT] {entry['filename']:<45} expected={expected:<10} "
        f"predicted={predicted:<14} engine={engine_result:<16} score={result.score} ok={ok}"
    )
    return record


def _write_result_json(stem: str, record: dict) -> None:
    """이미지별 result.json 저장. record에 result_output_path를 채워 넣는다."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT_DIR / f"{stem}_result.json"
    record["result_output_path"] = str(result_path.relative_to(ROOT))
    payload = {k: record.get(k) for k in RESULT_FIELDS}
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def make_error_record(entry: dict, error: str, engine_result: str) -> dict:
    """이미지 없음/추론 예외 등 오류 상황에서도 result.json을 남기고 record를 반환."""
    stem = Path(entry["filename"]).stem
    record = {
        "filename": entry["filename"],
        "source": entry.get("source", ""),
        "expected_label": entry.get("expected_label", ""),
        "predicted_label": "ERROR",
        "engine_result": engine_result,
        "score": "",
        "mandatory_passed": "",
        "ok": False,
        "water_visual_evidence": [],
        "objects": [],
        "rule_evidence": [],
        "raw_output_path": "",
        "normalized_output_path": "",
        "error": error,
    }
    _write_result_json(stem, record)
    return record


def load_manifest_images(limit: int | None) -> list[dict]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    images = manifest["images"]
    if limit is not None:
        images = images[:limit]
    return images


def _csv_value(value):
    """리스트는 ';'로 join, 그 외는 그대로."""
    if isinstance(value, list):
        return ";".join(str(v) for v in value)
    return value


def write_report(rows: list[dict]) -> None:
    with REPORT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _csv_value(row.get(k, "")) for k in CSV_FIELDS})
    print(f"\n[report] wrote {REPORT_PATH.relative_to(ROOT)} ({len(rows)} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch Qwen2.5-VL water verification eval.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="HF model id (default: Qwen2.5-VL-3B-Instruct)")
    parser.add_argument("--limit", type=int, default=None, help="처음 N장만 처리 (빠른 점검용)")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    images = load_manifest_images(args.limit)
    print(f"[INFO] manifest images to process: {len(images)}")

    # 모델은 배치 시작 시 한 번만 로드
    model, processor = load_model(args.model)

    rows: list[dict] = []
    for entry in images:
        image_path = ROOT / entry["image_path"]
        print(f"\n[RUN] {entry['filename']} (source={entry['source']}, expected={entry['expected_label']})")
        if not image_path.exists():
            print(f"[ERROR] image not found: {image_path}")
            rows.append(make_error_record(entry, f"image not found: {image_path}", "image_not_found"))
            continue
        try:
            output_text = generate_raw_text(model, processor, image_path, args.max_new_tokens)
            rows.append(process_entry(entry, output_text))
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {entry['filename']}: {exc}")
            rows.append(make_error_record(entry, str(exc), "exception"))
        finally:
            _empty_cuda_cache()  # 이미지별 처리 후 GPU 메모리 정리

    write_report(rows)

    considered = [r for r in rows if r["predicted_label"] != "ERROR"]
    correct = sum(1 for r in considered if r["ok"])
    false_pos = sum(
        1 for r in considered if r["predicted_label"] == "PASS" and r["expected_label"] != "PASS"
    )
    print(f"\n[SUMMARY] ok={correct}/{len(considered)}  false_positive(PASS)={false_pos}  errors={len(rows) - len(considered)}")


if __name__ == "__main__":
    main()
