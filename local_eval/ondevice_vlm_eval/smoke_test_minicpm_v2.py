"""MiniCPM-V 2.0 (openbmb/MiniCPM-V-2, ~2.8B) smoke test.

목적: ondevice runner 에 붙이기 전, MiniCPM-V 2.0 이 qwen-vlm 환경에서 로드/추론되는지 확인.
- 다운로드(로컬 /data/models/MiniCPM-V-2) 여부, torch/transformers/cuda, trust_remote_code 로딩
- 실제 어댑터(MiniCPMV2Adapter)로 로딩 → SmolVLM 과 동일 프롬프트/파서 경로
- load time / latency / raw output / normalized evidence 출력, 오류 시 traceback

주의: 2.8B 로딩은 무겁다. VSCode 금지, tmux/외부 터미널에서 실행(MINICPM_V2_RUNBOOK.md).

실행:
    conda activate qwen-vlm && cd ~/AI_Secretary_FeatureJW_Qwen
    python local_eval/ondevice_vlm_eval/smoke_test_minicpm_v2.py \
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

LOCAL = "/data/models/MiniCPM-V-2"
HF_ID = "openbmb/MiniCPM-V-2"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image", default="local_eval/study_verification_fixture_pack/images/study_02.png")
    ap.add_argument("--verification-type", default="study", choices=["water", "exercise", "study"])
    ap.add_argument("--max-new-tokens", type=int, default=128)
    args = ap.parse_args()

    print("=== MiniCPM-V 2.0 smoke test ===")
    try:
        import torch
        import transformers
        print(f"[deps] torch={torch.__version__} transformers={transformers.__version__} "
              f"cuda={torch.cuda.is_available()}")
    except Exception as exc:  # noqa: BLE001
        print(f"[deps] MISSING: {type(exc).__name__}: {exc}")
        return

    local_exists = Path(LOCAL).exists()
    print(f"[model] local_path_exists={local_exists} → model_id={LOCAL if local_exists else HF_ID}")
    if not local_exists:
        print(f"[model] (로컬 미탑재) HF 다운로드: {HF_ID} (GGUF int4: openbmb/MiniCPM-V-2-gguf)")

    try:
        from adapters.minicpm_v_adapter import MiniCPMV2Adapter
        adapter = MiniCPMV2Adapter(meta={"model_name": "MiniCPM-V-2.0", "model_id": HF_ID,
                                         "model_path": LOCAL, "max_new_tokens": args.max_new_tokens})
    except Exception:  # noqa: BLE001
        print("[load] FAILED (adapter 생성 예외):")
        traceback.print_exc()
        return

    print(f"[load] model_id={adapter.model_id} available={adapter.available()} "
          f"load_time_ms={adapter.model_load_time_ms}")
    if not adapter.available():
        print(f"[load] load_error = {adapter._load_error}")
        print("[hint] trust_remote_code 지원 transformers, GPU 메모리(2.8B fp16≈5.5GB), "
              "chat() 시그니처가 2.0과 다르면 adapters/minicpm_v_adapter.py MiniCPMV2Adapter._infer 조정")
        return

    image_path = ROOT / args.image
    print(f"[infer] image={image_path} exists={image_path.exists()} vt={args.verification_type}")
    if not image_path.exists():
        return
    t0 = time.perf_counter()
    try:
        normalized = adapter.analyze(image_path, args.verification_type,
                                     {"verification_type": args.verification_type, "exercise_activity_type": None})
    except Exception:  # noqa: BLE001
        print("[infer] FAILED (2.0 chat API 불일치 가능 — _infer 조정 필요):")
        traceback.print_exc()
        return
    dt = (time.perf_counter() - t0) * 1000
    ev_field = f"{args.verification_type}_visual_evidence"
    print(f"[infer] latency = {dt:.1f} ms")
    print(f"[infer] raw_output = {normalized.get('_raw_text')!r}")
    print(f"[infer] {ev_field} = {normalized.get(ev_field)}")
    print(f"[infer] objects = {[o['label'] for o in normalized.get('objects', [])]}")
    print("\n[note] evidence 추출까지만 확인. PASS/FAIL 판정은 Rule Engine 이 수행합니다.")


if __name__ == "__main__":
    main()
