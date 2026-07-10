"""SmolVLM2-2.2B-Instruct smoke test.

목적: ondevice runner 에 붙이기 전, SmolVLM2-2.2B 가 qwen-vlm 환경에서 로드/추론되는지 확인.
- 모델 다운로드(로컬 /data/models/...) 여부 확인, 없으면 HF id 사용
- torch / transformers / cuda 버전 출력
- 실제 어댑터(SmolVLM2Adapter)로 로딩 → 500M 과 동일한 프롬프트/파서/dtype 경로 검증
- single cuda device, input token 이후 생성분만 decode
- 이미지 1장 추론 latency + raw output + 정규화 evidence 출력
- 오류 시 traceback 과 원인 힌트 출력

주의: 이 스크립트는 2.2B 모델을 실제로 로딩/추론한다. VSCode 안에서 직접 실행하지 말고
      외부 터미널/tmux 에서 실행할 것(SMOLVLM2_RUNBOOK.md 참고).

실행:
    conda activate qwen-vlm
    cd ~/AI_Secretary_FeatureJW_Qwen
    python local_eval/ondevice_vlm_eval/smoke_test_smolvlm2.py \
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

LOCAL = "/data/models/SmolVLM2-2.2B-Instruct"
HF_ID = "HuggingFaceTB/SmolVLM2-2.2B-Instruct"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image", default="local_eval/study_verification_fixture_pack/images/study_02.png")
    ap.add_argument("--verification-type", default="study", choices=["water", "exercise", "study"])
    ap.add_argument("--max-new-tokens", type=int, default=128)
    args = ap.parse_args()

    print("=== SmolVLM2-2.2B-Instruct smoke test ===")

    # 1) 런타임/버전 진단
    try:
        import torch
        import transformers
        print(f"[deps] torch={torch.__version__} transformers={transformers.__version__} "
              f"cuda_available={torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"[deps] cuda_device={torch.cuda.get_device_name(0)}")
    except Exception as exc:  # noqa: BLE001
        print(f"[deps] MISSING: {type(exc).__name__}: {exc}")
        print("       torch/transformers 가 설치된 env(conda qwen-vlm)에서 실행하세요.")
        return

    # 2) 모델 다운로드 여부
    local_exists = Path(LOCAL).exists()
    model_id = LOCAL if local_exists else HF_ID
    print(f"[model] local_path_exists={local_exists} → model_id={model_id}")
    if not local_exists:
        print(f"[model] (로컬 미탑재) HF 에서 스트리밍/다운로드됩니다: {HF_ID}")
        print("        미리 받으려면 SMOLVLM2_RUNBOOK.md 의 다운로드 명령을 사용하세요.")

    # 3) 어댑터로 로딩 (runner 와 동일 경로)
    try:
        from adapters.smolvlm_adapter import SmolVLM2Adapter
        adapter = SmolVLM2Adapter(meta={
            "model_name": "SmolVLM2-2.2B-Instruct",
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
        print("  - num2words 설치 여부 (SmolVLM processor 필요): pip install num2words")
        print("  - transformers 가 SmolVLM2(Idefics3) 를 지원하는 버전인지 (>=4.50 권장)")
        print("  - GPU 메모리 여유 (2.2B bf16 ≈ 4.4GB)")
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
        print("\n[hint] pixel_values dtype 오류면 어댑터 _move_inputs 의 dtype 캐스팅을 확인하세요.")
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
