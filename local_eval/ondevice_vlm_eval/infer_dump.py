"""On-device VLM 추론 덤프 (stage 1) — pydantic 불필요 환경(mobilevlm 등)에서 실행.

MobileVLM 전용 env(transformers 4.33 → pydantic<2)는 backend 의 pydantic-v2 Rule Engine 을
못 돌린다. 그래서 추론(어댑터)만 이 스크립트로 수행해 이미지별 normalized VisionAnalysis dict +
raw_text + latency 를 JSONL 로 덤프하고, 판정/지표(stage 2)는 pydantic-v2 env 에서
`run_ondevice_eval.py --from-dump <jsonl>` 로 처리한다.

이 스크립트는 adapters 만 import 하며 backend/pydantic 을 import 하지 않는다.

실행(예):
    PYTHONPATH=/data/repos/MobileVLM \
    ~/anaconda3/envs/mobilevlm/bin/python local_eval/ondevice_vlm_eval/infer_dump.py \
        --models mobilevlm --verification-types study \
        --out local_eval/ondevice_vlm_eval/outputs/dumps/mobilevlm_study.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parents[1]
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import yaml  # noqa: E402

from adapters import ModelNotAvailable, build_adapter  # noqa: E402

CANDIDATES_YAML = THIS_DIR / "model_candidates.yaml"
WATER_MANIFEST = ROOT / "data" / "test_images" / "water" / "water_manifest.json"
EXERCISE_MANIFEST = ROOT / "data" / "test_images" / "exercise" / "exercise_manifest.json"
STUDY_PACK = ROOT / "local_eval" / "study_verification_fixture_pack"
STUDY_GT = STUDY_PACK / "study_ground_truth.jsonl"
STUDY_DECISION_TO_LABEL = {"verified": "PASS", "rejected": "FAIL", "retake_required": "BORDERLINE"}
VERIFICATION_TYPES = ("water", "exercise", "study")


def _load_candidates(only):
    data = yaml.safe_load(CANDIDATES_YAML.read_text(encoding="utf-8"))
    cands = data.get("candidates", [])
    if only:
        wanted = set(only)
        cands = [c for c in cands if c.get("adapter") in wanted or c.get("model_name") in wanted]
    return cands


def _json_items(manifest, vt):
    imgs = json.loads(Path(manifest).read_text(encoding="utf-8"))["images"]
    return [{"verification_type": vt, "filename": e["filename"], "image_path": str(ROOT / e["image_path"]),
             "expected_label": e["expected_label"], "exercise_activity_type": e.get("exercise_activity_type")}
            for e in imgs]


def _study_items():
    items = []
    for line in STUDY_GT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        gt = json.loads(line)
        iid = gt["image_id"]
        items.append({"verification_type": "study", "filename": f"{iid}.png",
                      "image_path": str(STUDY_PACK / gt.get("image_path", f"images/{iid}.png")),
                      "expected_label": STUDY_DECISION_TO_LABEL.get(gt.get("expected_decision"), "FAIL"),
                      "exercise_activity_type": None})
    return items


def load_eval_items(types):
    items = []
    if "water" in types:
        items += _json_items(WATER_MANIFEST, "water")
    if "exercise" in types:
        items += _json_items(EXERCISE_MANIFEST, "exercise")
    if "study" in types:
        items += _study_items()
    return items


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", default="mobilevlm")
    ap.add_argument("--verification-types", default="study")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    types = [t.strip() for t in args.verification_types.split(",") if t.strip()]
    for t in types:
        if t not in VERIFICATION_TYPES:
            raise SystemExit(f"지원하지 않는 verification_type: {t}")
    only = [m.strip() for m in args.models.split(",")]
    candidates = _load_candidates(only)
    items = load_eval_items(types)
    if args.limit:
        items = items[:args.limit]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out_path.open("w", encoding="utf-8") as f:
        for cand in candidates:
            adapter = build_adapter(cand["adapter"], meta=cand)
            load_ms = getattr(adapter, "model_load_time_ms", 0.0)
            print(f"[infer] model={cand['model_name']} available={adapter.available()} load_ms={load_ms}")
            for item in items:
                base = {
                    "model_name": cand["model_name"], "adapter": cand["adapter"],
                    "model_path": cand.get("model_path", ""), "model_size_mb": cand.get("model_size_mb", ""),
                    "runtime_target": cand.get("runtime_target", ""),
                    "android_feasibility": cand.get("android_feasibility", ""),
                    "filename": item["filename"], "verification_type": item["verification_type"],
                    "expected_label": item["expected_label"],
                    "exercise_activity_type": item.get("exercise_activity_type"),
                    "model_load_time_ms": load_ms,
                }
                t0 = time.perf_counter()
                try:
                    ctx = {"verification_type": item["verification_type"],
                           "exercise_activity_type": item.get("exercise_activity_type")}
                    normalized = adapter.analyze(Path(item["image_path"]), item["verification_type"], ctx)
                    base.update({
                        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
                        "raw_text": normalized.get("_raw_text", ""),
                        "normalized": normalized, "error": "",
                    })
                except ModelNotAvailable as exc:
                    base.update({"latency_ms": 0.0, "raw_text": "", "normalized": None,
                                 "error": f"model_not_available: {exc}"})
                except Exception as exc:  # noqa: BLE001
                    base.update({"latency_ms": round((time.perf_counter() - t0) * 1000, 3),
                                 "raw_text": "", "normalized": None, "error": f"infer_error: {exc}"})
                f.write(json.dumps(base, ensure_ascii=False) + "\n")
                n += 1
                print(f"  {item['filename']:14} raw={base.get('raw_text')!r} err={base['error']!r}")
    print(f"[done] wrote {n} records → {out_path}")


if __name__ == "__main__":
    main()
