# On-device VLM 평가 지표 정의 (METRICS)

`run_ondevice_eval.py`가 저장하는 정량 지표의 정의와 해석 기준.

## expected_label / predicted_label 매핑

- **expected_label**: 테스트셋 정답. `PASS` | `FAIL` | `BORDERLINE`
  - study 원본은 `verified/rejected/retake_required` → `PASS/FAIL/BORDERLINE`로 매핑.
- **predicted_label**: Rule Engine 결과를 매핑. `verified→PASS`, `rejected→FAIL`, `retake_required→BORDERLINE_CASE`.
- **정오 판정(ok)**: "PASS인가 아닌가"로 본다.
  - `expected == PASS` → `ok = (predicted == PASS)`
  - `expected in {FAIL, BORDERLINE}` → `ok = (predicted != PASS)`

## 혼동행렬 (positive = PASS)

인증에서 "positive"는 **PASS(인증 성공)**로 정의한다.

|            | predicted PASS | predicted ≠ PASS |
|------------|----------------|------------------|
| expected PASS   | **TP** | **FN** |
| expected ≠ PASS | **FP** | **TN** |

- **TP**: 실제 인증 대상인데 PASS로 맞게 판정
- **TN**: 인증 대상이 아닌데(빈 컵/비운동/비학습) 올바르게 PASS 거부
- **FP**: 인증 대상이 아닌데 **PASS로 잘못 판정** (가장 위험)
- **FN**: 실제 인증 대상인데 PASS를 놓침 (덜 위험)

`SKIPPED`(모델 미탑재) / `ERROR`(픽스처 없음) 행은 혼동행렬·지표에서 제외하고 `error_cases.csv`에만 남긴다.

## 지표 공식

- accuracy = (TP + TN) / (TP + TN + FP + FN)
- precision = TP / (TP + FP)   — PASS라고 한 것 중 실제 맞은 비율
- recall = TP / (TP + FN)      — 실제 인증 대상 중 잡아낸 비율
- f1 = 2·precision·recall / (precision + recall)
- false_positive_rate (FPR) = FP / (FP + TN)
- false_negative_rate (FNR) = FN / (FN + TP)
- latency: avg / p50 / p95 / min / max (ms) — per_image의 `latency_ms` 기준

분모가 0이면 해당 지표는 0.0으로 둔다.

## false positive가 가장 중요한 이유

이미지 인증의 목적은 "사용자가 실제로 그 활동(물 마시기/운동/공부)을 했다"는 것을 신뢰 가능하게 기록하는 것이다.

- **FP(오탐)** = 하지 않은 활동을 "인증됨"으로 처리 → 습관 추적·리워드의 **신뢰가 근본적으로 무너진다.**
- **FN(미탐)** = 실제로 했는데 인증 실패 → 사용자가 다시 촬영하면 되므로 회복 가능하고 피해가 작다.

따라서 인증 시스템은 **"false positive is worse than false negative"** 원칙을 따른다.
Rule Engine도 빈 컵/반사/색 음료/비운동/비학습 화면을 우선 거절하도록 보수적으로 설계되어 있다.

## Z Flip3 후보 선정 기준 (우선순위)

목표 기기: Samsung Galaxy Z Flip3 5G (Snapdragon 888, 8GB RAM).

1. **false_positive_rate 최소화** (인증 신뢰성의 핵심)
2. **accuracy / recall** (전반 정확도, 실제 활동을 놓치지 않기)
3. **온디바이스 실행 가능성**
   - `model_size_mb` (양자화 후 크기), `avg/p95 latency_ms`, `peak_gpu_memory_mb`
   - `android_feasibility` (llama.cpp / MLC / NNAPI / ONNX 런타임 계획)

즉 "정확도가 비슷하면 더 작고 빠른 모델"을, "크기가 비슷하면 FP가 더 낮은 모델"을 택한다.

## 산출물 (run 폴더별)

`outputs/runs/{timestamp}_{models}_{types}/`
- `per_image_report.csv` — 이미지 단위 전체 컬럼
- `predictions.jsonl` — 이미지 단위 JSON 라인
- `metrics_summary.csv` / `.json` — 모델×(인증타입 + ALL) 집계
- `confusion_matrix.csv` — 모델×인증타입 TP/TN/FP/FN
- `latency_summary.csv` — 모델×인증타입 지연 통계
- `error_cases.csv` — ok=false 또는 error 행 (FP 반드시 포함)
- `experiment_report.md` — 사람이 읽는 요약 + FP 사례 + 해석
- `raw_outputs/`, `normalized_outputs/` — 모델 원본/정규화 출력 (simulate에서는 normalized만)

> simulate=True는 매니페스트 픽스처를 '완벽한 모델' 출력으로 사용하는 **구조 검증 모드**다.
> 모든 모델이 동일 픽스처를 쓰므로 정확도가 동일하게 나온다. 실제 모델 비교는 어댑터에 추론을
> 연결하고 `--no-simulate`로 실행할 때 갈린다.
