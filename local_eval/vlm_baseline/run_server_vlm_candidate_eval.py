"""Server Fallback VLM 후보 공정비교 runner (Gate B: mini probe).

각 후보 model_key 에 대해 동일 probe 이미지셋을 돌려 **server VLM evidence → 기존 Rule Engine → final_result**
를 산출하고, FP 중심 지표를 비교한다. fallback 후보 선택용(정확도만 높고 FP>0 이면 탈락).

여기서는 Smol 을 거치지 않고 **fallback engine 단독** 을 평가한다(FP 는 전부 fallback 경로에서 발생하므로
후보 비교의 올바른 격리). 최종 end-to-end(Smol local-first + 선택 fallback)는 vlm_fallback_verifier 로 별도 검증.

사용:
  python run_server_vlm_candidate_eval.py --models qwen25_3b,ax_4_0_vl_light --probe \
      --output-dir outputs/server_candidate_eval

지표(후보별): FP total / task_fp / verified_on_negative / recall / retake_required /
parse_failed / engine_error / latency(avg,p50,p95) / json_compliance / verified,rejected counts.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
_CAND = _ROOT / "local_eval" / "real_validation_dataset_150_candidate"
for p in (str(_ROOT), str(_HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import server_vlm_evidence_engine as sve      # noqa: E402
import server_vlm_model_registry as registry  # noqa: E402
from run_vlm_fallback_full_eval import _load_rows  # probe subset 재사용  # noqa: E402


def _pct(sorted_vals, p):
    if not sorted_vals:
        return 0
    return sorted_vals[min(len(sorted_vals) - 1, int(p / 100 * (len(sorted_vals) - 1)))]


def eval_model(model_key, rows, out_dir):
    spec = registry.get(model_key)
    preds, lat = [], []
    print(f"\n===== [{model_key}] {spec['display']} available={spec['available']} =====", flush=True)
    for i, r in enumerate(rows, 1):
        iid, task, gt = r["image_id"], r["task"], str(r["ground_truth"]).upper()
        img = _CAND / r["filepath"]
        rec = {"image_id": iid, "task": task, "ground_truth": gt}
        if not img.exists():
            rec.update({"final_result": "error", "parse_status": "failed", "engine_error": "missing_image",
                        "latency_ms": 0, "rule_reason": "", "mapped_codes": []})
            preds.append(rec); continue
        t0 = time.perf_counter()
        o = sve.verify(str(img), task, model_key)
        dt = round((time.perf_counter() - t0) * 1000, 1); lat.append(dt)
        dbg = o.get("debug", {})
        raw = dbg.get("raw_output", "")
        engine_error = raw[:120] if isinstance(raw, str) and raw.startswith("[engine_error]") else ""
        rec.update({"final_result": o["final_result"], "parse_status": dbg.get("parse_status", ""),
                    "engine_error": engine_error, "latency_ms": dt, "rule_reason": o.get("rule_reason", ""),
                    "mapped_codes": o["evidence"].get("mapped_rule_codes", []),
                    "uncertainty": o["evidence"].get("uncertainty", ""),
                    "rule_engine_result": o.get("rule_engine_result", ""),
                    "guard_reason": o.get("guard_reason", ""),
                    "raw_output": (raw[:500] if isinstance(raw, str) else ""),
                    "rule_engine_fallback": dbg.get("rule_engine_fallback", False)})
        preds.append(rec)
        fp = rec["final_result"] == "verified" and gt != "PASS"
        print(f"  [{i}/{len(rows)}] {iid:22} gt={gt:10} {rec['final_result']:14} "
              f"parse={rec['parse_status']:8} {dt:7.0f}ms {'FP!' if fp else ''}", flush=True)

    def conf(rs):
        tp = sum(1 for x in rs if x["ground_truth"] == "PASS" and x["final_result"] == "verified")
        fp = sum(1 for x in rs if x["ground_truth"] != "PASS" and x["final_result"] == "verified")
        tn = sum(1 for x in rs if x["ground_truth"] != "PASS" and x["final_result"] != "verified")
        fn = sum(1 for x in rs if x["ground_truth"] == "PASS" and x["final_result"] != "verified")
        n = len(rs); rc = tp / (tp + fn) if tp + fn else 0
        return dict(n=n, tp=tp, tn=tn, fp=fp, fn=fn, recall=round(rc, 3),
                    accuracy=round((tp + tn) / n, 3) if n else 0)

    metrics = {"ALL": conf(preds)}
    for t in ("water", "study", "exercise"):
        metrics[t] = conf([p for p in preds if p["task"] == t])
    fps = [p for p in preds if p["final_result"] == "verified" and p["ground_truth"] != "PASS"]
    n_parse_failed = sum(1 for p in preds if p["parse_status"] == "failed")
    n_engine_error = sum(1 for p in preds if p["engine_error"])
    lat_s = sorted(lat)
    verified_from_error = sum(1 for p in preds if p["final_result"] == "verified" and (p["engine_error"] or p["parse_status"] == "failed"))
    summary = {
        "model_key": model_key, "display": spec["display"], "available": spec["available"],
        "n_total": len(preds), "FP": len(fps),
        "task_fp": {t: metrics[t]["fp"] for t in ("water", "study", "exercise")},
        "verified_on_negative": len(fps), "metrics": metrics,
        "verified_count": sum(1 for p in preds if p["final_result"] == "verified"),
        "rejected_count": sum(1 for p in preds if p["final_result"] == "rejected"),
        "retake_required_count": sum(1 for p in preds if p["final_result"] == "retake_required"),
        "parse_failed_count": n_parse_failed, "engine_error_count": n_engine_error,
        "verified_from_error_or_parsefail": verified_from_error,   # 반드시 0 이어야 안전
        "json_compliance": round(1 - n_parse_failed / len(preds), 3) if preds else 0,
        "latency_avg_ms": round(sum(lat) / len(lat), 1) if lat else 0,
        "latency_p50_ms": _pct(lat_s, 50), "latency_p95_ms": _pct(lat_s, 95),
        "latency_max_ms": max(lat) if lat else 0,
        "fp_ids": [p["image_id"] for p in fps],
        "confirm_decision": ("CONFIRM_OK (FP=0)" if not fps else "DO_NOT_CONFIRM (FP>0)"),
    }
    md = out_dir / model_key
    md.mkdir(parents=True, exist_ok=True)
    (md / "predictions.jsonl").write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in preds) + "\n", encoding="utf-8")
    (md / "metrics.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with (md / "fp_review.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["image_id", "task", "gt", "final_result", "mapped_codes", "rule_reason", "parse_status"])
        for p in fps:
            w.writerow([p["image_id"], p["task"], p["ground_truth"], p["final_result"],
                        "|".join(p.get("mapped_codes", [])), p.get("rule_reason", ""), p.get("parse_status")])
    print(f"[{model_key}] FP={summary['FP']} task_fp={summary['task_fp']} recall={metrics['ALL']['recall']} "
          f"parse_failed={n_parse_failed} engine_error={n_engine_error} "
          f"verified_from_error={verified_from_error} lat_avg={summary['latency_avg_ms']}ms → {summary['confirm_decision']}", flush=True)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True, help="comma-separated registry keys")
    ap.add_argument("--manifest", default=str(_CAND / "final_manifest.csv"))
    ap.add_argument("--probe", action="store_true", help="48-image hard-case probe subset")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    rows = _load_rows(args.manifest, args.probe, args.limit)
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    keys = [k.strip() for k in args.models.split(",") if k.strip()]
    print(f"[candidate-eval] {len(rows)} images | models={keys} | probe={args.probe}")
    summaries = []
    for k in keys:
        summaries.append(eval_model(k, rows, out))

    # comparison table
    comp = {"n_images": len(rows), "probe": args.probe, "models": summaries}
    (out / "comparison.json").write_text(json.dumps(comp, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Server VLM Candidate Comparison (Gate B)", "",
             f"n={len(rows)} probe={args.probe}", "",
             "| model | FP | task_fp(w/s/e) | recall | retake | parse_fail | eng_err | v_from_err | json_ok | lat_avg | decision |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in summaries:
        tf = s["task_fp"]
        lines.append(f"| {s['model_key']} | **{s['FP']}** | {tf['water']}/{tf['study']}/{tf['exercise']} | "
                     f"{s['metrics']['ALL']['recall']} | {s['retake_required_count']} | {s['parse_failed_count']} | "
                     f"{s['engine_error_count']} | {s['verified_from_error_or_parsefail']} | {s['json_compliance']} | "
                     f"{s['latency_avg_ms']}ms | {s['confirm_decision']} |")
    lines += ["", "선택 기준: 1)FP=0 2)task_fp 모두 0 3)engine_error/parse_failed→verified=0 4)recall 5)latency."]
    (out / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
