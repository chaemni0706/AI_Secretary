# SmolVLM2-2.2B-Instruct 온디바이스 feasibility 판정 (GGUF / llama.cpp)

목적: SmolVLM-500M 다음 후보로 SmolVLM2-2.2B 가 Z Flip3 온디바이스 인증 후보로 의미 있는지,
full validation 전에 gate 로 판정. 기준: **FP=0 최우선, 온디바이스 실행성, feasible ≠ 인증가능.**
평가일 2026-07-08. 평가기: `local_eval/real_validation_dataset/evaluate_minicpm_v46_gguf.py`(GGUF VLM 공용, `--model-name`).

## 결론: **HOLD** (Gate 0~1 통과, Gate 3 FP-trap 실패 → full validation 보류)

| Gate | 내용 | 결과 |
| --- | --- | --- |
| 0 파일/경로 | `ggml-org/SmolVLM2-2.2B-Instruct-GGUF` 존재 | ✅ PASS |
| 1 PC smoke | 이미지 1장 crash 없이 evidence 출력 | ✅ PASS |
| 2 온디바이스 feasibility | 총 ~1.67GB (≤3GB) | ✅ PASS(단 SmolVLM-500M 대비 큼) |
| 3 FP-trap (real 부정 16장) | **FP=2 (exercise 환각)** | ❌ FAIL |
| 4 full validation(40장) | Gate3 실패로 **미실행(보류)** | ⏸ HOLD |

## Gate 0 — 파일/다운로드 (HF, 다운로드 전 크기)
repo `ggml-org/SmolVLM2-2.2B-Instruct-GGUF` (llama.cpp 공식 org):
- LLM: Q4_K_M **1.113GB** / Q8_0 1.928GB / f16 3.627GB
- mmproj(**필수**, multimodal projector): Q8_0 **0.593GB** / f16 0.872GB
- 실행 binary: `llama-mtmd-cli` (projector = idefics3). base(비GGUF) `HuggingFaceTB/SmolVLM2-2.2B-Instruct` = safetensors ~9GB.
- 채택 조합: Q4_K_M + mmproj-Q8_0 = **~1.67GB (다운로드 실측 1.1G + 566M)**.

## Gate 1 — PC smoke (crash-free, evidence-only)
```
llama-mtmd-cli -m SmolVLM2-2.2B-Instruct-Q4_K_M.gguf --mmproj mmproj-...-Q8_0.gguf \
  --image real_zflip/20260707_212538.jpg -p "Describe what is visible ..." -ngl 99 -n 64 --temp 0
```
- exit 0, crash 없음. projector=idefics3, CLIP on CUDA0.
- 출력: "A white paper cup sits on a wooden table next to a green bag and a book." (자연스러운 evidence 서술, PASS/FAIL 판단 없음, **중립 프롬프트에선 prompt echo 없음**)
- latency ~717ms/124tok (A5000 GPU 단발).

## Gate 2 — 온디바이스 feasibility 추정
- gguf(LLM) 1.11GB + mmproj 0.59GB = **~1.67GB**. 예상 상주 메모리 ~2~2.5GB.
- MiniCPM-V-4.6(1.2GB)보다 **크고**, SmolVLM-500M(600MB) 대비 **약 2.8배**.
- Z Flip3 CPU/Vulkan: llama.cpp idefics3 mtmd 지원 + Android(examples/llama.android) 경로 존재 → 실행 자체는 가능 추정(실기기 지연 재측정 필요).
- 앱 포함 크기: 1.67GB 는 무겁지만 불가능은 아님. 단 SmolVLM 대비 크기·속도 손해.

## Gate 3 — FP-trap (real 부정 16장: water FAIL7·exercise FAIL/BORDERLINE6·study FAIL3)
결과: `results/smolvlm2_2b_gguf_fptrap/`. **FP=2, 모두 exercise. water FP=0, study FP=0.**

| type | n | FP |
| --- | --- | --- |
| water | 7 | **0** (empty/beverage 정상 감지) |
| exercise | 6 | **2** |
| study | 3 | **0** (game→gaming_content 등 정상) |

**FP 원인 = 모델 환각(파서/echo 아님, 수정 불가):**
- `exercise_real_07`(office desk+laptop, FAIL): raw = "office desk with a laptop … as indicated by **the presence of a treadmill, dumbbells, a barbell, and a weight machine** … an exercise mat" → 사무실 이미지에 헬스 기구를 **환각**.
- `exercise_real_09`(FAIL): raw = "a person engaging in physical activity at **a gym** … a treadmill, dumbbells, a barbell, and a weight machine …" → 없는 gym 을 **환각**.
- (참고: 초기 FP=3 중 `exercise_real_11`("running shoes only … the **absence of** other items like dumbbells, barbells …")은 파서 negation cue 에 "absence of" 추가로 제거됨 → 파서 아티팩트였음. 나머지 2건은 부정문/echo 가 아닌 유창한 환각 서술이라 파서로 못 막음.)

## 보고 항목 답
1. GGUF 존재: ✅ `ggml-org/SmolVLM2-2.2B-Instruct-GGUF`
2. 모델 파일 크기: Q4_K_M 1.11GB (Q8_0 1.93 / f16 3.63)
3. mmproj 필요: ✅ 필수, Q8_0 0.59GB (f16 0.87)
4. llama.cpp 실행: ✅ `llama-mtmd-cli`, projector idefics3, crash 없음
5. PC smoke: ✅ 자연 evidence 출력, echo 없음, ~0.7s(GPU 단발)/~1.7s(배치 재로딩)
6. 온디바이스 feasibility: 조건부 가능(~1.67GB, SmolVLM 2.8배·MiniCPM보다 큼), Android llama.cpp 경로 있음
7. FP-trap: **FP=2 (exercise 환각)**, water/study 0
8. full validation: **미실행(HOLD)** — Gate3 FP≥1 규칙
9. SmolVLM-500M 대비 개선 가능성: **불명/제한적** — exercise 환각 FP 발생(안전성 위반), 크기·지연 손해.
   water/study 부정 셋은 깨끗하나 study 개선은 미검증. FP=0 전제 미충족.
10. **최종 판단: HOLD** (reject 아님, proceed 아님)

## HOLD 근거 및 재개 조건
- 규칙상 FP≥1 → full validation 보류. exercise 환각은 **모델 신뢰성 문제**로 파서로 해결 불가.
- 재개(proceed) 하려면 아래 중 하나로 **exercise FP=0 를 먼저 입증**해야 함:
  1. exercise 프롬프트에서 기구 나열 제거 + 환각 억제 프롬프트로 FP-trap 재통과, 또는
  2. 더 높은 정밀도(Q8_0/f16, 단 크기↑ ~2.5GB+)로 환각 감소 여부 확인.
- 그렇지 않으면 **SmolVLM-500M(온디바이스 1차) + Qwen2.5-VL-3B-AWQ(study/server fallback) 유지**가 우선.
