"""MagicVL-2B smoke test (UNVERIFIED 후보).

주의: 'MagicVL-2B' 의 정확한 공식 HF id/추론 API/라이선스를 아직 확정하지 못했다.
이 스크립트는 먼저 존재/API 를 검증하는 용도이며, 검증 후 model_id 와 adapter._infer 를 조정한다.

실행:
    conda activate qwen-vlm && cd ~/AI_Secretary_FeatureJW_Qwen
    # 1) 정확한 id 를 알면 --model-id 로 지정
    python local_eval/ondevice_vlm_eval/smoke_test_magicvl.py --model-id <org>/MagicVL-2B \
        --image local_eval/study_verification_fixture_pack/images/study_02.png --verification-type study
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parents[1]
for p in (str(ROOT), str(THIS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model-id", default=None, help="검증된 정확한 HF model id (필수 권장)")
    ap.add_argument("--image", default="local_eval/study_verification_fixture_pack/images/study_02.png")
    ap.add_argument("--verification-type", default="study", choices=["water", "exercise", "study"])
    ap.add_argument("--max-new-tokens", type=int, default=128)
    args = ap.parse_args()

    print("=== MagicVL-2B smoke test (UNVERIFIED) ===")
    if not args.model_id:
        print("[warn] --model-id 를 지정하지 않았습니다. 먼저 HF 에서 정확한 id 를 확인하세요:")
        print("       python -c \"from huggingface_hub import list_models;")
        print("       print([m.id for m in list_models(search='MagicVL', limit=20)])\"")
    try:
        import torch, transformers  # noqa: F401
        print(f"[deps] torch={torch.__version__} transformers={transformers.__version__} cuda={torch.cuda.is_available()}")
    except Exception as exc:  # noqa: BLE001
        print(f"[deps] MISSING: {exc}")
        return

    try:
        from adapters.magicvl_adapter import MagicVLAdapter
        meta = {"model_name": "MagicVL-2B", "max_new_tokens": args.max_new_tokens}
        if args.model_id:
            meta["model_id"] = args.model_id
        adapter = MagicVLAdapter(meta=meta)
    except Exception:  # noqa: BLE001
        print("[load] FAILED (adapter 생성 예외):")
        traceback.print_exc()
        return

    print(f"[load] model_id={adapter.model_id} available={adapter.available()} load_time_ms={adapter.model_load_time_ms}")
    if not adapter.available():
        print(f"[load] load_error = {adapter._load_error}")
        print("[hint] 정확한 model id 확인, trust_remote_code 지원, .chat() API 여부 확인 후 어댑터 조정")
        return

    image_path = ROOT / args.image
    print(f"[infer] image={image_path} exists={image_path.exists()}")
    if not image_path.exists():
        return
    t0 = time.perf_counter()
    try:
        normalized = adapter.analyze(image_path, args.verification_type,
                                     {"verification_type": args.verification_type, "exercise_activity_type": None})
    except Exception:  # noqa: BLE001
        print("[infer] FAILED (API 불일치 가능 — _infer 조정 필요):")
        traceback.print_exc()
        return
    dt = (time.perf_counter() - t0) * 1000
    ev_field = f"{args.verification_type}_visual_evidence"
    print(f"[infer] latency={dt:.1f}ms raw={normalized.get('_raw_text')!r} {ev_field}={normalized.get(ev_field)}")


if __name__ == "__main__":
    main()
