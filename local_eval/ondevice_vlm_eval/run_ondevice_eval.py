"""On-device VLM 후보 모델 비교 평가 러너 (+ 정량 지표 저장).

동일한 water/exercise/study 테스트셋으로 여러 소형 VLM 후보(MiniCPM-V / MobileVLM /
SmolVLM / Qwen2.5-VL-AWQ)를 비교한다. wakeup은 VLM 대상이 아니므로 평가에서 제외한다.

    image → adapter.analyze() → VisionAnalysis dict → evaluate_image_verification(type, ...) → 판정

실제 모델은 아직 미탑재(stub). --simulate(기본) 모드에서는 각 이미지의 매니페스트 픽스처를
'모델 출력'으로 대체해 파이프라인/리포트 구조를 end-to-end로 검증한다.

실행마다 run_id 폴더(outputs/runs/{timestamp}_{models}_{types}/)에 아래를 저장한다:
    per_image_report.csv / predictions.jsonl / metrics_summary.csv|json /
    confusion_matrix.csv / latency_summary.csv / error_cases.csv /
    experiment_report.md / raw_outputs/ / normalized_outputs/

실행:
    python local_eval/ondevice_vlm_eval/run_ondevice_eval.py
    python local_eval/ondevice_vlm_eval/run_ondevice_eval.py --models mobilevlm,smolvlm
    python local_eval/ondevice_vlm_eval/run_ondevice_eval.py --verification-types water,study
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parents[1]  # ondevice_vlm_eval -> local_eval -> <repo root>
for p in (str(ROOT), str(THIS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import yaml  # noqa: E402

from adapters import ModelNotAvailable, build_adapter  # noqa: E402

from backend.database.schema.image_verification_schema import (  # noqa: E402
    ImageVerificationContext,
    VisionAnalysis,
)
from backend.services.image_verification_rule_engine import evaluate_image_verification  # noqa: E402

CANDIDATES_YAML = THIS_DIR / "model_candidates.yaml"
RUNS_DIR = THIS_DIR / "outputs" / "runs"

WATER_MANIFEST = ROOT / "data" / "test_images" / "water" / "water_manifest.json"
EXERCISE_MANIFEST = ROOT / "data" / "test_images" / "exercise" / "exercise_manifest.json"
STUDY_PACK = ROOT / "local_eval" / "study_verification_fixture_pack"
STUDY_GT = STUDY_PACK / "study_ground_truth.jsonl"
STUDY_FIXTURES = STUDY_PACK / "fixtures"

ENGINE_TO_PREDICTED = {"verified": "PASS", "rejected": "FAIL", "retake_required": "BORDERLINE_CASE"}
STUDY_DECISION_TO_LABEL = {"verified": "PASS", "rejected": "FAIL", "retake_required": "BORDERLINE"}
EVIDENCE_FIELD = {
    "water": "water_visual_evidence",
    "exercise": "exercise_visual_evidence",
    "study": "study_visual_evidence",
}
VERIFICATION_TYPES = ("water", "exercise", "study")  # wakeup 제외
NON_CLASSIFIED = {"SKIPPED", "ERROR", "UNKNOWN"}  # 혼동행렬/지표에서 제외하는 predicted 값

# per_image_report.csv 컬럼 (= 각 row dict 의 키)
CSV_FIELDS = [
    "run_id", "timestamp", "model_name", "model_path", "verification_type", "filename",
    "expected_label", "predicted_label", "engine_result", "ok", "false_positive",
    "false_negative", "latency_ms", "model_load_time_ms", "peak_gpu_memory_mb",
    "model_size_mb", "runtime_target", "visual_evidence", "objects",
    "raw_output_path", "normalized_output_path", "error",
]

METRICS_FIELDS = [
    "model_name", "verification_type", "num_samples", "tp", "tn", "fp", "fn",
    "accuracy", "precision", "recall", "f1", "false_positive_rate", "false_negative_rate",
    "avg_latency_ms", "p50_latency_ms", "p95_latency_ms", "max_latency_ms",
    "model_size_mb", "runtime_target", "android_feasibility",
]
CONFUSION_FIELDS = ["model_name", "verification_type", "tp", "tn", "fp", "fn"]
LATENCY_FIELDS = ["model_name", "verification_type", "avg_latency_ms", "p50_latency_ms",
                  "p95_latency_ms", "min_latency_ms", "max_latency_ms"]


@dataclass
class RunContext:
    run_id: str
    timestamp: str
    run_dir: Path
    raw_dir: Path
    normalized_dir: Path
    write_outputs: bool = True


# ---------------------------------------------------------------------------
# 후보 모델 / 평가 아이템 로딩
# ---------------------------------------------------------------------------

def load_candidates(only: list[str] | None = None) -> list[dict]:
    data = yaml.safe_load(CANDIDATES_YAML.read_text(encoding="utf-8"))
    candidates = data.get("candidates", [])
    if only:
        wanted = set(only)
        candidates = [c for c in candidates if c.get("adapter") in wanted or c.get("model_name") in wanted]
    return candidates


def _load_json_manifest_items(manifest_path: Path, verification_type: str) -> list[dict]:
    images = json.loads(manifest_path.read_text(encoding="utf-8"))["images"]
    return [{
        "verification_type": verification_type,
        "filename": e["filename"],
        "image_path": str(ROOT / e["image_path"]),
        "expected_label": e["expected_label"],
        "exercise_activity_type": e.get("exercise_activity_type"),
        "fixture": e["vision_analysis"],
    } for e in images]


def _load_study_items() -> list[dict]:
    items = []
    for line in STUDY_GT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        gt = json.loads(line)
        image_id = gt["image_id"]
        fixture_path = STUDY_FIXTURES / f"{image_id}.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8")) if fixture_path.exists() else None
        items.append({
            "verification_type": "study",
            "filename": f"{image_id}.png",
            "image_path": str(STUDY_PACK / gt.get("image_path", f"images/{image_id}.png")),
            "expected_label": STUDY_DECISION_TO_LABEL.get(gt.get("expected_decision"), "FAIL"),
            "exercise_activity_type": None,
            "fixture": fixture,
        })
    return items


def load_eval_items(verification_types: list[str]) -> list[dict]:
    items: list[dict] = []
    if "water" in verification_types:
        items += _load_json_manifest_items(WATER_MANIFEST, "water")
    if "exercise" in verification_types:
        items += _load_json_manifest_items(EXERCISE_MANIFEST, "exercise")
    if "study" in verification_types:
        items += _load_study_items()
    return items


# ---------------------------------------------------------------------------
# 평가
# ---------------------------------------------------------------------------

def _context(item: dict) -> ImageVerificationContext:
    if item["verification_type"] == "exercise":
        return ImageVerificationContext(exercise_activity_type=item.get("exercise_activity_type"))
    return ImageVerificationContext()


def _context_dict(item: dict) -> dict:
    return {"verification_type": item["verification_type"],
            "exercise_activity_type": item.get("exercise_activity_type")}


def _label_ok(expected: str, predicted: str) -> bool:
    if expected == "BORDERLINE":
        return predicted != "PASS"
    return (expected == "PASS") == (predicted == "PASS")


def evaluate_model(candidate: dict, items: list[dict], fixture_lookup, simulate: bool,
                   run_ctx: RunContext | None = None) -> list[dict]:
    """한 모델 후보에 대해 전체 아이템 평가. run_ctx가 있으면 normalized_outputs를 파일로 저장."""
    load_t0 = time.perf_counter()
    adapter = build_adapter(candidate["adapter"], meta=candidate, fixture_lookup=fixture_lookup)
    model_load_time_ms = round((time.perf_counter() - load_t0) * 1000, 3)

    run_id = run_ctx.run_id if run_ctx else ""
    timestamp = run_ctx.timestamp if run_ctx else ""
    adapter_key = candidate.get("adapter", "model")

    rows = []
    for item in items:
        vt = item["verification_type"]
        stem = Path(item["filename"]).stem
        t0 = time.perf_counter()
        analysis_dict = None
        error = ""
        try:
            if adapter.available():
                analysis_dict = adapter.analyze(Path(item["image_path"]), vt, _context_dict(item))
            else:
                raise ModelNotAvailable(f"{candidate['model_name']} not available")
        except ModelNotAvailable as exc:
            if not simulate:
                rows.append(_row(candidate, item, run_id=run_id, timestamp=timestamp,
                                 predicted="SKIPPED", engine_result="model_not_available",
                                 ok=False, fp=False, fn=False, latency_ms=0.0,
                                 model_load_time_ms=model_load_time_ms, evidence=[], objects=[],
                                 raw_output_path="", normalized_output_path="", error=str(exc)))
                continue
            analysis_dict = fixture_lookup(item["filename"])  # 픽스처로 시뮬레이션
            error = "simulated_from_fixture"
        latency_ms = round((time.perf_counter() - t0) * 1000, 3)

        if analysis_dict is None:
            rows.append(_row(candidate, item, run_id=run_id, timestamp=timestamp,
                             predicted="ERROR", engine_result="no_fixture", ok=False, fp=False, fn=False,
                             latency_ms=latency_ms, model_load_time_ms=model_load_time_ms,
                             evidence=[], objects=[], raw_output_path="", normalized_output_path="",
                             error="no_fixture_available"))
            continue

        analysis = VisionAnalysis.model_validate(analysis_dict)
        result = evaluate_image_verification(vt, analysis, _context(item))
        predicted = ENGINE_TO_PREDICTED.get(result.result, "UNKNOWN")
        expected = item["expected_label"]
        ok = _label_ok(expected, predicted)
        fp = predicted == "PASS" and expected != "PASS"
        fn = predicted != "PASS" and expected == "PASS"
        evidence = list(getattr(analysis, EVIDENCE_FIELD[vt]))
        objects = [o.label for o in analysis.objects]

        raw_output_path = ""
        normalized_output_path = ""
        if run_ctx and run_ctx.write_outputs:
            # raw_text 가 있으면(future 실제 어댑터) 저장. 현재 mock/simulate에서는 없음 → 빈 값.
            raw_text = analysis_dict.get("_raw_text") if isinstance(analysis_dict, dict) else None
            if raw_text:
                rp = run_ctx.raw_dir / f"{adapter_key}__{stem}.txt"
                rp.write_text(str(raw_text), encoding="utf-8")
                raw_output_path = _rel(rp)
            np_ = run_ctx.normalized_dir / f"{adapter_key}__{stem}.json"
            np_.write_text(json.dumps(analysis_dict, ensure_ascii=False, indent=2), encoding="utf-8")
            normalized_output_path = _rel(np_)

        rows.append(_row(candidate, item, run_id=run_id, timestamp=timestamp,
                         predicted=predicted, engine_result=result.result, ok=ok, fp=fp, fn=fn,
                         latency_ms=latency_ms, model_load_time_ms=model_load_time_ms,
                         evidence=evidence, objects=objects, raw_output_path=raw_output_path,
                         normalized_output_path=normalized_output_path, error=error))
    return rows


def _row(candidate, item, *, run_id, timestamp, predicted, engine_result, ok, fp, fn,
         latency_ms, model_load_time_ms, evidence, objects, raw_output_path,
         normalized_output_path, error, peak_gpu_memory_mb="") -> dict:
    return {
        "run_id": run_id,
        "timestamp": timestamp,
        "model_name": candidate["model_name"],
        "model_path": candidate.get("model_path", ""),
        "verification_type": item["verification_type"],
        "filename": item["filename"],
        "expected_label": item["expected_label"],
        "predicted_label": predicted,
        "engine_result": engine_result,
        "ok": ok,
        "false_positive": fp,
        "false_negative": fn,
        "latency_ms": latency_ms,
        "model_load_time_ms": model_load_time_ms,
        "peak_gpu_memory_mb": peak_gpu_memory_mb,  # simulate/stub 에서는 미측정("")
        "model_size_mb": candidate.get("model_size_mb", ""),
        "runtime_target": candidate.get("runtime_target", ""),
        "visual_evidence": ";".join(evidence),
        "objects": ";".join(objects),
        "raw_output_path": raw_output_path,
        "normalized_output_path": normalized_output_path,
        "error": error,
    }


def _rel(path: Path) -> str:
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# 지표 계산
# ---------------------------------------------------------------------------

def _classified(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["predicted_label"] not in NON_CLASSIFIED]


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return round(float(s[0]), 3)
    idx = min(len(s) - 1, max(0, math.ceil(q / 100.0 * len(s)) - 1))
    return round(float(s[idx]), 3)


def _confusion(rows: list[dict]) -> dict[str, int]:
    tp = tn = fp = fn = 0
    for r in rows:
        ep = r["expected_label"] == "PASS"
        pp = r["predicted_label"] == "PASS"
        if ep and pp:
            tp += 1
        elif not ep and not pp:
            tn += 1
        elif not ep and pp:
            fp += 1
        else:
            fn += 1
    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn}


def _latency_stats(rows: list[dict]) -> dict[str, float]:
    vals = [float(r["latency_ms"]) for r in rows if isinstance(r["latency_ms"], (int, float))]
    return {
        "avg_latency_ms": round(sum(vals) / len(vals), 3) if vals else 0.0,
        "p50_latency_ms": _percentile(vals, 50),
        "p95_latency_ms": _percentile(vals, 95),
        "min_latency_ms": round(min(vals), 3) if vals else 0.0,
        "max_latency_ms": round(max(vals), 3) if vals else 0.0,
    }


def _metrics_for(rows: list[dict], model_name: str, vtype: str, meta: dict) -> dict:
    cm = _confusion(rows)
    tp, tn, fp, fn = cm["tp"], cm["tn"], cm["fp"], cm["fn"]
    n = tp + tn + fp + fn
    acc = (tp + tn) / n if n else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    fnr = fn / (fn + tp) if (fn + tp) else 0.0
    lat = _latency_stats(rows)
    return {
        "model_name": model_name,
        "verification_type": vtype,
        "num_samples": n,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "false_negative_rate": round(fnr, 4),
        "avg_latency_ms": lat["avg_latency_ms"],
        "p50_latency_ms": lat["p50_latency_ms"],
        "p95_latency_ms": lat["p95_latency_ms"],
        "max_latency_ms": lat["max_latency_ms"],
        "model_size_mb": meta.get("model_size_mb", ""),
        "runtime_target": meta.get("runtime_target", ""),
        "android_feasibility": meta.get("android_feasibility", ""),
    }


def compute_metrics(rows: list[dict], model_meta: dict[str, dict]) -> list[dict]:
    """모델별 × (인증타입별 + ALL) 집계 지표."""
    classified = _classified(rows)
    models = [r["model_name"] for r in rows]
    seen_models = list(dict.fromkeys(models))
    out = []
    for model in seen_models:
        meta = model_meta.get(model, {})
        model_rows = [r for r in classified if r["model_name"] == model]
        for vt in VERIFICATION_TYPES:
            vt_rows = [r for r in model_rows if r["verification_type"] == vt]
            if vt_rows:
                out.append(_metrics_for(vt_rows, model, vt, meta))
        # 모델 전체 롤업
        if model_rows:
            out.append(_metrics_for(model_rows, model, "ALL", meta))
    return out


# ---------------------------------------------------------------------------
# 파일 저장
# ---------------------------------------------------------------------------

def _write_csv(rows: list[dict], fields: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_report(rows: list[dict], output: Path) -> None:
    """per_image_report.csv (하위호환: 기존 테스트가 이 함수를 사용)."""
    _write_csv(rows, CSV_FIELDS, output)
    print(f"[report] wrote {_rel(output)} ({len(rows)} rows)")


def write_predictions_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_error_cases(rows: list[dict], path: Path) -> None:
    """ok=False 또는 error 가 있는 row (false_positive 포함) 만 저장."""
    err = [r for r in rows if (not r["ok"]) or r.get("error")]
    _write_csv(err, CSV_FIELDS, path)
    return err


def _fmt(v) -> str:
    return "" if v == "" or v is None else str(v)


def write_experiment_report(rows: list[dict], metrics: list[dict], run_ctx: RunContext,
                            models: list[str], types: list[str], simulate: bool) -> None:
    classified = _classified(rows)
    total = len(rows)
    fp_rows = [r for r in rows if r["false_positive"]]
    all_rollup = {m["model_name"]: m for m in metrics if m["verification_type"] == "ALL"}

    lines = []
    lines.append(f"# On-device VLM 실험 리포트 — {run_ctx.run_id}\n")
    lines.append(f"- 실행 시각: {run_ctx.timestamp}")
    lines.append(f"- simulate: {simulate} (True면 픽스처 기반 = '완벽한 모델' 시뮬레이션)")
    lines.append(f"- 모델: {', '.join(models)}")
    lines.append(f"- 인증 타입: {', '.join(types)}  (wakeup 제외 — 세션/시간 기반이라 VLM 평가 대상 아님)")
    lines.append(f"- 총 샘플 수(행): {total}, 분류 대상: {len(classified)}\n")

    lines.append("## 모델별 요약 (전체 인증타입 합산)\n")
    lines.append("| model | accuracy | false_positive | avg_latency_ms | size_mb | android |")
    lines.append("|-------|----------|----------------|----------------|---------|---------|")
    for model in dict.fromkeys(r["model_name"] for r in rows):
        m = all_rollup.get(model)
        if not m:
            continue
        lines.append(f"| {model} | {m['accuracy']} | {m['fp']} | {m['avg_latency_ms']} | "
                     f"{_fmt(m['model_size_mb'])} | {_fmt(m['android_feasibility'])} |")
    lines.append("")

    lines.append("## False positive 사례\n")
    if not fp_rows:
        lines.append("- 없음 (모든 FAIL/BORDERLINE 이미지가 PASS로 잘못 판정되지 않음)\n")
    else:
        lines.append("| model | type | filename | expected | predicted |")
        lines.append("|-------|------|----------|----------|-----------|")
        for r in fp_rows:
            lines.append(f"| {r['model_name']} | {r['verification_type']} | {r['filename']} | "
                         f"{r['expected_label']} | {r['predicted_label']} |")
        lines.append("")

    lines.append("## 해석 메모\n")
    lines.append("- **인증 기능에서는 false positive(빈 컵/비운동/비학습을 PASS로 오인)가 가장 위험한 지표다.**")
    lines.append("  사용자가 실제로 하지 않은 활동을 '인증됨'으로 처리하면 습관 추적 신뢰가 무너지기 때문이다.")
    lines.append("- 따라서 후보 모델 선택 1순위는 **false_positive_rate 최소화**, 그 다음이 accuracy/recall,")
    lines.append("  그리고 Z Flip3 실행 가능성(model_size_mb / latency / android_feasibility)이다.")
    lines.append("- simulate=True 결과는 파이프라인 검증용이며, 실제 모델 정확도 비교는 --no-simulate + 실제 어댑터로 수행한다.")

    path = run_ctx.run_dir / "experiment_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# 실행 오케스트레이션
# ---------------------------------------------------------------------------

def _slug(parts: list[str]) -> str:
    return "-".join(parts) if parts else "none"


def run_experiment(models_only: list[str] | None, types: list[str], simulate: bool,
                   base_dir: Path | None = None, now: datetime | None = None) -> dict:
    for t in types:
        if t not in VERIFICATION_TYPES:
            raise ValueError(f"지원하지 않는 verification_type: {t} (wakeup은 VLM 평가 대상이 아님)")

    candidates = load_candidates(models_only)
    items = load_eval_items(types)
    fixture_lookup = {it["filename"]: it["fixture"] for it in items}.get
    model_meta = {c["model_name"]: c for c in candidates}

    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    models_slug = _slug([c.get("adapter", "m") for c in candidates])
    if len(models_slug) > 40:
        models_slug = f"{len(candidates)}models"
    run_id = f"{stamp}_{models_slug}_{_slug(types)}"

    base = base_dir or RUNS_DIR
    run_dir = base / run_id
    raw_dir = run_dir / "raw_outputs"
    normalized_dir = run_dir / "normalized_outputs"
    for d in (run_dir, raw_dir, normalized_dir):
        d.mkdir(parents=True, exist_ok=True)
    run_ctx = RunContext(run_id=run_id, timestamp=stamp, run_dir=run_dir,
                         raw_dir=raw_dir, normalized_dir=normalized_dir, write_outputs=True)

    rows: list[dict] = []
    for candidate in candidates:
        rows += evaluate_model(candidate, items, fixture_lookup, simulate, run_ctx=run_ctx)

    metrics = _finalize(rows, run_ctx, model_meta, [c["model_name"] for c in candidates], types, simulate)
    return {"run_id": run_id, "run_dir": run_dir, "rows": rows, "metrics": metrics}


def _finalize(rows: list[dict], run_ctx: RunContext, model_meta: dict[str, dict],
              model_names: list[str], types: list[str], simulate: bool) -> list[dict]:
    """rows → 지표 계산 + 모든 산출물 파일 저장. run_experiment 와 run_from_dump 가 공유."""
    metrics = compute_metrics(rows, model_meta)
    confusion = [{k: m[k] for k in CONFUSION_FIELDS}
                 for m in metrics if m["verification_type"] != "ALL"]
    latency = []
    classified = _classified(rows)
    for m in metrics:
        if m["verification_type"] == "ALL":
            continue
        vt_rows = [r for r in classified
                   if r["model_name"] == m["model_name"] and r["verification_type"] == m["verification_type"]]
        latency.append({"model_name": m["model_name"], "verification_type": m["verification_type"],
                        **_latency_stats(vt_rows)})

    run_dir = run_ctx.run_dir
    write_report(rows, run_dir / "per_image_report.csv")
    write_predictions_jsonl(rows, run_dir / "predictions.jsonl")
    _write_csv(metrics, METRICS_FIELDS, run_dir / "metrics_summary.csv")
    (run_dir / "metrics_summary.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(confusion, CONFUSION_FIELDS, run_dir / "confusion_matrix.csv")
    _write_csv(latency, LATENCY_FIELDS, run_dir / "latency_summary.csv")
    write_error_cases(rows, run_dir / "error_cases.csv")
    write_experiment_report(rows, metrics, run_ctx, model_names, types, simulate)
    return metrics


def run_from_dump(dump_path: str, base_dir: Path | None = None, now: datetime | None = None,
                  reparse: bool = False) -> dict:
    """stage 2: infer_dump.py 가 만든 JSONL(추론 결과)을 읽어 Rule Engine 판정 + 지표 저장.

    pydantic-v2 환경(base/qwen-vlm)에서 실행한다. 모델 로드/추론은 하지 않는다.
    reparse=True 면 저장된 raw_text 를 현재 파서(to_vision_analysis)로 다시 정규화한다
    (파서 개선을 재추론 없이 반영).
    """
    recs = [json.loads(x) for x in Path(dump_path).read_text(encoding="utf-8").splitlines() if x.strip()]
    if reparse:
        from adapters.smolvlm_adapter import to_vision_analysis
        for rec in recs:
            if not rec.get("error") and rec.get("raw_text"):
                rec["normalized"] = to_vision_analysis(
                    rec["raw_text"], rec["verification_type"],
                    {"verification_type": rec["verification_type"],
                     "exercise_activity_type": rec.get("exercise_activity_type")},
                )
    if not recs:
        raise ValueError(f"빈 dump: {dump_path}")

    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    adapters_slug = _slug(list(dict.fromkeys(r.get("adapter", "m") for r in recs)))
    types = list(dict.fromkeys(r["verification_type"] for r in recs))
    run_id = f"{stamp}_{adapters_slug}_{_slug(types)}_fromdump"
    base = base_dir or RUNS_DIR
    run_dir = base / run_id
    raw_dir = run_dir / "raw_outputs"
    normalized_dir = run_dir / "normalized_outputs"
    for d in (run_dir, raw_dir, normalized_dir):
        d.mkdir(parents=True, exist_ok=True)
    run_ctx = RunContext(run_id=run_id, timestamp=stamp, run_dir=run_dir,
                         raw_dir=raw_dir, normalized_dir=normalized_dir, write_outputs=True)

    model_meta: dict[str, dict] = {}
    rows: list[dict] = []
    for rec in recs:
        vt = rec["verification_type"]
        stem = Path(rec["filename"]).stem
        adapter_key = rec.get("adapter", "model")
        model_meta.setdefault(rec["model_name"], {
            "model_size_mb": rec.get("model_size_mb", ""),
            "runtime_target": rec.get("runtime_target", ""),
            "android_feasibility": rec.get("android_feasibility", ""),
        })
        row = {
            "run_id": run_id, "timestamp": stamp, "model_name": rec["model_name"],
            "model_path": rec.get("model_path", ""), "verification_type": vt,
            "filename": rec["filename"], "expected_label": rec.get("expected_label", ""),
            "model_load_time_ms": rec.get("model_load_time_ms", ""), "peak_gpu_memory_mb": "",
            "model_size_mb": rec.get("model_size_mb", ""), "runtime_target": rec.get("runtime_target", ""),
        }
        normalized = rec.get("normalized")
        if rec.get("error") or normalized is None:
            row.update({"predicted_label": "ERROR", "engine_result": rec.get("error") or "no_output",
                        "ok": False, "false_positive": False, "false_negative": False,
                        "latency_ms": rec.get("latency_ms", ""), "visual_evidence": "", "objects": "",
                        "raw_output_path": "", "normalized_output_path": "", "error": rec.get("error", "")})
            rows.append(row)
            continue

        raw_text = rec.get("raw_text") or (normalized.get("_raw_text", "") if isinstance(normalized, dict) else "")
        raw_path = ""
        if raw_text:
            rp = raw_dir / f"{adapter_key}__{stem}.txt"
            rp.write_text(str(raw_text), encoding="utf-8")
            raw_path = _rel(rp)
        np_ = normalized_dir / f"{adapter_key}__{stem}.json"
        np_.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

        analysis = VisionAnalysis.model_validate(normalized)
        ctx = (ImageVerificationContext(exercise_activity_type=rec.get("exercise_activity_type"))
               if vt == "exercise" else ImageVerificationContext())
        result = evaluate_image_verification(vt, analysis, ctx)
        predicted = ENGINE_TO_PREDICTED.get(result.result, "UNKNOWN")
        expected = rec.get("expected_label", "")
        ok = _label_ok(expected, predicted)
        row.update({
            "predicted_label": predicted, "engine_result": result.result,
            "score": result.score, "mandatory_passed": result.mandatory_passed, "ok": ok,
            "false_positive": predicted == "PASS" and expected != "PASS",
            "false_negative": predicted != "PASS" and expected == "PASS",
            "latency_ms": rec.get("latency_ms", ""),
            "visual_evidence": ";".join(getattr(analysis, EVIDENCE_FIELD[vt])),
            "objects": ";".join(o.label for o in analysis.objects),
            "raw_output_path": raw_path, "normalized_output_path": _rel(np_), "error": "",
        })
        rows.append(row)

    metrics = _finalize(rows, run_ctx, model_meta, list(model_meta.keys()), types, simulate=False)
    return {"run_id": run_id, "run_dir": run_dir, "rows": rows, "metrics": metrics}


def summarize(rows: list[dict]) -> None:
    by_model: dict[str, list[dict]] = {}
    for r in rows:
        if r["predicted_label"] in NON_CLASSIFIED:
            continue
        by_model.setdefault(r["model_name"], []).append(r)
    print("\n[SUMMARY]")
    for model, rs in by_model.items():
        ok = sum(1 for r in rs if r["ok"])
        fp = sum(1 for r in rs if r["false_positive"])
        print(f"  {model:<24} ok={ok}/{len(rs)}  false_positive={fp}")


def main() -> None:
    parser = argparse.ArgumentParser(description="On-device VLM candidate comparison (water/exercise/study).")
    parser.add_argument("--models", default=None, help="쉼표구분 adapter/model 이름 (기본: 전체 후보)")
    parser.add_argument("--verification-types", default=",".join(VERIFICATION_TYPES),
                        help="쉼표구분 (water,exercise,study). wakeup은 지원하지 않음")
    parser.add_argument("--simulate", dest="simulate", action="store_true", default=True,
                        help="실제 모델이 없으면 매니페스트 픽스처로 대체 (기본 on)")
    parser.add_argument("--no-simulate", dest="simulate", action="store_false",
                        help="시뮬레이션 끄기 (실제 어댑터만 사용, 없으면 SKIPPED)")
    parser.add_argument("--output-dir", default=None, help="run 폴더의 base 경로 (기본: outputs/runs)")
    parser.add_argument("--from-dump", default=None,
                        help="infer_dump.py 가 만든 JSONL 경로. 지정 시 모델 로드 없이 판정+지표만 계산(stage 2).")
    parser.add_argument("--reparse", action="store_true",
                        help="--from-dump 와 함께: 저장된 raw_text 를 현재 파서로 다시 정규화(재추론 없이 파서 개선 반영).")
    args = parser.parse_args()

    base_dir = Path(args.output_dir) if args.output_dir else None
    try:
        if args.from_dump:
            result = run_from_dump(args.from_dump, base_dir=base_dir, reparse=args.reparse)
        else:
            types = [t.strip() for t in args.verification_types.split(",") if t.strip()]
            only = [m.strip() for m in args.models.split(",")] if args.models else None
            result = run_experiment(only, types, args.simulate, base_dir=base_dir)
    except ValueError as exc:
        raise SystemExit(str(exc))

    print(f"[INFO] run_id={result['run_id']} items rows={len(result['rows'])}")
    print(f"[INFO] outputs → {_rel(result['run_dir'])}")
    summarize(result["rows"])


if __name__ == "__main__":
    main()
