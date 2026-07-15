# MiniCPM-V GGUF / llama.cpp 온디바이스 실행 가능성 판정

목적: MiniCPM-V 를 **최적화가 아니라 "Z Flip3 온디바이스로 운용 가능한지"** 빠르게 판정.
판정 기준: 실이미지 1장 crash 없이 output 생성 + 총 크기 ≤3GB(유지) / ≥4GB(탈락) + 공식 llama.cpp/GGUF 경로.

## 결론 (요약)

| 버전 | 총 크기(LLM+mmproj) | llama.cpp 실행 | 판정 |
| --- | --- | --- | --- |
| MiniCPM-V-2.0 GGUF (openbmb) | Q4_K_M 1.9GB + 0.83GB ≈ **2.7GB** | **vision(clip build_minicpmv) abort** (사용자 확인) | ❌ 탈락(runtime incompatibility) |
| MiniCPM-V-2.6 GGUF (openbmb, 8B) | 최소 Q2_K 3.0GB + 1.04GB ≈ **4.0GB**(Q4 ~5.5GB) | 미실행 | ❌ 탈락(size >4GB) |
| MiniCPM-V-4.5 GGUF (openbmb, 8.2B) | Q4_K_M 5.03GB + 1.1GB ≈ **6.1GB** | 미실행 | ❌ 탈락(size) |
| **MiniCPM-V-4.6 GGUF (ggml-org)** | Q4_K_M 0.51GB + mmproj-Q8_0 0.68GB ≈ **1.2GB** | **crash 없이 output 생성** | ✅ runtime PASS / ❌ **validation FAIL** |

**→ 최종: runtime feasibility 는 MiniCPM-V-4.6 만 PASS 였으나, real validation(40장)에서 FP=9 로 탈락.**
2.0/2.6/4.5 는 (runtime/size) 탈락, 4.6 은 (accuracy/FP) 탈락 → **MiniCPM-V 계열 전부 온디바이스 후보 제외.**

## Real validation 결과 (MiniCPM-V-4.6, 2026-07-08)

평가: `local_eval/real_validation_dataset/evaluate_minicpm_v46_gguf.py`, source=real 40장(synthetic/TODO 제외),
llama-mtmd-cli → 보수적 파서 → backend Rule Engine. 결과: `results/minicpm_v46_gguf/`.

| type | n | acc | precision | recall | F1 | **FP** | FN |
| --- | --- | --- | --- | --- | --- | --- | --- |
| water | 18 | 0.611 | 0.667 | 0.727 | 0.696 | **4** | 3 |
| exercise | 12 | 0.500 | 0.500 | 0.833 | 0.625 | **5** | 1 |
| study | 10 | 0.500 | 1.000 | 0.286 | 0.444 | **0** | 5 |
| **ALL** | 40 | 0.550 | 0.625 | 0.625 | 0.625 | **9** | 9 |

latency ≈ 3.5s/img (A5000 GPU, 이미지당 모델 재로딩 포함). parse_failures=0.

**탈락 사유 (FP=9, 최우선 기준 FP=0 위반):**
1. **water hallucination** — 빈 컵/용기를 "visible water … non-empty container with water inside"로 서술.
   `water_real_03/04/16/17`(FAIL/BORDERLINE)이 verified. **파서가 아니라 raw output 자체의 환각.**
2. **exercise prompt echo/parroting** — 프롬프트에 나열한 treadmill/dumbbell/barbell/weight machine 등을
   그대로 복창(예: raw = "Gym environment; treadmill; dumbbell; ...") → 강한 positive 로 추출 → office/unrelated 이미지가 verified.
3. **study 개선 없음** — FP=0 이지만 recall 0.286(SmolVLM 동일). 이는 이해가 아니라 부정어(entertainment 등)까지
   복창돼 Rule Engine 이 거절한 부작용. 실제 study 성능 개선 아님.

**판정: runtime feasibility PASS, 인증 후보 FAIL → 온디바이스 후보에서 제외.**

## PASS 상세 (MiniCPM-V-4.6)

- 사용한 repo: `ggml-org/MiniCPM-V-4.6-GGUF` (HuggingFace, **llama.cpp 공식 org** 호스팅 → on-device 경로 공식 확인)
- 모델 파일명: `MiniCPM-V-4.6-Q4_K_M.gguf` (505 MB)
- mmproj 파일명: `mmproj-MiniCPM-V-4.6-Q8_0.gguf` (695 MB)
- 총 크기: **1.2 GB** (≤3GB 통과)
- llama.cpp: `/home/piai/llama.cpp`, commit `2496f9c14965c39589f53eea31bdb6d762b1d360` (2026-05-06), CUDA 빌드, `llama-mtmd-cli`
  (별도 OpenBMB fork 불필요 — 현재 upstream llama.cpp mtmd 스택이 minicpmv4_6 projector 를 지원)
- 실행 명령:
  ```bash
  /home/piai/llama.cpp/build/bin/llama-mtmd-cli \
    -m /data/models/MiniCPM-V-4.6-GGUF/MiniCPM-V-4.6-Q4_K_M.gguf \
    --mmproj /data/models/MiniCPM-V-4.6-GGUF/mmproj-MiniCPM-V-4.6-Q8_0.gguf \
    --image <real_zflip>/20260707_212538.jpg \
    -p "Describe what is visible in this photo in one short sentence." \
    -ngl 99 -n 64 --temp 0
  ```
- 성공 여부: **성공 (exit 0, crash 없음)**
- 출력 결과:
  > "The image shows a white paper cup, a book, a notebook, and a bag on a wooden table."
- 핵심 로그(2.0에서 abort 하던 vision 단계가 정상):
  ```
  clip_model_loader: has vision encoder
  clip_ctx: CLIP using CUDA0 backend
  load_hparams: projector:  minicpmv4_6
  llama_perf_context_print: total time = 1917 ms / 694 tokens  (A5000, GPU)
  ```
  (clip_graph::build_minicpmv shape mismatch / abort **없음**.)

## 판정 근거
- ✅ 실이미지 1장 crash 없이 output 생성
- ✅ 총 크기 1.2GB ≤ 3GB
- ✅ 공식 GGUF + upstream llama.cpp mtmd(llama-mtmd-cli) 경로 확인, llama.cpp 에 Android 예제(examples/llama.android) 존재 → Android 배포 경로 존재
- ⇒ **온디바이스 후보 유지.**

## 남은 확인(별도 단계, feasibility 범위 밖)
- 정확도(water/exercise/study, FP=0)는 미측정 — feasibility(실행성)와 분리. 채택 확정 전 `run_ondevice_eval` 또는 llama.cpp 배치로 벤치 필요.
- Z Flip3 실기기 속도: 위 지연은 A5000(GPU) 기준. 실제 단말은 llama.cpp CPU/Vulkan(Adreno) 로 재측정 필요.
- "MiniCPM-V-4.6"(ggml-org)은 LLM n_embd=1024 로 소형(bf16 1.5GB급). 소형인 만큼 semantic 정확도는 별도 검증 대상.
