# local_eval/vlm_baseline

**기존 이미지 판독 엔진을 Qwen-3B 로 교체하는 adapter** (기존 앱/Rule Engine 구조 유지). 임시 VLM baseline — 최종 제품 구조 아님, **YOLO 전환 예정**.
> **Qwen-3B 는 최종 판정 모델이 아니다.** evidence extractor 이며, 최종 verified/rejected/retake_required 는 **기존 Rule Engine** 이 결정한다.

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
