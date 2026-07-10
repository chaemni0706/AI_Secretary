# On-device VLM 후보 비교 평가 (ondevice_vlm_eval)

이미지 인증(water/exercise/study)의 최종 목표는 **소형 VLM 온디바이스화**다. Qwen을 반드시
쓸 필요는 없고, **정확도 + Samsung Galaxy Z Flip3 5G 실행 가능성**이 핵심이다.

이 디렉터리는 동일한 water/exercise/study 테스트셋으로 여러 후보 모델을 **동일 인터페이스**로
비교하는 구조다. 기존 `local_eval/qwen_vlm_eval`(Qwen 전용 batch)는 그대로 유지된다.

## 1차 실험 후보 모델 (4개)

| 모델 | family | 크기 | 양자화 계획 | Z Flip3 적합성 | 선정 이유 |
|------|--------|------|------------|----------------|-----------|
| MiniCPM-V-4.6 | MiniCPM-V | ~8B | int4 GGUF / MLC | low-medium | 정확도 상한선(레퍼런스). 크기 부담이 커 온디바이스는 공격적 양자화 필요 |
| MobileVLM-V2-1.7B | MobileVLM | 1.7B | int4/int8, NNAPI | high | 모바일 추론 목적 설계 → Z Flip3에서 가장 현실적. 정확도 충족 여부가 관건 |
| SmolVLM-500M (대안 2.2B) | SmolVLM | 0.5B/2.2B | int8/int4, ONNX | high/medium | 초경량. 크기·속도 유리하나 세밀한 근거(빈 컵/학습 콘텐츠) 정확도 위험 → 2.2B와 트레이드오프 비교 |
| Qwen2.5-VL-3B-AWQ | Qwen2.5-VL | 3B | AWQ 4bit | medium | 기존 파이프라인이 Qwen2.5-VL-3B로 검증됨 → 정확도 비교 anchor + 온디바이스 가능성 |

상세 메타데이터: [model_candidates.yaml](model_candidates.yaml).

## 구조

```
local_eval/ondevice_vlm_eval/
├── adapters/
│   ├── base.py               # VLMAdapter ABC + ModelNotAvailable + empty_vision_analysis
│   ├── mock_adapter.py       # 매니페스트 픽스처를 모델 출력으로 반환 (구조 검증용)
│   ├── minicpm_v_adapter.py  # 실제 모델 stub (미탑재 → ModelNotAvailable)
│   ├── mobilevlm_adapter.py  # stub
│   ├── smolvlm_adapter.py    # stub
│   ├── qwen_awq_adapter.py   # stub
│   └── __init__.py           # ADAPTER_REGISTRY + build_adapter
├── model_candidates.yaml
├── run_ondevice_eval.py
└── README.md
```

## Adapter 공통 인터페이스

모든 어댑터는 동일 시그니처를 따른다:

```python
adapter.analyze(image_path, verification_type, context) -> VisionAnalysis 호환 dict
```

- 반환 dict는 backend `VisionAnalysis` 스키마와 호환(quality/objects/…/water|exercise|study_visual_evidence).
- 어댑터는 **시각 근거만** 추출한다. 최종 인증 판정은 Rule Engine(`evaluate_image_verification`)이 한다.
- 실제 모델은 아직 미탑재: 4개 실제 어댑터는 `available()==False`, `analyze()`는 `ModelNotAvailable`을 던진다.
- `MockAdapter`는 매니페스트 픽스처(사람이 검수한 vision_analysis = '완벽한 모델')를 반환해 파이프라인을 검증한다.

## 평가 흐름 (water/exercise/study)

```
manifest → 이미지별 (expected_label, activity_type, vision_analysis 픽스처)
        → adapter.analyze() (실제 or --simulate 시 픽스처)
        → VisionAnalysis
        → evaluate_image_verification(type, analysis, context)   # exercise는 activity_type 컨텍스트 포함
        → verified/rejected/retake_required → PASS/FAIL/BORDERLINE_CASE → ok / false_positive
```

- water/exercise: `data/test_images/{water,exercise}/*_manifest.json`의 `images[].vision_analysis`
- study: `local_eval/study_verification_fixture_pack/study_ground_truth.jsonl` + `fixtures/{id}.json`
- **wakeup은 평가 대상에서 제외**된다(세션/시간 기반이라 시각 근거 평가가 아님). `--verification-types wakeup`은 거부된다.

## 실행

```bash
# 전체 후보 × water/exercise/study (실제 모델 없으면 픽스처로 시뮬레이션)
python local_eval/ondevice_vlm_eval/run_ondevice_eval.py

# 특정 모델/타입만
python local_eval/ondevice_vlm_eval/run_ondevice_eval.py --models mobilevlm,smolvlm --verification-types water,study

# 실제 어댑터만 사용 (미탑재 모델은 SKIPPED)
python local_eval/ondevice_vlm_eval/run_ondevice_eval.py --no-simulate
```

옵션: `--models`, `--verification-types`, `--simulate`(기본)/`--no-simulate`, `--output`.

### 리포트 CSV 컬럼

`model_name, verification_type, filename, expected_label, predicted_label, engine_result, ok,
false_positive, latency_ms, model_size_mb, runtime_target, visual_evidence, objects`

기본 출력: `local_eval/ondevice_vlm_eval/outputs/ondevice_eval_report.csv`

> `--simulate` 모드에서는 모든 모델이 동일한 픽스처를 출력하므로 정확도(ok)가 동일하게 나온다.
> 이는 **파이프라인/리포트 구조 검증**용이다. 실제 모델을 어댑터에 붙이고 `--no-simulate`로 돌리면
> 모델별 정확도·지연(latency_ms)이 실제로 갈린다. 크기/런타임(model_size_mb/runtime_target)은
> model_candidates.yaml 기반이다.

## 실제 모델 연동 방법 (다음 단계)

각 실제 어댑터의 `analyze()`에 추론을 구현하고 `available()`이 True를 반환하게 하면 된다:
이미지+타입별 프롬프트로 추론 → 출력을 VisionAnalysis 호환 dict로 정규화
(`normalize_water_output` / `normalize_exercise_output` / `normalize_qwen_output`의 함수 재사용 가능).
런타임 계획은 llama.cpp(GGUF) / MLC-LLM(AWQ) / ONNX Runtime / NNAPI.
