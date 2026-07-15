# 온디바이스 분류 모델 (실험용)

이 폴더는 **실험용** TFLite/LiteRT 분류 모델과 학습 데이터 샘플을 두는 곳입니다.
현재는 모델 파일(`.tflite`)이 없어도 되고, 앱은 항상 rule-based fallback으로 정상 동작합니다.

> ⚠️ 감정 분류 모델은 **의학적/심리 진단이 아니라 UX 보조 라벨링**입니다.
> 위기 감지·안전문구·코칭 문구는 항상 rule-based(`LocalEmotionClassifier`)가 담당하며,
> 모델은 감정 "라벨 정교화"만 보조합니다.

## 상태 (MVP 기준)

- `OnDeviceModelService.enableOnDeviceModel = false` (기본) → 모델 코드 실행 안 함.
- `tflite_flutter` 패키지 **미도입** → `tryLoadInterpreter()`는 스텁으로 항상 `null` 반환.
- 따라서 `intent_classifier_service` / `emotion_model_classifier_service` 는 지금 전부
  rule-based fallback으로 동작합니다. 앱 핵심 기능은 이 폴더/모델에 의존하지 않습니다.

## 파일

- `intent_classifier.tflite` (선택, 미포함) — intent 6-클래스 분류 모델을 여기에 둡니다.
- `emotion_classifier.tflite` (선택, 미포함) — emotion/burden 6-클래스 분류 모델.
- `intent_dataset.sample.jsonl` — intent 학습 데이터 샘플.
- `emotion_dataset.sample.jsonl` — emotion 학습 데이터 샘플.

## 실제로 모델을 켜려면 (향후)

1. `pubspec.yaml` 에 패키지 + 에셋 등록:
   ```yaml
   dependencies:
     tflite_flutter: ^0.11.0   # 버전은 도입 시점 최신으로

   flutter:
     uses-material-design: true
     assets:
       - assets/models/
   ```
2. 학습한 `.tflite` 파일을 이 폴더에 넣습니다.
3. `OnDeviceModelService.enableOnDeviceModel` 를 true 로(또는 개발자 설정 플래그로) 전환.
4. `OnDeviceModelService.tryLoadInterpreter()` 의 TODO 위치에서
   `Interpreter.fromAsset(assetPath)` 를 반환하도록 교체하고,
   각 서비스의 `_runModel` 부분(토크나이즈→추론→argmax)을 구현합니다.

## 라벨

- intent: `create_schedule`, `create_todo`, `ask_briefing`, `emotion_coaching`,
  `reservation_request`, `unknown`
- emotion/burden: `neutral`, `tired`, `anxious`, `angry`, `sad`, `burden_high`

## 데이터 포맷

- JSONL (권장): 한 줄당 `{"text": "...", "label": "..."}`.
- CSV 대안: 헤더 `text,label` 후 각 행. 콤마/따옴표는 CSV 이스케이프 규칙 준수.
  ```csv
  text,label
  "내일 2시에 회의 잡아줘",create_schedule
  "오늘 너무 힘들어",emotion_coaching
  "브리핑 해줘",ask_briefing
  ```

## 입출력 스키마

- input: 사용자 문장(String)
- preprocessing: `trim()` + 영문 소문자화. 한국어는 형태소 분석 없이 키워드/서브워드
  토크나이즈(모델 학습 시 정한 vocab에 맞춤).
- output: `{ label: String, confidence: double }`
- confidence < `OnDeviceModelService.minConfidence`(0.60) → rule-based/서버로 fallback.
