# 온디바이스 TFLite 분류기 구현 명세서 (intent · emotion)

> 목적: 현재 스텁 상태인 온디바이스 의도/감정 분류기를 **실제로 동작**시키기 위한 단계별 실행 문서.
> 모델 아티팩트와 기기 런타임이 준비되면 이 문서만 따라가면 바로 이행할 수 있도록, 학습→export→전처리 계약→패키지 통합→서비스 코드→화면 연동→검증까지 정의한다.
> 대상 파일: `frontend/lib/services/on_device_model_service.dart`, `intent_classifier_service.dart`, `emotion_model_classifier_service.dart`, `frontend/assets/models/`.

---

## 0. 현재 상태 (기준선)

- `tflite_flutter` 패키지 **미도입** → `OnDeviceModelService.tryLoadInterpreter()`는 항상 `null`.
- `OnDeviceModelService.enableOnDeviceModel = false` (하드코딩 게이트).
- `intent_classifier.tflite` / `emotion_classifier.tflite` **파일 없음**(assets/models엔 샘플 `.jsonl`만).
- 두 서비스는 전부 **rule-based fallback**으로 동작(`_ruleClassify`, `LocalEmotionClassifier`). 어떤 화면도 두 서비스를 아직 호출하지 않음.
- 라벨 계약(코드에 고정):
  - intent: `create_schedule | create_todo | ask_briefing | emotion_coaching | reservation_request | unknown`
  - emotion: `neutral | tired | anxious | angry | sad | burden_high`
- `minConfidence = 0.60` 미만이면 rule-based로 폴백.

**안전 원칙(불변):** 감정 모델은 라벨 정교화만 보조한다. 위기 감지·안전문구·코칭 문구는 **항상 `LocalEmotionClassifier`(rule-based)**가 담당하며, 모델이 이를 override하지 않는다.

---

## 1. 전체 파이프라인

```
(1) 데이터 확장     sample.jsonl  →  train.jsonl (수백~수천 라벨)
(2) 전처리 계약     text → 고정길이 정수 벡터  (train/infer 동일 코드로 재현)
(3) 학습·export     TF/Keras 소형 MLP  →  float32 .tflite  (+ metadata.json)
(4) 통합            pubspec: tflite_flutter + assets 등록,  .tflite 배치
(5) 추론 코드       tryLoadInterpreter → Interpreter.fromAsset,
                    각 서비스 _runModel(토크나이즈→추론→argmax)
(6) 화면 연동       음성/채팅 입력 라우팅에 IntentClassifierService 사용
(7) 검증·롤아웃     기기 eval(FP/정확도), confidence 임계, 플래그 단계적 on
```

핵심 난점은 **(2) 전처리 계약**이다. 학습 시 텍스트를 벡터로 바꾼 방식과 **Dart 추론 시 방식이 1:1로 동일**해야 한다. 아래는 외부 vocab 파일 없이 재현 가능한 **char n-gram 해싱(feature hashing)** 방식을 기준으로 한다(한국어 형태소 분석기를 Dart에 이식하지 않아도 됨).

---

## 2. 데이터셋 준비

형식(기존 유지): 한 줄당 `{"text": "...", "label": "..."}`.

```jsonl
{"text": "내일 2시에 회의 잡아줘", "label": "create_schedule"}
{"text": "요즘 너무 지치고 피곤해", "label": "tired"}
```

- 라벨은 위 6종 계약을 벗어나지 않게 한다(코드 라벨 순서 = 모델 출력 인덱스 순서, §4 참고).
- 클래스당 최소 수백 문장 권장. `unknown`(intent)은 잡담/무관 문장으로 충분히 채워 false trigger를 억제한다.
- 감정은 특히 경계 사례(빈정/반어)를 라벨링하되, **위기 표현은 모델 학습 대상에서 제외**하고 rule-based가 처리하게 둔다.

---

## 3. 전처리 계약 (train ↔ infer 동일)

**방식: char 2-gram 해싱 → 고정 길이 `D` bag-of-ngrams(정규화) float 벡터.**

상수(양쪽에서 동일하게 고정):

| 상수 | 값(예) | 의미 |
|------|--------|------|
| `D` | 4096 | 해시 버킷 수(입력 벡터 차원) |
| `NGRAM` | 2 | 문자 n-gram 크기 |
| `NORMALIZE` | L1 | 벡터 합=1 정규화 |
| 해시 | FNV-1a 32bit | 결정적, 언어 독립 |

의사코드(양쪽 공통):

```
normalize(text): trim → lower(영문) → 공백 1칸 축소   # 한글은 그대로
features(text):
  v = float[D] (0)
  s = normalize(text)
  for i in 0..len(s)-NGRAM:
    g = s[i : i+NGRAM]
    h = fnv1a(g) % D
    v[h] += 1
  if sum(v) > 0 and NORMALIZE==L1: v /= sum(v)
  return v
```

FNV-1a(32bit): `h=2166136261; for c in bytes(g): h=(h XOR c)*16777619 mod 2^32`. UTF-8 바이트 기준으로 통일한다(Python `g.encode('utf-8')`, Dart `utf8.encode(g)`).

> 이 방식은 vocab 파일이 필요 없고, Python과 Dart에서 **완전히 동일한 벡터**를 만든다. 정확도가 부족하면 후속으로 형태소 토크나이저 + 임베딩(+ `vocab.json` 번들)으로 승급한다(§9).

---

## 4. 학습 & TFLite export (Python, 학습 머신에서)

라벨 인덱스는 **코드의 라벨 배열 순서와 동일**해야 한다.

```python
# intent 라벨 순서 = IntentClassifierService.labels
INTENT_LABELS = ["create_schedule","create_todo","ask_briefing",
                 "emotion_coaching","reservation_request","unknown"]
EMOTION_LABELS = ["neutral","tired","anxious","angry","sad","burden_high"]

D, NGRAM = 4096, 2
def fnv1a(b):
    h = 2166136261
    for x in b: h = ((h ^ x) * 16777619) & 0xFFFFFFFF
    return h
def features(text):
    import numpy as np
    s = " ".join(text.strip().lower().split())
    v = np.zeros(D, dtype="float32")
    for i in range(len(s)-NGRAM+1):
        v[fnv1a(s[i:i+NGRAM].encode("utf-8")) % D] += 1.0
    t = v.sum()
    return v/t if t>0 else v

# X = [features(t) for t in texts], y = [label_index]
import tensorflow as tf
model = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(D,)),
    tf.keras.layers.Dense(128, activation="relu"),
    tf.keras.layers.Dropout(0.2),
    tf.keras.layers.Dense(len(LABELS), activation="softmax"),
])
model.compile("adam","sparse_categorical_crossentropy",metrics=["accuracy"])
model.fit(X, y, epochs=30, validation_split=0.15)

conv = tf.lite.TFLiteConverter.from_keras_model(model)
conv.optimizations = [tf.lite.Optimize.DEFAULT]      # 크기↓(동적 양자화)
open("intent_classifier.tflite","wb").write(conv.convert())
```

**출력 계약(중요):**
- 입력 텐서: shape `[1, D]`, dtype `float32`.
- 출력 텐서: shape `[1, C]`, dtype `float32`(softmax 확률). `C = 라벨 수(6)`.
- 라벨 인덱스 순서 = 위 배열. `metadata.json`에 `{ "D":4096, "ngram":2, "labels":[...], "hash":"fnv1a-utf8" }`를 함께 저장해 계약을 문서화한다.

---

## 5. pubspec & assets 통합

```yaml
dependencies:
  tflite_flutter: ^0.11.0   # 도입 시점 최신. AGP 9 호환 확인 필수(아래 주의)

flutter:
  assets:
    - assets/models/         # .tflite 포함
```

**AGP 9 호환 주의:** 이 프로젝트는 `vosk_flutter_2`를 로컬 vendoring해 gradle을 수정한 이력이 있다(pubspec 주석). `tflite_flutter`의 네이티브(.so) 로드가 AGP 9/NDK와 충돌하면, ① 최신 버전 우선 시도 → ② 안 되면 vosk처럼 로컬 vendor 후 `namespace`/`compileSdk` 보정. 릴리즈 시 `.so` 관련 proguard/`packagingOptions` 확인.

배치: 학습한 `intent_classifier.tflite`, `emotion_classifier.tflite`를 `frontend/assets/models/`에 넣는다.

---

## 6. 서비스 코드 구현

### 6-1. `on_device_model_service.dart`

- `enableOnDeviceModel`을 개발자 설정/`--dart-define`로 제어(하드코딩 대신).
- `tryLoadInterpreter`의 TODO를 실제 로드로 교체 + **인터프리터 캐시**(매 호출 재로드 금지):

```dart
import 'package:tflite_flutter/tflite_flutter.dart';

final Map<String, Interpreter> _cache = {};
Future<Object?> tryLoadInterpreter(String assetPath) async {
  if (!isEnabled) return null;
  final hit = _cache[assetPath];
  if (hit != null) return hit;
  if (!await assetExists(assetPath)) return null;
  try {
    final itp = await Interpreter.fromAsset(assetPath);
    _cache[assetPath] = itp;
    return itp;
  } catch (e) {
    debugPrint('[OnDeviceModel] 로드 실패 → fallback: $e');
    return null;
  }
}
```

- 공용 전처리/추론 유틸을 한 곳에 두어 두 서비스가 재사용:

```dart
List<double> hashFeatures(String text, {int d = 4096, int n = 2}) {
  final s = text.trim().toLowerCase().split(RegExp(r'\s+')).join(' ');
  final v = List<double>.filled(d, 0);
  for (var i = 0; i + n <= s.length; i++) {
    final bytes = utf8.encode(s.substring(i, i + n));
    var h = 2166136261;
    for (final b in bytes) { h = ((h ^ b) * 16777619) & 0xFFFFFFFF; }
    v[h % d] += 1.0;
  }
  final total = v.fold<double>(0, (a, b) => a + b);
  if (total > 0) { for (var i = 0; i < d; i++) v[i] /= total; }
  return v;
}

/// interpreter 실행 → (argmax label, confidence).
ClassifierResult runModel(Interpreter itp, List<String> labels, String text) {
  final input = [hashFeatures(text)];               // [1, D]
  final output = [List<double>.filled(labels.length, 0)]; // [1, C]
  itp.run(input, output);
  final probs = output[0];
  var best = 0;
  for (var i = 1; i < probs.length; i++) { if (probs[i] > probs[best]) best = i; }
  return ClassifierResult(
    label: labels[best], confidence: probs[best], source: 'on_device_model');
}
```

### 6-2. `intent_classifier_service.dart`

`classify()`의 TODO 블록을 교체:

```dart
final interpreter = await onDeviceModelService.tryLoadInterpreter(
  OnDeviceModelService.intentModelAsset);
if (interpreter is Interpreter) {
  final r = onDeviceModelService.runModel(interpreter, labels, input);
  if (r.confidence >= OnDeviceModelService.minConfidence) return r;
  // 낮으면 아래 rule fallback으로 진행
}
```

### 6-3. `emotion_model_classifier_service.dart` (안전 유지)

```dart
final rule = LocalEmotionClassifier.classify(text);        // 항상 먼저
final interpreter = await onDeviceModelService.tryLoadInterpreter(
  OnDeviceModelService.emotionModelAsset);
if (interpreter is Interpreter && rule.safetyNote == null /* 위기 아님 */) {
  final r = onDeviceModelService.runModel(interpreter, emotionLabels, text);
  if (r.confidence >= OnDeviceModelService.minConfidence) {
    // 라벨만 교체, coaching_reply/safety_note는 rule 값을 유지
    return rule.copyWithLabel(r.label);
  }
}
return rule;   // 스텁/저신뢰/위기 → rule 전체 결과
```

> `EmotionAnalysis`에 라벨만 바꾸는 헬퍼(`copyWithLabel`)가 없으면 추가한다. **위기(safetyNote 존재)면 모델을 절대 태우지 않는다.**

---

## 7. 화면 연동

현재 두 서비스는 미사용이다. 도입 시:
- **의도 라우팅**: 음성/채팅 입력(`ai_chat_screen`, `voice_*_screen`)에서 서버 파싱 전에 `IntentClassifierService.classify`로 1차 라우팅(오프라인/빠른 분기). 규칙과 동일 라벨이라 기존 분기 로직 재사용.
- **감정 라벨**: `emotion_*` 화면/코칭에서 라벨 정교화에만 사용(문구·안전은 rule 유지).

라우팅은 항상 "모델 confidence≥0.6 → 사용, 아니면 기존 규칙/서버"의 폴백 순서를 지킨다.

---

## 8. 검증 & 롤아웃

- **오프라인 정확도**: held-out 셋으로 클래스별 정확도/혼동행렬. `unknown`(intent)·경계 감정 위주 오류 점검.
- **기기 벤치**: 실제 단말에서 지연(ms)·메모리·APK 증가량 측정. 동적 양자화로 크기 최소화.
- **false trigger 가드**: intent는 `unknown` 재현율을, emotion은 위기 미검출 0을 최우선(위기는 rule 담당이므로 모델이 놓쳐도 안전).
- **롤아웃**: `enableOnDeviceModel`을 debug→내부 베타→일반 순으로 단계적 on. 회귀 시 플래그만 끄면 즉시 rule-based로 원복.
- **테스트**: `hashFeatures`의 Python↔Dart 동일성 골든 테스트(같은 입력 → 같은 상위 인덱스), 저신뢰 시 fallback 단위 테스트.

---

## 9. 리스크 & 승급 경로

- **정확도 부족(해싱 BoW 한계)**: 문맥·어순을 못 잡음 → 형태소 토크나이저(kiwipiepy, 학습측) + `vocab.json` 번들 + 임베딩 평균/1D-CNN으로 승급. 단 Dart가 동일 토큰화를 재현해야 하므로 vocab 기반 화이트리스트 토큰화로 계약을 단순화.
- **패키지/AGP 충돌**: §5 주의. 최악의 경우 vendoring.
- **모델·전처리 드리프트**: `metadata.json`으로 D/ngram/labels/hash를 고정하고, 앱 로드시 검증(불일치면 모델 비활성).

---

## 10. 체크리스트 (이행 순서)

1. [ ] 데이터셋 확장(클래스당 수백+, `unknown` 충분)
2. [ ] `features()` 상수 확정(D, NGRAM, 해시) — 문서화
3. [ ] 학습 → `.tflite` + `metadata.json` export(입력 `[1,D]` f32 / 출력 `[1,6]` f32)
4. [ ] pubspec: `tflite_flutter` + assets, AGP 호환 확인
5. [ ] `.tflite` 2종 배치
6. [ ] `tryLoadInterpreter` 실제 로드 + 캐시
7. [ ] `hashFeatures`/`runModel` 공용 유틸 + 두 서비스 `_runModel` 연결(감정 안전 유지)
8. [ ] Python↔Dart 전처리 동일성 골든 테스트
9. [ ] 화면 라우팅 연동(confidence 폴백)
10. [ ] 기기 eval → 플래그 단계적 on
