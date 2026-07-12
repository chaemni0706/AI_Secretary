"""Full-test runner for the Smol local-first + Qwen3B fallback + existing Rule Engine pipeline.

각 이미지: verify_image_with_vlm_fallback → final_result(기존 Rule Engine/fail-safe). FP=0 최우선.
outputs 는 git 미스테이징(요약 report.md/metrics.json 만 필요 시 별도). 모델 weight 미포함.
사용: --manifest <csv> [--probe] [--limit N] --output-dir <dir> [--borderline-as-fail]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
_RVD = _ROOT / "local_eval" / "real_validation_dataset"
_OND = _ROOT / "local_eval" / "ondevice_vlm_eval"
_CAND = _ROOT / "local_eval" / "real_validation_dataset_150_candidate"
for p in (str(_ROOT), str(_HERE), str(_RVD), str(_OND)):
    if p not in sys.path:
        sys.path.insert(0, p)

import vlm_fallback_verifier as vfb  # noqa: E402


def _load_rows(manifest, probe, limit):
    """self-contained: manifest(csv/json) → PASS/FAIL/BORDERLINE rows. probe=48(FP9 taxonomy + task 대비쌍)."""
    mp = Path(manifest)
    if mp.suffix == ".csv":
        rows = list(csv.DictReader(mp.open(encoding="utf-8-sig")))
    else:
        obj = json.loads(mp.read_text(encoding="utf-8"))
        rows = obj if isinstance(obj, list) else obj.get("images", [])
    rows = [r for r in rows if str(r.get("ground_truth", "")).upper() in ("PASS", "FAIL", "BORDERLINE")]
    if probe:
        by_id = {r["image_id"]: r for r in rows}
        probe_rows, seen = [], set()
        tax = _OND / "SMOLVLM_FP_FAILURE_TAXONOMY.csv"
        if tax.exists():
            for t in csv.DictReader(tax.open(encoding="utf-8-sig")):
                m = by_id.get(t.get("image_id"))
                if m and m["image_id"] not in seen:
                    probe_rows.append(m); seen.add(m["image_id"])
        from collections import defaultdict
        buckets = defaultdict(list)
        for r in rows:
            buckets[(r["task"], str(r["ground_truth"]).upper())].append(r)
        for task in ("water", "exercise", "study"):
            for gt in ("PASS", "FAIL", "BORDERLINE"):
                for r in buckets.get((task, gt), [])[:5]:
                    if r["image_id"] not in seen:
                        probe_rows.append(r); seen.add(r["image_id"])
        rows = probe_rows
    if limit:
        rows = rows[:limit]
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(_CAND / "final_manifest.csv"))
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--probe", action="store_true", help="48-image hard-case probe subset")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--borderline-as-fail", action="store_true", default=True)
    ap.add_argument("--no-qwen", action="store_true")
    args = ap.parse_args()

    rows = _load_rows(args.manifest, args.probe, args.limit)
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    preds, lat = [], []
    from collections import Counter
    print(f"[run] {len(rows)} images | probe={args.probe} | no_qwen={args.no_qwen}")
    for i, r in enumerate(rows, 1):
        iid, task, gt = r["image_id"], r["task"], str(r["ground_truth"]).upper()
        img = _CAND / r["filepath"]
        rec = {"image_id": iid, "task": task, "ground_truth": gt}
        if not img.exists():
            rec.update({"final_result": "error", "engine_used": "fail_safe", "error": "missing_image"})
            preds.append(rec); continue
        t0 = time.perf_counter()
        try:
            o = vfb.verify_image_with_vlm_fallback(str(img), task, image_id=iid, no_qwen=args.no_qwen)
        except Exception as exc:  # noqa: BLE001
            o = {"final_result": "retake_required", "engine_used": "fail_safe", "fallback_used": False,
                 "local_result": "error", "fallback_result": None, "rule_reason": f"orchestrator_error: {exc}",
                 "rule_trace": [], "evidence": {}, "debug": {}}
        dt = round((time.perf_counter() - t0) * 1000, 1); lat.append(dt)
        rec.update({"final_result": o["final_result"], "engine_used": o["engine_used"],
                    "fallback_used": o["fallback_used"], "local_result": o.get("local_result"),
                    "fallback_result": o.get("fallback_result"), "rule_reason": o.get("rule_reason", ""),
                    "rule_trace": o.get("rule_trace", []),
                    "local_parse_status": o.get("debug", {}).get("local_parse_status", ""),
                    "fallback_parse_status": o.get("debug", {}).get("fallback_parse_status", ""),
                    "local_error": o.get("debug", {}).get("local_error", ""),
                    "fallback_error": o.get("debug", {}).get("fallback_error", ""), "latency_ms": dt})
        preds.append(rec)
        fp = rec["final_result"] == "verified" and gt != "PASS"
        print(f"  [{i}/{len(rows)}] {iid:20} gt={gt:10} {rec['final_result']:14} engine={rec['engine_used']:16} {'FP!' if fp else ''}")

    def conf(rs):
        tp = sum(1 for x in rs if x["ground_truth"] == "PASS" and x["final_result"] == "verified")
        fpp = sum(1 for x in rs if x["ground_truth"] != "PASS" and x["final_result"] == "verified")
        tn = sum(1 for x in rs if x["ground_truth"] != "PASS" and x["final_result"] != "verified")
        fn = sum(1 for x in rs if x["ground_truth"] == "PASS" and x["final_result"] != "verified")
        n = len(rs); rec_ = tp / (tp + fn) if tp + fn else 0
        return dict(n=n, tp=tp, tn=tn, fp=fpp, fn=fn, recall=round(rec_, 3),
                    accuracy=round((tp + tn) / n, 3) if n else 0)
    metrics = {"ALL": conf(preds)}
    for t in ("water", "study", "exercise"):
        metrics[t] = conf([p for p in preds if p["task"] == t])
    fps = [p for p in preds if p["final_result"] == "verified" and p["ground_truth"] != "PASS"]
    fns = [p for p in preds if p["ground_truth"] == "PASS" and p["final_result"] != "verified"]
    errs = [p for p in preds if p["final_result"] == "error" or p.get("local_error") or p.get("fallback_error") == "fallback_engine_error"]
    lat_s = sorted(lat)
    def pct(p): return lat_s[min(len(lat_s) - 1, int(p / 100 * (len(lat_s) - 1)))] if lat_s else 0
    summary = {
        "n_total": len(preds), "by_task": dict(Counter(p["task"] for p in preds)),
        "by_gt": dict(Counter(p["ground_truth"] for p in preds)),
        "FP": len(fps), "task_fp": {t: metrics[t]["fp"] for t in ("water", "study", "exercise")},
        "verified_on_negative": len(fps), "metrics": metrics,
        "retake_required_count": sum(1 for p in preds if p["final_result"] == "retake_required"),
        "rejected_count": sum(1 for p in preds if p["final_result"] == "rejected"),
        "verified_count": sum(1 for p in preds if p["final_result"] == "verified"),
        "fallback_used_count": sum(1 for p in preds if p.get("fallback_used")),
        "smol_accept_count": sum(1 for p in preds if p["engine_used"] == "smol"),
        "server_fallback_count": sum(1 for p in preds if p["engine_used"] == "server_fallback"),
        "server_fallback_success_count": sum(1 for p in preds if p["engine_used"] == "server_fallback"),
        "fail_safe_count": sum(1 for p in preds if p["engine_used"] == "fail_safe"),
        "error_count": len(errs),
        "parse_failed_count": sum(1 for p in preds if p.get("local_parse_status") == "failed" or p.get("fallback_parse_status") == "failed"),
        "latency_avg_ms": round(sum(lat) / len(lat), 1) if lat else 0,
        "latency_p50_ms": pct(50), "latency_p95_ms": pct(95), "latency_max_ms": max(lat) if lat else 0,
        "confirm_decision": ("CONFIRM_OK (FP=0)" if not fps else "DO_NOT_CONFIRM (FP>0)"),
    }
    (out / "predictions.jsonl").write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in preds) + "\n", encoding="utf-8")
    with (out / "per_image.csv").open("w", newline="", encoding="utf-8") as f:
        cols = ["image_id", "task", "ground_truth", "final_result", "engine_used", "fallback_used",
                "local_result", "fallback_result", "local_parse_status", "fallback_parse_status",
                "local_error", "fallback_error", "latency_ms", "rule_reason"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for p in preds:
            w.writerow(p)
    (out / "metrics.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "metrics_by_task.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["task", "n", "tp", "tn", "fp", "fn", "recall", "accuracy"])
        for t in ("ALL", "water", "study", "exercise"):
            m = metrics[t]; w.writerow([t, m["n"], m["tp"], m["tn"], m["fp"], m["fn"], m["recall"], m["accuracy"]])
    for name, data in (("fp_review.csv", fps), ("fn_review.csv", fns), ("error_review.csv", errs)):
        with (out / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["image_id", "task", "gt", "final_result", "engine_used", "fallback_used", "rule_reason", "local_error", "fallback_error"])
            for p in data:
                w.writerow([p["image_id"], p["task"], p["ground_truth"], p["final_result"], p.get("engine_used"),
                            p.get("fallback_used"), p.get("rule_reason", ""), p.get("local_error", ""), p.get("fallback_error", "")])
    (out / "report.md").write_text(
        f"# VLM Fallback Full-Test Report\n\nn={summary['n_total']} by_gt={summary['by_gt']}\n\n"
        f"**FP={summary['FP']}** task_fp={summary['task_fp']} → **{summary['confirm_decision']}**\n\n"
        f"metrics ALL={metrics['ALL']}\nwater={metrics['water']}\nstudy={metrics['study']}\nexercise={metrics['exercise']}\n\n"
        f"verified={summary['verified_count']} rejected={summary['rejected_count']} retake={summary['retake_required_count']}\n"
        f"fallback_used={summary['fallback_used_count']} smol_accept={summary['smol_accept_count']} server_fallback={summary['server_fallback_count']} fail_safe={summary['fail_safe_count']}\n"
        f"error={summary['error_count']} parse_failed={summary['parse_failed_count']}\n"
        f"latency avg={summary['latency_avg_ms']}ms p50={summary['latency_p50_ms']} p95={summary['latency_p95_ms']} max={summary['latency_max_ms']}\n\n"
        f"확정 기준: FP==0 이면 인증 시스템 확정 가능. FP>0 이면 fp_review.csv 보고 보수 정책 수정.\n", encoding="utf-8")
    print(f"\nFULL_EVAL_SUMMARY n={summary['n_total']} FP={summary['FP']} task_fp={summary['task_fp']} "
          f"verified={summary['verified_count']} fallback_used={summary['fallback_used_count']} "
          f"fail_safe={summary['fail_safe_count']} error={summary['error_count']} → {summary['confirm_decision']}")
    print(f"  metrics ALL={metrics['ALL']}")
    print(f"  FP ids: {[p['image_id'] for p in fps]}")


if __name__ == "__main__":
    main()
