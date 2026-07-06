"""On-device VLM 후보 모델 비교 평가 러너.

동일한 water/exercise/study 테스트셋으로 여러 소형 VLM 후보(MiniCPM-V / MobileVLM /
SmolVLM / Qwen2.5-VL-AWQ)를 비교한다. wakeup은 VLM 대상이 아니므로 평가에서 제외한다.

    image → adapter.analyze() → VisionAnalysis dict → evaluate_image_verification(type, ...) → 판정

실제 모델은 아직 미탑재(stub). --simulate(기본) 모드에서는 각 이미지의 매니페스트 픽스처를
'모델 출력'으로 대체해 파이프라인/리포트 구조를 end-to-end로 검증한다. 실제 모델이 붙으면
--no-simulate로 어댑터의 실제 추론을 사용한다.

실행:
    python local_eval/ondevice_vlm_eval/run_ondevice_eval.py
    python local_eval/ondevice_vlm_eval/run_ondevice_eval.py --models mobilevlm,smolvlm
    python local_eval/ondevice_vlm_eval/run_ondevice_eval.py --verification-types water,study
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parents[1]  # ondevice_vlm_eval -> local_eval -> <repo root>
for p in (str(ROOT), str(THIS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import yaml  # noqa: E402

from adapters import ADAPTER_REGISTRY, ModelNotAvailable, build_adapter  # noqa: E402

from backend.database.schema.image_verification_schema import (  # noqa: E402
    ImageVerificationContext,
    VisionAnalysis,
)
from backend.services.image_verification_rule_engine import evaluate_image_verification  # noqa: E402

CANDIDATES_YAML = THIS_DIR / "model_candidates.yaml"
DEFAULT_OUTPUT = THIS_DIR / "outputs" / "ondevice_eval_report.csv"

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

CSV_FIELDS = [
    "model_name", "verification_type", "filename", "expected_label", "predicted_label",
    "engine_result", "ok", "false_positive", "latency_ms", "model_size_mb",
    "runtime_target", "visual_evidence", "objects",
]


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
    items = []
    for e in images:
        items.append({
            "verification_type": verification_type,
            "filename": e["filename"],
            "image_path": str(ROOT / e["image_path"]),
            "expected_label": e["expected_label"],
            "exercise_activity_type": e.get("exercise_activity_type"),
            "fixture": e["vision_analysis"],
        })
    return items


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


def _label_ok(expected: str, predicted: str) -> bool:
    if expected == "BORDERLINE":
        return predicted != "PASS"
    return (expected == "PASS") == (predicted == "PASS")


def evaluate_model(candidate: dict, items: list[dict], fixture_lookup, simulate: bool) -> list[dict]:
    adapter = build_adapter(candidate["adapter"], meta=candidate, fixture_lookup=fixture_lookup)
    rows = []
    for item in items:
        vt = item["verification_type"]
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
                rows.append(_row(candidate, item, predicted="SKIPPED", engine_result="model_not_available",
                                 ok=False, fp=False, latency_ms=0.0, evidence=[], objects=[], ))
                continue
            analysis_dict = fixture_lookup(item["filename"])  # 픽스처로 시뮬레이션
            error = "simulated_from_fixture"
        latency_ms = round((time.perf_counter() - t0) * 1000, 3)

        if analysis_dict is None:
            rows.append(_row(candidate, item, predicted="ERROR", engine_result="no_fixture",
                             ok=False, fp=False, latency_ms=latency_ms, evidence=[], objects=[]))
            continue

        analysis = VisionAnalysis.model_validate(analysis_dict)
        result = evaluate_image_verification(vt, analysis, _context(item))
        predicted = ENGINE_TO_PREDICTED.get(result.result, "UNKNOWN")
        expected = item["expected_label"]
        ok = _label_ok(expected, predicted)
        fp = predicted == "PASS" and expected != "PASS"
        evidence = getattr(analysis, EVIDENCE_FIELD[vt])
        objects = [o.label for o in analysis.objects]
        rows.append(_row(candidate, item, predicted=predicted, engine_result=result.result,
                         ok=ok, fp=fp, latency_ms=latency_ms, evidence=list(evidence), objects=objects))
    return rows


def _context_dict(item: dict) -> dict:
    return {"verification_type": item["verification_type"],
            "exercise_activity_type": item.get("exercise_activity_type")}


def _row(candidate, item, *, predicted, engine_result, ok, fp, latency_ms, evidence, objects) -> dict:
    return {
        "model_name": candidate["model_name"],
        "verification_type": item["verification_type"],
        "filename": item["filename"],
        "expected_label": item["expected_label"],
        "predicted_label": predicted,
        "engine_result": engine_result,
        "ok": ok,
        "false_positive": fp,
        "latency_ms": latency_ms,
        "model_size_mb": candidate.get("model_size_mb", ""),
        "runtime_target": candidate.get("runtime_target", ""),
        "visual_evidence": ";".join(evidence),
        "objects": ";".join(objects),
    }


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_report(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"[report] wrote {_rel(output)} ({len(rows)} rows)")


def summarize(rows: list[dict]) -> None:
    by_model: dict[str, list[dict]] = {}
    for r in rows:
        if r["predicted_label"] in {"SKIPPED", "ERROR"}:
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
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    types = [t.strip() for t in args.verification_types.split(",") if t.strip()]
    for t in types:
        if t not in VERIFICATION_TYPES:
            raise SystemExit(f"지원하지 않는 verification_type: {t} (wakeup은 VLM 평가 대상이 아님)")

    only = [m.strip() for m in args.models.split(",")] if args.models else None
    candidates = load_candidates(only)
    items = load_eval_items(types)
    fixture_map = {item["filename"]: item["fixture"] for item in items}
    fixture_lookup = fixture_map.get

    print(f"[INFO] models={[c['model_name'] for c in candidates]} types={types} "
          f"items={len(items)} simulate={args.simulate}")

    all_rows: list[dict] = []
    for candidate in candidates:
        rows = evaluate_model(candidate, items, fixture_lookup, args.simulate)
        all_rows += rows

    write_report(all_rows, Path(args.output))
    summarize(all_rows)


if __name__ == "__main__":
    main()
