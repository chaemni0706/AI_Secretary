"""Qwen2.5-VL-3B-AWQ smoke test.

목적: ondevice runner 에 붙이기 전, Qwen2.5-VL-3B-AWQ 가 qwen-vlm 환경에서 로드/추론되는지 확인.
- 모델 다운로드(로컬 /data/models/...) 여부 확인, 없으면 HF AWQ id 사용
- torch / transformers / qwen_vl_utils / autoawq 가용성 + cuda 출력
- 실제 어댑터(QwenAWQAdapter)로 로딩 → SmolVLM 과 동일한 프롬프트/파서 경로 검증
- input token 이후 생성분만 decode
- 이미지 1장 추론 latency + raw output + 정규화 evidence 출력
- 오류 시 traceback 과 원인 힌트 출력

주의: 이 스크립트는 3B(AWQ) 모델을 실제로 로딩/추론한다. VSCode 안에서 직접 실행하지 말고
      외부 터미널/tmux 에서 실행할 것(QWEN_AWQ_RUNBOOK.md 참고).

실행:
    conda activate qwen-vlm
    cd ~/AI_Secretary_FeatureJW_Qwen
    python local_eval/ondevice_vlm_eval/smoke_test_qwen_awq.py \
        --image local_eval/study_verification_fixture_pack/images/study_02.png \
        --verification-type study
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

LOCAL = "/data/models/Qwen2.5-VL-3B-Instruct-AWQ"
HF_ID = "Qwen/Qwen2.5-VL-3B-Instruct-AWQ"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image", default="local_eval/study_verification_fixture_pack/images/study_02.png")
    ap.add_argument("--verification-type", default="study", choices=["water", "exercise", "study"])
    ap.add_argument("--max-new-tokens", type=int, default=128)
    args = ap.parse_args()

    print("=== Qwen2.5-VL-3B-AWQ smoke test ===")

    # 1) 런타임/버전 진단
    try:
        import torch
        import transformers
        print(f"[deps] torch={torch.__version__} transformers={transformers.__version__} "
              f"cuda_available={torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"[deps] cuda_device={torch.cuda.get_device_name(0)}")
    except Exception as exc:  # noqa: BLE001
        print(f"[deps] torch/transformers MISSING: {type(exc).__name__}: {exc}")
        print("       torch/transformers 가 설치된 env(conda qwen-vlm)에서 실행하세요.")
        return
    # 주의: pip 패키지명은 'autoawq' 지만 실제 import module 은 'awq' 다.
    for mod, hint in [("qwen_vl_utils", "pip install qwen-vl-utils"),
                      ("awq", "pip install autoawq  # 패키지=autoawq, import module=awq")]:
        try:
            __import__(mod)
            print(f"[deps] import '{mod}' OK")
        except Exception as exc:  # noqa: BLE001
            print(f"[deps] import '{mod}' MISSING: {exc}  → {hint}")

    # 2) 모델 다운로드 여부
    local_exists = Path(LOCAL).exists()
    model_id = LOCAL if local_exists else HF_ID
    print(f"[model] local_path_exists={local_exists} → model_id={model_id}")
    if not local_exists:
        print(f"[model] (로컬 미탑재) HF 에서 다운로드됩니다: {HF_ID}")
        print("        미리 받으려면 QWEN_AWQ_RUNBOOK.md 의 다운로드 명령을 사용하세요.")

    # 3) 어댑터로 로딩 (runner 와 동일 경로)
    try:
        from adapters.qwen_awq_adapter import QwenAWQAdapter
        adapter = QwenAWQAdapter(meta={
            "model_name": "Qwen2.5-VL-3B-AWQ",
            "model_id": HF_ID, "model_path": LOCAL,
            "max_new_tokens": args.max_new_tokens,
        })
    except Exception:  # noqa: BLE001
        print("[load] FAILED (adapter 생성 예외):")
        traceback.print_exc()
        return

    print(f"[load] model_id(resolved)={adapter.model_id} available={adapter.available()} "
          f"load_time_ms={adapter.model_load_time_ms}")
    if not adapter.available():
        print(f"[load] load_error = {adapter._load_error}")
        print("\n[hint] 다음을 확인하세요:")
        print("  - autoawq 설치 여부 (AWQ 4bit 로딩): pip install autoawq")
        print("  - qwen_vl_utils 설치 여부: pip install qwen-vl-utils")
        print("  - transformers 가 Qwen2.5-VL 지원 버전인지 (>=4.49 권장)")
        print("  - GPU 메모리 여유 (3B AWQ ≈ 2.3GB)")
        return

    # 4) 이미지 1장 추론
    image_path = ROOT / args.image
    print(f"[infer] image={image_path} exists={image_path.exists()} vt={args.verification_type}")
    if not image_path.exists():
        print("[infer] 이미지가 없어 추론을 건너뜁니다.")
        return

    t0 = time.perf_counter()
    try:
        ctx = {"verification_type": args.verification_type, "exercise_activity_type": None}
        normalized = adapter.analyze(image_path, args.verification_type, ctx)
    except Exception:  # noqa: BLE001
        print("[infer] FAILED:")
        traceback.print_exc()
        return
    dt = (time.perf_counter() - t0) * 1000

    ev_field = {"water": "water_visual_evidence", "exercise": "exercise_visual_evidence",
                "study": "study_visual_evidence"}[args.verification_type]
    print(f"[infer] latency = {dt:.1f} ms")
    print(f"[infer] raw_output = {normalized.get('_raw_text')!r}")
    print(f"[infer] {ev_field} = {normalized.get(ev_field)}")
    print(f"[infer] objects = {[o['label'] for o in normalized.get('objects', [])]}")
    print("\n[note] 이 스크립트는 evidence 추출까지만 확인합니다. PASS/FAIL 판정은 Rule Engine 이 수행합니다.")


if __name__ == "__main__":
    main()
