"""SmolVLM-500M 최종 추론 러너 (final_manifest → predictions.jsonl + per_image.csv).

원칙: VLM 은 evidence 만 추출(smolvlm_adapter, 검증된 프롬프트/파서 재사용). 최종 판정은 Rule Engine
(evaluate_image_verification). 이 스크립트는 backend/adapter 를 read-only 로 import 하며 수정하지 않는다.

exercise activity: final_manifest 에 activity 컬럼이 없어, 모델 evidence 에서 activity 를 추정한다.
(FP 안전: activity 를 잘못 골라도 Rule Engine 은 최악의 경우 reject → 가짜 verify 불가. 실제 앱에선
사용자가 activity 를 선택한다.)

실행(qwen-vlm env):
  ~/anaconda3/envs/qwen-vlm/bin/python local_eval/real_validation_dataset/run_smolvlm_final_inference.py \
    --manifest local_eval/real_validation_dataset_150_candidate/final_manifest.csv \
    --run-name smolvlm500_final
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parents[1]
CAND_DIR = ROOT / "local_eval" / "real_validation_dataset_150_candidate"
ONDEVICE = ROOT / "local_eval" / "ondevice_vlm_eval"
import sys
for p in (str(ROOT), str(ONDEVICE)):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.database.schema.image_verification_schema import (  # noqa: E402
    ImageVerificationContext, VisionAnalysis,
)
from backend.services.image_verification_rule_engine import evaluate_image_verification  # noqa: E402

# exercise activity 추정용 evidence 그룹
_ACT = {
    "gym": {"gym_environment", "treadmill_present", "dumbbell_present", "barbell_present",
            "weight_machine_present", "exercise_bike_present", "gym_bench_present"},
    "running": {"running_environment", "running_track_present", "treadmill_running_environment",
                "stadium_track_present", "park_running_path_present"},
    "home_workout": {"home_workout_environment", "exercise_mat_present", "resistance_band_present",
                     "home_dumbbell_present", "kettlebell_present", "pull_up_bar_present",
                     "home_exercise_pose_visible"},
    "yoga": {"yoga_environment", "yoga_mat_present", "yoga_studio_present", "yoga_pose_visible"},
    "pilates": {"pilates_environment", "pilates_reformer_present", "pilates_equipment_present",
                "pilates_studio_present", "pilates_pose_visible"},
    "swimming": {"swimming_pool_environment", "swimming_lane_present", "lane_rope_present",
                 "swim_cap_present", "swim_goggles_present"},
}


def _derive_activity(evidence) -> str:
    ev = set(evidence or [])
    best, score = "gym", 0
    for act, s in _ACT.items():
        n = len(ev & s)
        if n > score:
            best, score = act, n
    return best  # 겹침 없으면 gym(FP 위험 없음: 근거 없으면 어차피 reject)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default=str(CAND_DIR / "final_manifest.csv"))
    ap.add_argument("--run-name", default="smolvlm500_final")
    ap.add_argument("--output-dir", default=str(THIS_DIR / "results"))
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    rows = list(csv.DictReader(Path(args.manifest).open(encoding="utf-8")))
    # 절대 필터(안전): include=Y 가정(final_manifest 는 이미 필터됨), gt 확정만
    rows = [r for r in rows if str(r.get("ground_truth", "")).upper() in ("PASS", "FAIL", "BORDERLINE")]
    if args.limit:
        rows = rows[: args.limit]

    from adapters.smolvlm_adapter import SmolVLMAdapter
    t0 = time.perf_counter()
    adapter = SmolVLMAdapter(meta={"model_name": "SmolVLM-500M", "max_new_tokens": 48})
    model_load_ms = round((time.perf_counter() - t0) * 1000, 1)
    print(f"[load] available={adapter.available()} load_ms={model_load_ms} err={adapter._load_error}")
    if not adapter.available():
        raise SystemExit(f"SmolVLM 로드 실패: {adapter._load_error}")

    out = Path(args.output_dir) / args.run_name
    out.mkdir(parents=True, exist_ok=True)
    preds = []
    for i, r in enumerate(rows, 1):
        img = CAND_DIR / r["filepath"]
        task = r["task"]
        gt = str(r["ground_truth"]).upper()
        rec = {"image_id": r["image_id"], "image": r["filepath"], "verification_type": task,
               "ground_truth": gt, "model_load_time": model_load_ms}
        if not img.exists():
            rec.update({"pred_result": "error", "error": "missing_image", "got_evidence": [],
                        "rule_evidence": [], "score": 0, "mandatory_passed": False})
            preds.append(rec); print(f"  [{i}/{len(rows)}] {r['image_id']:22} MISSING"); continue
        try:
            ti = time.perf_counter()
            normalized = adapter.analyze(img, task, {"verification_type": task})
            infer_ms = round((time.perf_counter() - ti) * 1000, 1)
            ev = list(normalized.get(f"{task}_visual_evidence", []) or [])
            act = _derive_activity(ev) if task == "exercise" else None
            va_payload = {k: v for k, v in normalized.items() if k != "_raw_text"}
            va = VisionAnalysis(**va_payload)
            tr = time.perf_counter()
            data = evaluate_image_verification(task, va, ImageVerificationContext(exercise_activity_type=act))
            rule_ms = round((time.perf_counter() - tr) * 1000, 2)
            rec.update({
                "pred_result": data.result,
                "got_evidence": ev,
                "rule_evidence": [e.code for e in data.rule_evidence],
                "score": data.score, "mandatory_passed": data.mandatory_passed,
                "exercise_activity_type_used": act,
                "raw_text": normalized.get("_raw_text", ""),
                "inference_time": infer_ms, "rule_engine_time": rule_ms,
                "parse_time": 0.0, "total_time": round(infer_ms + rule_ms, 1),
                "latency_ms": round(infer_ms + rule_ms, 1), "error": "",
            })
        except Exception as exc:  # noqa: BLE001
            rec.update({"pred_result": "error", "error": f"{type(exc).__name__}: {exc}",
                        "got_evidence": [], "rule_evidence": [], "score": 0, "mandatory_passed": False})
        preds.append(rec)
        flag = ""
        if rec.get("pred_result") == "verified" and gt != "PASS":
            flag = "FP!"
        elif rec.get("pred_result") != "verified" and gt == "PASS":
            flag = "FN"
        print(f"  [{i}/{len(rows)}] {r['image_id']:22} gt={gt:9} pred={rec.get('pred_result'):14} {flag}")

    (out / "predictions.jsonl").write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in preds) + "\n", encoding="utf-8")
    cols = ["image_id", "image", "verification_type", "ground_truth", "pred_result", "score",
            "mandatory_passed", "got_evidence", "rule_evidence", "exercise_activity_type_used",
            "inference_time", "rule_engine_time", "total_time", "error"]
    with (out / "per_image.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for p in preds:
            row = dict(p)
            for k in ("got_evidence", "rule_evidence"):
                row[k] = ";".join(map(str, row.get(k, []) or []))
            w.writerow({k: row.get(k, "") for k in cols})
    n_fp = sum(1 for p in preds if p.get("pred_result") == "verified" and p["ground_truth"] != "PASS")
    print(f"\n[done] {len(preds)} preds → {out}  (quick FP≈{n_fp}, model_load {model_load_ms}ms)")


if __name__ == "__main__":
    main()
