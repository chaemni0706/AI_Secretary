# Qwen-3B as Image Evidence Engine (into EXISTING Rule Engine)

작성 2026-07-10, 개정. branch: `archive/vlm-qwen3b-unified-baseline`.
> **방향 수정**: 새 verification 시스템을 만드는 게 아니라, **기존 앱/검증 시스템 구조를 유지하고 "이미지 판독 엔진"만 Qwen-3B 로 교체**한다.
> **Qwen-3B 는 최종 판정 모델이 아니다.** Qwen-3B 는 기존 객체/장면/evidence 판독 엔진을 대체하는 **evidence extractor** 이며, 최종 verified/rejected/retake_required 는 **기존 Rule Engine** 이 결정한다.

## 1. 구조 (기존 구조 유지 + adapter 삽입)
```
Camera Image
  → 기존 시스템 입력부
  → Qwen-3B 객체/장면/evidence 판독 엔진        (기존 객체 판독 엔진/SmolVLM 자리 교체)
  → 기존 evidence/parser/normalizer            (adapter: Qwen evidence → VisionAnalysis schema)
  → 기존 Rule Engine (evaluate_image_verification)   ← 최종 판정 여기서
  → verified / rejected / retake_required
```

## 2. 역할 분리 (중요)
- **Qwen-3B**: evidence 만 추출(visible_objects/actions/scene, positive/negative/blockers, uncertainty, image_quality). **final_result 확정 금지.**
- **adapter**(`qwen3b_evidence_adapter.py`): Qwen evidence 토큰 → **기존 Rule Engine 이 기대하는 VisionAnalysis evidence 코드**로 변환 + 기존 `evaluate_image_verification` 호출.
- **기존 Rule Engine**(backend, **미수정**): 최종 verified/rejected/retake_required 결정 + FP=0 정책.

## 3. 기존 Rule Engine interface (확인됨)
- `evaluate_image_verification(verification_type, VisionAnalysis, ImageVerificationContext) -> ImageVerificationData(.result/.score/.mandatory_passed/.rule_evidence)`.
- VisionAnalysis: quality/scene/objects/visible_text + `{water|study|exercise}_visual_evidence`(고정 Literal enum 코드).
- adapter 는 이 schema 로만 변환하고 core 는 수정하지 않는다.

## 4. 파일
- `local_eval/vlm_baseline/qwen3b_evidence_engine.py`: extract(image_path, task) → Qwen evidence JSON. (run_qwen_evidence_extraction / parse_qwen_evidence). 모델 로드/generate 는 skeleton(런타임), **weight 는 repo 에 없음**(QWEN3B_MODEL_PATH).
- `local_eval/vlm_baseline/qwen3b_evidence_adapter.py`: to_existing_rule_input(evidence,task) → VisionAnalysis; run_existing_rule_engine(); verify() 파이프라인.
- `local_eval/vlm_baseline/qwen3b_unified_verifier.py`: [deprecated] adapter.verify 로 위임(직접 판정 없음).
- prompts: `prompts.py`(evidence 추출) + `QWEN3B_TASK_PROMPTS.md`.

## 5. Qwen 출력(evidence) 스키마 — final result 없음
```json
{
  "task": "water|study|exercise",
  "image_quality": "good|poor|unusable|unknown",
  "visible_objects": [], "visible_actions": [], "scene_type": "",
  "positive_evidence": [], "negative_evidence": [], "blockers": [],
  "uncertainty": "low|medium|high", "reason": ""
}
```

## 6. 최종 output (기존 시스템 호환)
```json
{
  "task": "water",
  "final_result": "verified|rejected|retake_required",   // 앱이 사용 (기존 Rule Engine 산출)
  "rule_reason": "", "rule_trace": [],
  "evidence": { "positive_evidence": [], "negative_evidence": [], "blockers": [],
                "uncertainty": "...", "image_quality": "...", "visible_objects": [], "visible_actions": [],
                "mapped_rule_codes": [] },
  "debug": { "engine": "qwen3b", "qwen_raw_output": "", "qwen_parse_status": "clean|repaired|failed" }
}
```
- **앱 사용**: `final_result`.  **앱 사용 금지**: `qwen_raw_output`, `qwen_suggested_result`(debug 전용).

## 7. FP=0 우선 정책 (기존 Rule Engine 유지)
- blocker → rejected, 불확실(high) → uncertain 코드 추가 후 Rule Engine 이 retake, 근거 부족 → retake. 최종 결정은 Rule Engine.
- adapter 는 정책을 새로 만들지 않고 **기존 Rule Engine 이 결정하도록** evidence 를 충실히 매핑만 한다.

## 8. dry-run 검증 (7 케이스, 모두 Rule Engine 산출)
`python local_eval/vlm_baseline/qwen3b_evidence_engine.py --dry-run` → 7/7 기대 일치:
water(clear+bottle)→verified, water(empty)→rejected, study(laptop_only)→rejected, study(open_book+doc)→verified,
exercise(equipment_only)→rejected, exercise(person_exercising)→verified, water(unc high)→retake_required.

## 9. 한계 / 다음
- 서버 Qwen-3B 의존(온디바이스 완결성 낮음). **YOLO/OpenImages 전환 예정**(별도 phase).
- 실제 Qwen 로드/generate 는 skeleton(런타임 구현). backend/Flutter production 대규모 수정 없음; 통합은 local_eval/vlm_baseline adapter 로 먼저.
