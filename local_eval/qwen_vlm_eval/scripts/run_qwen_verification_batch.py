"""공통 Qwen 인증 batch runner — water / exercise / study를 하나의 인터페이스로 실행.

기존 개별 runner(run_qwen_water_batch.py / run_qwen_exercise_batch.py / run_qwen_study_batch.py)는
그대로 유지한다. 이 러너는 verification_type만 바꿔서 동일한 파이프라인을 돌린다:

    image → Qwen 증거 추출(raw) → normalize_{type}_evidence → VisionAnalysis
          → evaluate_image_verification(type, analysis, context) → PASS/FAIL

    python local_eval/qwen_vlm_eval/scripts/run_qwen_verification_batch.py --verification-type water --limit 2
    python local_eval/qwen_vlm_eval/scripts/run_qwen_verification_batch.py --verification-type exercise --limit 2
    python local_eval/qwen_vlm_eval/scripts/run_qwen_verification_batch.py --verification-type study --limit 2

옵션: --verification-type(필수) --manifest --output-dir --model --limit --start-index --skip-existing

라벨 매핑: verified→PASS, rejected→FAIL, retake_required→BORDERLINE_CASE.
expected_label=BORDERLINE이면 predicted가 PASS만 아니면 ok=True.

무거운 의존성(torch/transformers/qwen_vl_utils)은 추론 시점에만 lazy import 하므로,
모델 없이도 config/manifest/normalize/rule-engine/CSV 로직을 import 해 검증할 수 있다.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parents[2]
for p in (str(ROOT), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from normalize_water_output import normalize_water_evidence  # noqa: E402
from normalize_exercise_output import normalize_exercise_evidence  # noqa: E402
from normalize_qwen_output import normalize_study_evidence  # noqa: E402

from backend.database.schema.image_verification_schema import (  # noqa: E402
    ImageVerificationContext,
    VisionAnalysis,
)
from backend.services.image_verification_rule_engine import (  # noqa: E402
    evaluate_image_verification,
)

DEFAULT_MODEL = "Qwen/Qwen2.5-VL-3B-Instruct"

ENGINE_TO_PREDICTED = {
    "verified": "PASS",
    "rejected": "FAIL",
    "retake_required": "BORDERLINE_CASE",
}
STUDY_DECISION_TO_LABEL = {
    "verified": "PASS",
    "rejected": "FAIL",
    "retake_required": "BORDERLINE",
}

# 통합 CSV/record 컬럼: 공통 + 타입 전용(해당 없으면 빈 문자열)
CSV_FIELDS = [
    "filename", "source", "verification_type", "expected_label", "predicted_label",
    "engine_result", "score", "mandatory_passed", "ok", "visual_evidence", "objects",
    "raw_output_path", "normalized_output_path", "result_output_path", "error",
    # exercise 전용
    "exercise_activity_type",
    # study 전용
    "image_id", "expected_decision", "expected_study_evidence",
]


@dataclass
class VConfig:
    verification_type: str
    default_manifest: Path
    default_output_dir: Path
    manifest_format: str          # "json" | "jsonl"
    evidence_field: str           # VisionAnalysis 내 어떤 evidence를 리포트할지
    normalize: Callable           # (raw: dict, entry: dict) -> dict
    build_context: Callable       # (entry: dict) -> ImageVerificationContext
    prompt_activity: Callable     # (entry: dict) -> str


CONFIGS: dict[str, VConfig] = {
    "water": VConfig(
        verification_type="water",
        default_manifest=ROOT / "data" / "test_images" / "water" / "water_manifest.json",
        default_output_dir=ROOT / "local_eval" / "qwen_vlm_eval" / "outputs" / "water_batch",
        manifest_format="json",
        evidence_field="water_visual_evidence",
        normalize=lambda raw, entry: normalize_water_evidence(raw),
        build_context=lambda entry: ImageVerificationContext(),
        prompt_activity=lambda entry: "null",
    ),
    "exercise": VConfig(
        verification_type="exercise",
        default_manifest=ROOT / "data" / "test_images" / "exercise" / "exercise_manifest.json",
        default_output_dir=ROOT / "local_eval" / "qwen_vlm_eval" / "outputs" / "exercise_batch",
        manifest_format="json",
        evidence_field="exercise_visual_evidence",
        normalize=lambda raw, entry: normalize_exercise_evidence(raw, entry.get("exercise_activity_type")),
        build_context=lambda entry: ImageVerificationContext(exercise_activity_type=entry.get("exercise_activity_type")),
        prompt_activity=lambda entry: entry.get("exercise_activity_type") or "null",
    ),
    "study": VConfig(
        verification_type="study",
        default_manifest=ROOT / "local_eval" / "study_verification_fixture_pack" / "study_ground_truth.jsonl",
        default_output_dir=ROOT / "local_eval" / "qwen_vlm_eval" / "outputs" / "study_batch",
        manifest_format="jsonl",
        evidence_field="study_visual_evidence",
        normalize=lambda raw, entry: normalize_study_evidence(raw),
        build_context=lambda entry: ImageVerificationContext(),
        prompt_activity=lambda entry: "null",
    ),
}

STUDY_IMAGE_BASE = ROOT / "local_eval" / "study_verification_fixture_pack"


def get_config(verification_type: str) -> VConfig:
    if verification_type not in CONFIGS:
        raise ValueError(f"unknown verification_type: {verification_type}")
    return CONFIGS[verification_type]


# ---------------------------------------------------------------------------
# Manifest 로딩 → 공통 entry 형태
# ---------------------------------------------------------------------------

def load_entries(config: VConfig, manifest_path: Path) -> list[dict]:
    if config.manifest_format == "json":
        images = json.loads(manifest_path.read_text(encoding="utf-8"))["images"]
        entries = []
        for e in images:
            entries.append({
                "filename": e["filename"],
                "image_path": e["image_path"],
                "expected_label": e["expected_label"],
                "source": e.get("source", "generated"),
                "verification_type": config.verification_type,
                "exercise_activity_type": e.get("exercise_activity_type", ""),
                "image_id": "",
                "expected_decision": "",
                "expected_study_evidence": "",
                "reason": e.get("reason", ""),
            })
        return entries

    # jsonl (study)
    entries = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        image_id = item["image_id"]
        rel = item.get("image_path", f"images/{image_id}.png")
        full = (STUDY_IMAGE_BASE / rel)
        entries.append({
            "filename": f"{image_id}.png",
            "image_path": _rel(full),
            "expected_label": STUDY_DECISION_TO_LABEL.get(item.get("expected_decision"), "FAIL"),
            "source": "fixture",
            "verification_type": "study",
            "exercise_activity_type": "",
            "image_id": image_id,
            "expected_decision": item.get("expected_decision", ""),
            "expected_study_evidence": ";".join(item.get("expected_study_evidence", []) or []),
            "reason": item.get("notes", ""),
        })
    return entries


# ---------------------------------------------------------------------------
# JSON 추출 / 모델 / 프롬프트 (torch 등은 lazy import)
# ---------------------------------------------------------------------------

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


def build_prompt(verification_type: str, activity_type: str) -> str:
    from run_qwen_single import EVIDENCE_PROMPT

    return (
        EVIDENCE_PROMPT
        + f"\n\nCurrent verification_type: {verification_type}\n"
        + f"Current activity_type: {activity_type}\n"
    )


def generate_raw_text(model, processor, image_path: Path, verification_type: str,
                      activity_type: str, max_new_tokens: int) -> str:
    import torch
    from qwen_vl_utils import process_vision_info

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": str(image_path.resolve())},
                {"type": "text", "text": build_prompt(verification_type, activity_type)},
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


# ---------------------------------------------------------------------------
# 처리 (torch 불필요 — 테스트에서 직접 호출)
# ---------------------------------------------------------------------------

def _rel(path: Path) -> str:
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return str(path)


def _base_record(entry: dict, config: VConfig) -> dict:
    return {
        "filename": entry["filename"],
        "source": entry.get("source", ""),
        "verification_type": config.verification_type,
        "expected_label": entry.get("expected_label", ""),
        "exercise_activity_type": entry.get("exercise_activity_type", ""),
        "image_id": entry.get("image_id", ""),
        "expected_decision": entry.get("expected_decision", ""),
        "expected_study_evidence": entry.get("expected_study_evidence", ""),
    }


def process_entry(entry: dict, output_text: str, config: VConfig, output_dir: Path) -> dict:
    stem = Path(entry["filename"]).stem
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_text_path = output_dir / f"{stem}_raw_text.txt"
    raw_json_path = output_dir / f"{stem}_raw.json"
    normalized_path = output_dir / f"{stem}_normalized.json"

    raw_text_path.write_text(output_text, encoding="utf-8")

    record = _base_record(entry, config)
    try:
        raw = extract_json(output_text)
        raw["verification_type"] = config.verification_type
        if config.verification_type == "exercise":
            raw["activity_type"] = entry.get("exercise_activity_type")
        raw_json_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        raw_output_path = raw_json_path
    except Exception as exc:  # noqa: BLE001
        # JSON 파싱 실패 → raw_text만 저장하고 해당 이미지는 ERROR로 기록 (batch는 계속 진행)
        print(f"[WARN] {stem}: JSON 파싱 실패 → {raw_text_path.name} 만 저장 ({exc})")
        record.update({
            "predicted_label": "ERROR", "engine_result": "parse_error", "score": "",
            "mandatory_passed": "", "ok": False, "visual_evidence": [], "objects": [],
            "rule_evidence": [], "raw_output_path": _rel(raw_text_path),
            "normalized_output_path": "", "error": str(exc),
        })
        _write_result_json(output_dir, stem, record, config)
        return record

    normalized = config.normalize(raw, entry)
    normalized_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    analysis = VisionAnalysis.model_validate(normalized)
    context = config.build_context(entry)
    result = evaluate_image_verification(config.verification_type, analysis, context)

    engine_result = result.result
    predicted = ENGINE_TO_PREDICTED.get(engine_result, "UNKNOWN")
    expected = entry.get("expected_label", "")
    if expected == "BORDERLINE":
        ok = predicted != "PASS"
    else:
        ok = (expected == "PASS") == (predicted == "PASS")

    record.update({
        "predicted_label": predicted,
        "engine_result": engine_result,
        "score": result.score,
        "mandatory_passed": result.mandatory_passed,
        "ok": ok,
        "visual_evidence": list(normalized.get(config.evidence_field, [])),
        "objects": [o["label"] for o in normalized.get("objects", [])],
        "rule_evidence": [e.model_dump() for e in result.rule_evidence],
        "raw_output_path": _rel(raw_output_path),
        "normalized_output_path": _rel(normalized_path),
        "error": "",
    })
    _write_result_json(output_dir, stem, record, config)
    print(
        f"[RESULT] {entry['filename']:<48} type={config.verification_type:<9} "
        f"expected={expected:<10} predicted={predicted:<15} engine={engine_result:<16} "
        f"score={result.score} ok={ok}"
    )
    return record


def make_error_record(entry: dict, error: str, engine_result: str, config: VConfig, output_dir: Path) -> dict:
    record = _base_record(entry, config)
    record.update({
        "predicted_label": "ERROR", "engine_result": engine_result, "score": "",
        "mandatory_passed": "", "ok": False, "visual_evidence": [], "objects": [],
        "rule_evidence": [], "raw_output_path": "", "normalized_output_path": "", "error": error,
    })
    _write_result_json(output_dir, Path(entry["filename"]).stem, record, config)
    return record


def _result_payload_fields(verification_type: str) -> list[str]:
    fields = [
        "filename", "source", "verification_type", "expected_label", "predicted_label",
        "engine_result", "score", "mandatory_passed", "ok", "visual_evidence", "objects",
        "rule_evidence", "raw_output_path", "normalized_output_path", "result_output_path", "error",
    ]
    if verification_type == "exercise":
        fields.append("exercise_activity_type")
    if verification_type == "study":
        fields += ["image_id", "expected_decision", "expected_study_evidence"]
    return fields


def _write_result_json(output_dir: Path, stem: str, record: dict, config: VConfig) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / f"{stem}_result.json"
    record["result_output_path"] = _rel(result_path)
    payload = {k: record.get(k) for k in _result_payload_fields(config.verification_type)}
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _csv_value(value):
    return ";".join(str(v) for v in value) if isinstance(value, list) else value


def write_report(rows: list[dict], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _csv_value(row.get(k, "")) for k in CSV_FIELDS})
    print(f"\n[report] wrote {_rel(report_path)} ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def run(verification_type: str, manifest: str | None, output_dir: str | None, model: str,
        limit: int | None, start_index: int, skip_existing: bool, max_new_tokens: int = 512) -> list[dict]:
    config = get_config(verification_type)
    manifest_path = Path(manifest) if manifest else config.default_manifest
    out_dir = Path(output_dir) if output_dir else config.default_output_dir
    report_path = out_dir / f"{verification_type}_qwen_batch_report.csv"
    out_dir.mkdir(parents=True, exist_ok=True)

    entries = load_entries(config, manifest_path)
    if start_index:
        entries = entries[start_index:]
    if limit is not None:
        entries = entries[:limit]
    print(f"[INFO] verification_type={verification_type} images={len(entries)}")

    model_obj, processor = load_model(model)

    rows: list[dict] = []
    for entry in entries:
        stem = Path(entry["filename"]).stem
        if skip_existing and (out_dir / f"{stem}_result.json").exists():
            print(f"[SKIP] {entry['filename']} (result.json exists)")
            continue
        image_path = ROOT / entry["image_path"]
        print(f"\n[RUN] {entry['filename']} (expected={entry['expected_label']})")
        if not image_path.exists():
            print(f"[ERROR] image not found: {image_path}")
            rows.append(make_error_record(entry, f"image not found: {image_path}", "image_not_found", config, out_dir))
            continue
        try:
            output_text = generate_raw_text(
                model_obj, processor, image_path, verification_type,
                config.prompt_activity(entry), max_new_tokens,
            )
            rows.append(process_entry(entry, output_text, config, out_dir))
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {entry['filename']}: {exc}")
            rows.append(make_error_record(entry, str(exc), "exception", config, out_dir))
        finally:
            _empty_cuda_cache()

    write_report(rows, report_path)
    considered = [r for r in rows if r["predicted_label"] != "ERROR"]
    correct = sum(1 for r in considered if r["ok"])
    fp = sum(1 for r in considered if r["predicted_label"] == "PASS" and r["expected_label"] != "PASS")
    print(f"\n[SUMMARY:{verification_type}] ok={correct}/{len(considered)} "
          f"false_positive(PASS)={fp} errors={len(rows) - len(considered)}")
    return rows


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--max-new-tokens", type=int, default=512)


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified Qwen verification batch runner (water/exercise/study).")
    parser.add_argument("--verification-type", required=True, choices=list(CONFIGS.keys()))
    _add_common_args(parser)
    args = parser.parse_args()
    run(args.verification_type, args.manifest, args.output_dir, args.model,
        args.limit, args.start_index, args.skip_existing, args.max_new_tokens)


def main_with_type(verification_type: str, argv: list[str] | None = None) -> None:
    """개별 wrapper runner에서 호출할 진입점 (--verification-type 고정)."""
    parser = argparse.ArgumentParser(description=f"Qwen {verification_type} verification batch runner.")
    _add_common_args(parser)
    args = parser.parse_args(argv)
    run(verification_type, args.manifest, args.output_dir, args.model,
        args.limit, args.start_index, args.skip_existing, args.max_new_tokens)


if __name__ == "__main__":
    main()
