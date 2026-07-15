# On-device VLM 실험 리포트 — 20260707_004310_smolvlm2_2b_water-exercise

- 실행 시각: 20260707_004310
- simulate: False (True면 픽스처 기반 = '완벽한 모델' 시뮬레이션)
- 모델: SmolVLM2-2.2B-Instruct
- 인증 타입: water, exercise  (wakeup 제외 — 세션/시간 기반이라 VLM 평가 대상 아님)
- 총 샘플 수(행): 30, 분류 대상: 30

## 모델별 요약 (전체 인증타입 합산)

| model | accuracy | false_positive | avg_latency_ms | size_mb | android |
|-------|----------|----------------|----------------|---------|---------|
| SmolVLM2-2.2B-Instruct | 0.9333 | 1 | 665.097 | 4400 | medium |

## False positive 사례

| model | type | filename | expected | predicted |
|-------|------|----------|----------|-----------|
| SmolVLM2-2.2B-Instruct | exercise | generated_exercise_09_food_table.png | FAIL | PASS |

## 해석 메모

- **인증 기능에서는 false positive(빈 컵/비운동/비학습을 PASS로 오인)가 가장 위험한 지표다.**
  사용자가 실제로 하지 않은 활동을 '인증됨'으로 처리하면 습관 추적 신뢰가 무너지기 때문이다.
- 따라서 후보 모델 선택 1순위는 **false_positive_rate 최소화**, 그 다음이 accuracy/recall,
  그리고 Z Flip3 실행 가능성(model_size_mb / latency / android_feasibility)이다.
- simulate=True 결과는 파이프라인 검증용이며, 실제 모델 정확도 비교는 --no-simulate + 실제 어댑터로 수행한다.
