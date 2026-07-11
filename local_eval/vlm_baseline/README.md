# local_eval/vlm_baseline

**기존 이미지 판독 엔진을 로컬 VLM(SmolVLM/Qwen-3B) evidence 로 대체하는 adapter** (기존 앱/Rule Engine 구조 유지).
임시 VLM baseline — 최종 제품 구조 아님, YOLO/액체-수위 신호 도입은 **후순위 보류**.
> **SmolVLM/Qwen-3B 는 최종 판정 모델이 아니다.** evidence extractor 이며, 최종 verified/rejected/retake_required 는 **기존 Rule Engine** 이 결정한다.

## end-to-end fallback 파이프라인 (2026-07-11 안정화)
`vlm_fallback_verifier.py` = **SmolVLM 로컬 우선 → server fallback VLM(Qwen2.5-VL-7B) → FP guard → fail-safe**.
최종 판정은 항상 **기존 Rule Engine**. 전체 감사/선정/결과는 루트 **`IMAGE_VERIFICATION_SYSTEM_AUDIT.md`**,
**`VLM_FALLBACK_STABILIZATION_REPORT.md`** 참조.

### fallback VLM 선정 (Gate C full-test 171, +guard)
| 후보 | FP | task_fp(w/s/e) | water recall | error/parse_fail | latency avg | 판정 |
|---|---|---|---|---|---|---|
| Qwen2.5-VL-3B (bf16, incumbent) | (mini15) | — | — | — | 11.4s | 탈락 |
| A.X-4.0-VL-Light + guard | 9 | 8/1/0 | 0.95 | 4/4 | 4.5s | 탈락 |
| **Qwen2.5-VL-7B + guard (채택)** | **6** | 6/0/0 | 0.85 | **0/0** | 6.6s | DO_NOT_CONFIRM(FP>0) |

→ **Qwen2.5-VL-7B 채택**(FP 6<9, study/exercise FP=0, 엔진오류·파싱 0). 잔여 FP=6 은 변기물/오염수/맥주+물/borderline
= **외관상 물과 구분 불가**(외관 기반 인증의 근본 실링).

### VLM-eligible visual scope 확정 (2026-07-11)
잔여 FP=6 전수 재분류(`fp_scope_review.csv`, visual_model_error=0) → **eligible subset(165) FP=0 → CONFIRM_ELIGIBLE_SCOPE**.
재계산: `recompute_metrics_with_scope.py` → `metrics_scope_adjusted.json`.

> Qwen2.5-VL-7B + guard is selected as the default server fallback model for VLM-based image verification.
> The model is confirmed only within the VLM-eligible visual scope. Water cases requiring non-visual context,
> such as contamination, toilet water, or visually indistinguishable alcohol, are excluded from VLM-only
> automatic confirmation and must be handled by secondary_review or context-based rules.

- **secondary_review 정책 + DB 운영 큐**: `verified(water)` → `review_required=true`, `review_status=pending`(비시각 맥락 리스크).
  DB 테이블 `image_verification_reviews` + API(pending 목록·상세·결정) → 루트 `SECONDARY_REVIEW_FLOW.md`. exercise/study 는 FP=0 자동 확정.
- **Smol 온디바이스**: ONNX q4f16 자산 + Dart/Kotlin 스텁 구현(`smol_android_runtime_stubbed`) → 루트 `SMOL_ONDEVICE_STATUS.md`.

### FP=0 hard guard (`vlm_fp_guard.py`)
Rule Engine core 미수정. Rule Engine 이 `verified` 를 내도 **A.X 의 `reason` 자유텍스트**를 스캔해
빈 잔("empty")·색깔 음료("yellowish/not water/green tea")·불투명·불확실이면 `retake_required` 로 강등.
(주의: A.X 의 positive/negative_evidence 필드는 vocabulary-dump 라 신뢰 불가 → **reason 중심 스캔**, negative_evidence 제외.)
water/exercise 에만 적용(study 는 mini_probe FP=0). `verified_from_error_or_parsefail=0` 보장(엔진 오류→verified 불가).

- 신규 파일: `vlm_fallback_verifier.py`, `smol_evidence_engine.py`, `smol_evidence_adapter.py`,
  `server_vlm_evidence_engine.py`, `server_vlm_model_registry.py`, `vlm_fp_guard.py`,
  `run_server_vlm_candidate_eval.py`, `run_vlm_fallback_full_eval.py`.

### 앱/backend 호출 진입점
```python
from local_eval.vlm_baseline.vlm_fallback_verifier import verify_image_with_vlm_fallback
out = verify_image_with_vlm_fallback(image_path, task)   # task ∈ {water,study,exercise}
# out["final_result"] ∈ {verified, rejected, retake_required}  ← 앱은 이것만 사용
# fallback 모델 교체: env VLM_FALLBACK_MODEL=<registry key>
```

## 파이프라인
```
image + task
  → qwen3b_evidence_engine.extract()   # Qwen evidence JSON (final result 없음)
  → qwen3b_evidence_adapter.to_existing_rule_input()  # → 기존 VisionAnalysis schema
  → 기존 evaluate_image_verification() (Rule Engine core, 미수정)  ← 최종 판정
  → final_result (verified/rejected/retake_required)
```

## 파일
- `qwen3b_evidence_engine.py` — Qwen evidence 추출(extract/run_qwen_evidence_extraction/parse_qwen_evidence). **transformers Qwen2.5-VL 실추론 구현**(Qwen2_5_VLForConditionalGeneration + AutoProcessor + qwen_vl_utils, **lazy singleton**: 최초 1회 로드 후 재사용). **weight 는 repo 에 없음**(config).
- `qwen3b_runtime_config.py` — env 기반 config: `QWEN3B_MODEL_PATH`, `QWEN3B_DEVICE`(cuda), `QWEN3B_DTYPE`(auto), `QWEN3B_MAX_NEW_TOKENS`(512), `QWEN3B_TEMPERATURE`(0.0), `QWEN3B_DO_SAMPLE`(false).
- `qwen3b_evidence_adapter.py` — Qwen evidence → 기존 Rule Engine 입력 매핑 + `run_existing_rule_engine()` + `verify()`.
- `qwen3b_unified_verifier.py` — [deprecated] adapter.verify 로 위임(직접 판정 없음).
- `prompts.py` — task별 evidence-extraction prompt. `sample_output_schema.json` — 최종 output 예시.

## 사용
```
export QWEN3B_MODEL_PATH=/data/models/Qwen2.5-VL-3B-Instruct   # non-AWQ bf16 권장(아래 주의). weight 는 repo 에 없음
# dry-run (모델 없이 mock evidence → 기존 Rule Engine → final_result 검증; 7/7)
python local_eval/vlm_baseline/qwen3b_evidence_engine.py --dry-run
# 단일 이미지 실모델 smoke (raw/parsed/final_result/rule_reason/fallback 출력)
python local_eval/vlm_baseline/qwen3b_evidence_engine.py --image <path> --task water --model-path <model>
# evidence JSON 만(Rule Engine 미호출)
python local_eval/vlm_baseline/qwen3b_evidence_engine.py --image <path> --task water --evidence-only
```
- dry-run: 7 케이스 모두 **final_result 를 기존 Rule Engine 에서** 산출(7/7, rule_engine_fallback=false).

## 원칙 / 안전
- Qwen weight/outputs/데이터셋 이미지 **git 미포함**. backend/Rule Engine core **미수정**(read-only import).
- 앱 사용: `final_result`. 앱 사용 금지: `qwen_raw_output`, `qwen_suggested_result`(debug).
- **FP=0 안전**: 모델 로드/generate/파싱 실패(engine_error/parse_failed)는 절대 verified 로 이어지지 않음 → uncertainty high → 기존 Rule Engine 이 **retake_required**. (Rule Engine import 실패 시 adapter 보수적 fallback=retake.)

## ⚠️ 런타임 주의 (AWQ)
- 로컬에 `Qwen2.5-VL-3B-Instruct-AWQ`(int4)만 있는 경우, 이 환경(torch 2.8 / Triton 3.4 / AutoAWQ 0.2.9)에서는 **AWQ GEMM Triton 커널 CompilationError** 로 generate 실패(모델 로드는 성공). → smoke 는 engine_error→**retake_required**(fail-safe)로 처리됨.
- 실추론 검증에는 **비-AWQ Qwen2.5-VL-3B(bf16)** 또는 **vLLM(awq_marlin)** 필요. 코드/파이프라인은 완성 상태(비-AWQ 모델이면 즉시 동작).

## 배경
- SmolVLM-500M 온디바이스 단독 인증 = FP=9 탈락(루트 `SMOLVLM_ONDEVICE_EVAL_FINAL_DECISION.md`).
- 상세: 루트 `VLM_TASK_ARCHIVE_SUMMARY.md`, `QWEN3B_UNIFIED_VERIFICATION_BASELINE.md`, `QWEN3B_TASK_PROMPTS.md`, `QWEN3B_FALLBACK_ARCHITECTURE_NOTE.md`.
