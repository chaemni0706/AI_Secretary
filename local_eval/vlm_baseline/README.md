# local_eval/vlm_baseline

Qwen-3B **unified verification baseline** (VLM task 정리용). 임시 baseline — 최종 제품 구조 아님, **YOLO 전환 예정**.

## 구성
- `qwen3b_unified_verifier.py` — image_path + task → verified/rejected/retake_required (JSON). FP=0 우선 normalize. **skeleton**(런타임에서 Qwen2.5-VL 로드/generate 구현).
- `prompts.py` — task별 prompt(water/study/exercise). 요약: 루트 `QWEN3B_TASK_PROMPTS.md`.
- `sample_output_schema.json` — 출력 스키마 예시.

## 사용 (개념)
```
export QWEN3B_MODEL_PATH=/data/models/Qwen2.5-VL-3B-Instruct-AWQ   # weight 는 repo 에 없음
python qwen3b_unified_verifier.py --task water --image <path>
python qwen3b_unified_verifier.py --task study --image <path> --dry-run   # 모델 없이 normalize 경로 확인
```

## 원칙
- **VLM weight 는 git 에 포함하지 않는다**(config 경로로 분리).
- Qwen-3B 하나가 local/fallback 구분 없이 전체 verification 수행(임시).
- FP=0 우선: 애매/불확실 → retake_required, 부정 근거 → rejected, positive 충분+blocker 없음+불확실 낮음 → verified.
- 최종 판정 로직/제품 통합은 별도(backend Rule Engine 미수정). 이 폴더는 baseline 정리/스켈레톤.

## 배경
- SmolVLM-500M 온디바이스 단독 인증 = FP=9 로 탈락(루트 `SMOLVLM_ONDEVICE_EVAL_FINAL_DECISION.md`).
- Qwen2.5-VL-3B(별도 실측 전 task FP=0/study 1.000)를 임시 unified baseline 으로 정리.
- 상세: 루트 `VLM_TASK_ARCHIVE_SUMMARY.md`, `QWEN3B_UNIFIED_VERIFICATION_BASELINE.md`, `QWEN3B_FALLBACK_ARCHITECTURE_NOTE.md`.
