"""MobileVLM V2 1.7B smoke test.

목적: 실제 모델 다운로드/추론 전, MobileVLM 어댑터의 연결 가능 여부를 빠르게 확인한다.
- 모델 경로 해석(로컬/HF)
- 런타임 의존성(torch / mtgv 'mobilevlm' 패키지) 확인
- 로드 가능하면 이미지 1장 추론 + latency 출력
- 불가하면 원인과 준비 방법을 명확히 안내(환경을 건드리지 않음)

실행(권장: MobileVLM 전용 환경):
    python local_eval/ondevice_vlm_eval/smoke_test_mobilevlm.py
    python local_eval/ondevice_vlm_eval/smoke_test_mobilevlm.py --image data/test_images/water/uploaded/water_test_08.png --verification-type water
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parents[1]
for p in (str(ROOT), str(THIS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from adapters.mobilevlm_adapter import MobileVLMAdapter  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image", default="data/test_images/water/uploaded/water_test_08.png")
    ap.add_argument("--verification-type", default="water", choices=["water", "exercise", "study"])
    args = ap.parse_args()

    print("=== MobileVLM V2 1.7B smoke test ===")
    # 1) 런타임 진단
    try:
        import torch  # noqa: F401
        print(f"[deps] torch OK, cuda={torch.cuda.is_available()}")
    except Exception as exc:  # noqa: BLE001
        print(f"[deps] torch MISSING: {exc}")
    try:
        from mobilevlm.model.mobilevlm import load_pretrained_model  # noqa: F401
        print("[deps] mobilevlm.model.mobilevlm.load_pretrained_model OK")
    except Exception as exc:  # noqa: BLE001
        print(f"[deps] mobilevlm.model.mobilevlm.load_pretrained_model MISSING: {exc}")
        print("       (PYTHONPATH=/data/repos/MobileVLM 확인, 또는 repo 미탑재)")

    # 2) 어댑터 로드 시도 (가중치 로드는 __init__ 에서 1회)
    adapter = MobileVLMAdapter(meta={"model_name": "MobileVLM-V2-1.7B"})
    print(f"[model] model_id/path = {adapter.model_id}")
    print(f"[model] local /data/models/MobileVLM_V2-1.7B exists = {Path('/data/models/MobileVLM_V2-1.7B').exists()}")
    print(f"[load] available = {adapter.available()} (load_time_ms={adapter.model_load_time_ms})")
    if not adapter.available():
        print(f"[load] load_error = {adapter._load_error}")
        print("\n[결론] 현재 환경에서는 실제 추론 불가. 준비 방법:")
        print("  1) repo: PYTHONPATH=/data/repos/MobileVLM (mobilevlm 패키지 import 경로)")
        print("  2) 가중치: mtgv/MobileVLM_V2-1.7B (HF) 또는 /data/models/MobileVLM_V2-1.7B (로컬)")
        print("     (CLIP vision tower openai/clip-vit-large-patch14-336 도 최초 로드 시 필요)")
        print("  3) 전용 env: torch 2.0.x / transformers 4.33.x (qwen-vlm 4.55 와 분리)")
        print("  준비 후 동일 명령으로 재실행하면 어댑터가 자동으로 실제 추론을 사용합니다.")
        return

    # 3) 이미지 1장 추론
    image = ROOT / args.image
    print(f"[infer] image = {image} (exists={image.exists()})")
    t0 = time.perf_counter()
    result = adapter.analyze(image, args.verification_type, {"verification_type": args.verification_type})
    dt = (time.perf_counter() - t0) * 1000
    print(f"[infer] latency = {dt:.1f} ms")
    print(f"[infer] raw_output = {result.get('_raw_text')!r}")
    ev_field = {"water": "water_visual_evidence", "exercise": "exercise_visual_evidence",
                "study": "study_visual_evidence"}[args.verification_type]
    print(f"[infer] {ev_field} = {result.get(ev_field)}")
    print(f"[infer] objects = {[o['label'] for o in result.get('objects', [])]}")


if __name__ == "__main__":
    main()
