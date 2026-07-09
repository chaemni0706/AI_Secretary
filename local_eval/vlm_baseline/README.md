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
- `qwen3b_evidence_engine.py` — Qwen evidence 추출(extract/run_qwen_evidence_extraction/parse_qwen_evidence). 모델 로드/generate 는 skeleton(런타임). **weight 는 repo 에 없음**(env `QWEN3B_MODEL_PATH`).
- `qwen3b_evidence_adapter.py` — Qwen evidence → 기존 Rule Engine 입력 매핑 + `run_existing_rule_engine()` + `verify()`.
- `qwen3b_unified_verifier.py` — [deprecated] adapter.verify 로 위임(직접 판정 없음).
- `prompts.py` — task별 evidence-extraction prompt. `sample_output_schema.json` — 최종 output 예시.

## 사용
```
export QWEN3B_MODEL_PATH=/data/models/Qwen2.5-VL-3B-Instruct-AWQ   # weight 는 repo 에 없음
# dry-run (모델 없이 mock evidence → 기존 Rule Engine → final_result 검증)
python local_eval/vlm_baseline/qwen3b_evidence_engine.py --dry-run
# 실제(런타임에서 Qwen generate 구현 후)
python local_eval/vlm_baseline/qwen3b_evidence_engine.py --image <path> --task water   # evidence JSON
```
- dry-run: 7 케이스(water/study/exercise × positive/blocker/uncertain) 모두 **final_result 를 기존 Rule Engine 에서** 산출(7/7 기대 일치).

## 원칙
- Qwen weight/outputs/데이터셋 이미지 **git 미포함**. backend/Rule Engine core **미수정**(read-only import).
- 앱 사용: `final_result`. 앱 사용 금지: `qwen_raw_output`, `qwen_suggested_result`(debug).
- Rule Engine import 실패 시 adapter 는 보수적 fallback(retake) + TODO 로 연결 지점 표기.

## 배경
- SmolVLM-500M 온디바이스 단독 인증 = FP=9 탈락(루트 `SMOLVLM_ONDEVICE_EVAL_FINAL_DECISION.md`).
- 상세: 루트 `VLM_TASK_ARCHIVE_SUMMARY.md`, `QWEN3B_UNIFIED_VERIFICATION_BASELINE.md`, `QWEN3B_TASK_PROMPTS.md`, `QWEN3B_FALLBACK_ARCHITECTURE_NOTE.md`.
