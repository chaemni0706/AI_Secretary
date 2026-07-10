"""real_validation_dataset 배치 평가기.

기존 Local VLM pipeline(LocalVLMVisionAnalyzer → VisionAnalysis → Rule Engine)을 재사용해
검증셋 전체를 평가하고, PASS(=verified) 기준 confusion/지표와 실패 케이스를 저장한다.

모델은 PASS/FAIL 을 결정하지 않는다(시각 evidence 만). 최종 판정은 항상 Rule Engine.
FP(부정 케이스인데 verified) 최소화가 최우선 관점.

두 가지 모드:
  --simulate : manifest 의 reference_vision_analysis 로 Rule Engine 만 실행(모델 불필요, 즉시 실행 가능).
               데이터셋/Rule Engine 정합성 확인용.
  (기본)     : 실제 Local VLM pipeline(verify_image_upload) 실행. torch/모델 있는 env(qwen-vlm)에서,
               가급적 외부 터미널/tmux 에서 실행(대형 모델 로딩).

결과는 real_validation_dataset/results/<mode>/ 아래에 저장(기존 local_eval metrics 구조는 건드리지 않음).

실행:
  # 즉시(모델 없이) 데이터셋 정합성 확인
  python local_eval/real_validation_dataset/evaluate_validation_dataset.py --simulate

  # 실제 로컬 VLM 평가 (외부 터미널, qwen-vlm env)
  IMAGE_VERIFICATION_VLM_PROVIDER=smolvlm IMAGE_VERIFICATION_STUDY_FALLBACK=qwen_awq \
    python local_eval/real_validation_dataset/evaluate_validation_dataset.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MANIFEST = THIS_DIR / "annotations" / "validation_manifest.json"
IMAGES_DIR = THIS_DIR / "images"

_RESULT_TO_LABEL = {"verified": "PASS", "rejected": "FAIL", "retake_required": "BORDERLINE"}
_CONTENT_TYPE = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def _load_manifest() -> list[dict]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return data.get("images", [])


def _predict_simulate(item: dict):
    """reference_vision_analysis → Rule Engine (모델 없이)."""
    from backend.database.schema.image_verification_schema import (
        ImageVerificationContext,
        VisionAnalysis,
    )
    from backend.services.image_verification_rule_engine import evaluate_image_verification

    va = VisionAnalysis(**item.get("reference_vision_analysis", {}))
    ctx = ImageVerificationContext(exercise_activity_type=item.get("exercise_activity_type"))
    return evaluate_image_verification(item["verification_type"], va, ctx)


def _predict_real(item: dict):
    """실제 Local VLM pipeline(verify_image_upload) — env provider + study fallback 포함."""
    from backend.services.image_verification_service import verify_image_upload

    img = IMAGES_DIR / item["image"]
    ctype = _CONTENT_TYPE.get(img.suffix.lower(), "image/png")
    with img.open("rb") as f:
        return verify_image_upload(
            f, filename=img.name, content_type=ctype,
            verification_type=item["verification_type"],
            exercise_activity_type=item.get("exercise_activity_type"),
        )


def _metrics(rows: list[dict]) -> dict:
    """PASS(=verified)=positive 기준 confusion + 지표. 타입별 + 전체."""
    def confusion(subset):
        tp = fp = tn = fn = 0
        for r in subset:
            gt_pass = r["ground_truth"] == "PASS"
            pred_pass = r["pred_result"] == "verified"
            if gt_pass and pred_pass:
                tp += 1
            elif not gt_pass and pred_pass:
                fp += 1
            elif not gt_pass and not pred_pass:
                tn += 1
            else:
                fn += 1
        n = len(subset)
        acc = (tp + tn) / n if n else 0.0
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        return {"n": n, "tp": tp, "tn": tn, "fp": fp, "fn": fn,
                "accuracy": round(acc, 3), "precision": round(prec, 3),
                "recall": round(rec, 3), "false_positive_rate": round(fpr, 3)}

    out = {"ALL": confusion(rows)}
    for vt in ("water", "exercise", "study"):
        sub = [r for r in rows if r["verification_type"] == vt]
        if sub:
            out[vt] = confusion(sub)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--simulate", action="store_true",
                    help="모델 없이 reference_vision_analysis 로 Rule Engine 만 실행")
    ap.add_argument("--types", default="water,exercise,study")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    types = {t.strip() for t in args.types.split(",") if t.strip()}
    items = [i for i in _load_manifest() if i["verification_type"] in types]
    if args.simulate:
        # simulate 는 reference_vision_analysis 로 Rule Engine 만 확인한다.
        # 참조 분석이 없는 실촬영 엔트리(real_zflip 등)는 실제 VLM 모드 전용이므로 제외.
        skipped_ref = [i for i in items if not i.get("reference_vision_analysis")]
        if skipped_ref:
            print(f"[simulate] reference_vision_analysis 없는 {len(skipped_ref)}개 제외 "
                  f"(실제 VLM 모드에서 평가하세요)")
        items = [i for i in items if i.get("reference_vision_analysis")]
    if args.limit:
        items = items[: args.limit]

    mode = "simulate" if args.simulate else "local_vlm"
    predict = _predict_simulate if args.simulate else _predict_real

    rows = []
    for item in items:
        rec = {
            "image": item["image"], "verification_type": item["verification_type"],
            "ground_truth": item["ground_truth"],
            "expected_evidence": item.get("expected_evidence", []),
            "source": item.get("source", ""),
        }
        try:
            data = predict(item)
            rec["pred_result"] = data.result
            rec["pred_label"] = _RESULT_TO_LABEL.get(data.result, data.result)
            rec["score"] = data.score
            rec["mandatory_passed"] = data.mandatory_passed
            rec["rule_evidence"] = [ev.code for ev in data.rule_evidence]
            va = data.vlm_analysis
            rec["got_evidence"] = list(
                getattr(va, f"{item['verification_type']}_visual_evidence", []) or []
            )
            rec["quality_usable"] = va.quality.usable
            rec["error"] = ""
        except Exception as exc:  # noqa: BLE001
            rec.update({"pred_result": "error", "pred_label": "ERROR", "score": 0,
                        "mandatory_passed": False, "rule_evidence": [], "got_evidence": [],
                        "quality_usable": False, "error": f"{type(exc).__name__}: {exc}"})
        # FP/FN 플래그 (PASS=positive)
        gt_pass = rec["ground_truth"] == "PASS"
        pred_pass = rec["pred_result"] == "verified"
        rec["is_false_positive"] = (not gt_pass) and pred_pass
        rec["is_false_negative"] = gt_pass and (not pred_pass)
        rec["correct"] = gt_pass == pred_pass
        rows.append(rec)
        flag = "FP!" if rec["is_false_positive"] else ("FN" if rec["is_false_negative"] else ("ok" if rec["correct"] else ""))
        print(f"  {rec['image']:38} gt={rec['ground_truth']:9} pred={rec['pred_label']:9} {flag} {rec['error']}")

    metrics = _metrics(rows)
    failures = [r for r in rows if not r["correct"] or r["error"]]
    false_positives = [r for r in rows if r["is_false_positive"]]

    out_dir = THIS_DIR / "results" / mode
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics_summary.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "failure_cases.json").write_text(
        json.dumps({"false_positives": false_positives, "all_failures": failures},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["image", "verification_type", "ground_truth", "pred_label", "pred_result",
              "score", "mandatory_passed", "quality_usable", "is_false_positive",
              "is_false_negative", "correct", "expected_evidence", "got_evidence",
              "rule_evidence", "source", "error"]
    with (out_dir / "per_image.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            row = dict(r)
            for k in ("expected_evidence", "got_evidence", "rule_evidence"):
                row[k] = ";".join(map(str, row.get(k, [])))
            w.writerow({k: row.get(k, "") for k in fields})

    print(f"\n[mode={mode}] {len(rows)} images")
    for vt in ("ALL", "water", "exercise", "study"):
        if vt in metrics:
            m = metrics[vt]
            print(f"  {vt:9} acc={m['accuracy']:.3f} FP={m['fp']} FN={m['fn']} "
                  f"recall={m['recall']:.3f} FPR={m['false_positive_rate']:.3f} (n={m['n']})")
    print(f"  false_positives={len(false_positives)}  failures={len(failures)}")
    print(f"[out] {out_dir}")


if __name__ == "__main__":
    main()
