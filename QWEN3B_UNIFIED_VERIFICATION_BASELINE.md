# Qwen-3B Unified Verification Baseline

작성 2026-07-10. branch: `archive/vlm-qwen3b-unified-baseline`.
> 임시 VLM baseline(팀 공유용). 최종 제품 구조 아님. YOLO 전환 예정.

## 1. 구조
```
Camera Image
  → Qwen-3B VLM (Qwen2.5-VL-3B-Instruct[-AWQ])
  → task-specific prompt (water / study / exercise)
  → verified / rejected / retake_required
  → result logging / report
```
- 이 baseline 에서는 **Qwen-3B 하나가 local/fallback 구분 없이 전체 verification 을 수행**한다(온디바이스 SmolVLM 역할 + 서버 fallback 역할 모두 대체).

## 2. Qwen-3B 가 담당하는 것
- **water verification** / **study verification** / **exercise verification** — 세 task 의 verified/rejected/retake_required 판정.

## 3. 출력 형식 (JSON)
```json
{
  "task": "water|study|exercise",
  "result": "verified|rejected|retake_required",
  "positive_evidence": [],
  "negative_evidence": [],
  "uncertainty": "low|medium|high",
  "reason": ""
}
```
- (참고) 스키마 예시: `local_eval/vlm_baseline/sample_output_schema.json`.

## 4. retake_required 기준
- 이미지 흐림/저조도(image blur/quality poor)
- 객체 불명확(핵심 대상 식별 불가)
- task evidence 부족(positive 근거 약함)
- **불확실성 high**(uncertainty=high)

## 5. FP=0 우선 정책 (핵심)
- **애매하면 verified 금지** → retake_required.
- **불확실하면 retake_required**(uncertainty high).
- **negative blocker 가 있으면 rejected**(예 water: 빈컵/색음료; study: 게임/영상; exercise: 앉아 쉬는 중/장비만).
- positive 근거가 뚜렷하고 blocker/불확실이 없을 때만 **verified**.

## 6. 판정 우선순위 (parser/normalize)
1. runtime/parse 실패 또는 image unusable → **retake_required**.
2. negative blocker 존재 → **rejected**.
3. uncertainty high 또는 positive 근거 부족 → **retake_required**.
4. positive 근거 충분 + blocker 없음 + 불확실 낮음 → **verified**.
- VLM 이 result 를 직접 내되(이 baseline 은 VLM 이 판정), **애매/불확실은 반드시 retake/reject 로** normalize(FP=0 우선).

## 7. 구현
- 스켈레톤: `local_eval/vlm_baseline/qwen3b_unified_verifier.py`
  - input: image_path, task → output: 위 JSON.
  - task-specific prompt 선택(`prompts.py`), Qwen2.5-VL 호출, result parser + normalize.
  - **모델 경로는 config(환경변수/인자)로 분리**. **모델 weight 는 git 에 포함하지 않음**(로컬 `/data/models/...`).
- prompts: `local_eval/vlm_baseline/prompts.py` (+ 요약 `QWEN3B_TASK_PROMPTS.md`).

## 8. 한계 / 다음
- 서버 의존(온디바이스 완결성 낮음), Qwen-3B latency/VRAM 필요.
- **YOLO/OpenImages 기반 구조로 전환 예정**(별도 phase). 이 baseline 은 그 전까지의 팀 공유용 정리본.
