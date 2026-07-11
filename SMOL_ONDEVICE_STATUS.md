# SMOL_ONDEVICE_STATUS

작성일: 2026-07-11
대상: SmolVLM-500M 을 앱의 **1차 local/on-device evidence engine** 으로 사용하기 위한 상태 감사 + 온디바이스화 구현 현황.

> **중요:** Smol 은 **final verifier 가 아니다.** 빠른 1차 evidence extractor 이며, confident 하지 않으면
> **Qwen2.5-VL-7B server fallback** 으로 넘긴다. 최종 판정은 항상 **기존 Rule Engine**.
> Smol 단독 최종 인증은 과거 final171 에서 **FP=9** 이력이 있어 금지(특히 water). → [smol_evidence_engine.py](local_eval/vlm_baseline/smol_evidence_engine.py) 참조.

## 1. 현재 상태

**분류: `smol_android_runtime_stubbed`**
(이전: `smol_server_python_only` → 이번 작업으로 인터페이스/브릿지 스텁 + 온디바이스 자산 식별까지 진행. 실디바이스 런타임 검증은 미완.)

| 항목 | 값 |
|---|---|
| 모델 경로 | `/data/models/SmolVLM-500M-Instruct` (weight git 미포함) |
| safetensors 크기 | 6.5G (서버 Python 추론용) |
| **ONNX exports** | `/data/models/SmolVLM-500M-Instruct/onnx/` 존재 (transformers.js/ONNX Runtime 용) |
| 현재 서버 추론 | ✅ Python transformers `build_adapter("smolvlm")` (lazy singleton) |
| Flutter/Android 호출 | ❌ 현재 앱은 **server-only**(`POST /api/v1/verification/image/{type}`) — 온디바이스 미연결 |
| GGUF 대안 | `/data/models/SmolVLM2-2.2B-Instruct-GGUF`(2.2B, Q4_K_M+mmproj) — 500M 용은 ONNX 우선 |

## 2. 온디바이스 자산 (ONNX Runtime Mobile 경로 — 실측)

`onnx/` 안에 mobile-friendly 양자화 변형이 이미 존재한다. **q4f16 조합이 모바일 최적**:

| 컴포넌트 | 파일(q4f16) | 크기 |
|---|---|---|
| vision encoder | `vision_encoder_q4f16.onnx` | ~57 MB |
| token embed | `embed_tokens_q4f16.onnx` | ~94 MB |
| decoder(merged) | `decoder_model_merged_q4f16.onnx` | ~205 MB |
| **합계** | | **~356 MB** (Galaxy Z Flip3 적재 가능) |

(int8/uint8/bnb4 변형도 있음. 정확도-크기 트레이드오프는 디바이스 벤치 후 결정.)
전처리: `preprocessor_config.json`(SmolVLM image processor), 토크나이저: `tokenizer_config.json`+`merges.txt`+`chat_template.json` → asset 동봉 필요.

## 3. 이번 작업에서 구현한 것 (인터페이스/스텁)

앱을 깨지 않도록 **기존 화면에 배선하지 않은 additive interface/stub** 으로 추가:

- Flutter: [frontend/lib/models/image_verification_result.dart](frontend/lib/models/image_verification_result.dart)
  — local-first + server fallback 통합 결과 모델(`finalResult/engineUsed/reviewRequired/reviewReason/localResult/fallbackResult`).
- Flutter: [frontend/lib/services/smol_ondevice_verifier.dart](frontend/lib/services/smol_ondevice_verifier.dart)
  — 온디바이스 Smol 추론 **인터페이스 + stub**(`isAvailable=false` → 서버 fallback 유도). ONNX 자산/연결 TODO 명시.
- Flutter: [frontend/lib/services/image_verification_service.dart](frontend/lib/services/image_verification_service.dart)
  — **오케스트레이터**: Smol on-device first → confident 하면 반환, 아니면 `VerificationApi`(서버 Qwen7B fallback) 호출.
- Flutter: [frontend/lib/models/verification_result.dart](frontend/lib/models/verification_result.dart) 확장
  — `reviewRequired`/`reviewReason` getter(백엔드 `data` 에서 읽음, non-breaking).
- Android: [frontend/android/app/src/main/kotlin/com/example/frontend/SmolVlmBridge.kt](frontend/android/app/src/main/kotlin/com/example/frontend/SmolVlmBridge.kt)
  — ONNX Runtime MethodChannel **브릿지 스켈레톤**(MainActivity 미배선, 독립 클래스).
- Python(local-first 계약): [local_eval/vlm_baseline/vlm_fallback_verifier.py](local_eval/vlm_baseline/vlm_fallback_verifier.py)
  — `verify_image_with_vlm_fallback(image, task)` = Smol local → server fallback → guard → review policy. **온디바이스가 mirror 할 response schema 기준.**

## 4. 온디바이스 런타임을 "실동작"시키려면 (남은 작업)

1. `onnxruntime`(Flutter: `onnxruntime` pub 또는 Android AAR `onnxruntime-android`) 의존성 추가.
2. q4f16 ONNX 3종 + tokenizer/merges/chat_template/preprocessor 를 `android/app/src/main/assets/models/smolvlm/` 에 asset 동봉(**git 미포함**, CI/release 시 주입).
3. SmolVLM 추론 루프 구현(Kotlin/JNI 또는 Dart): image preprocess → vision_encoder → embed_tokens → decoder autoregressive(use_cache) → detokenize → evidence JSON.
4. 출력 evidence 를 서버와 **동일 schema** 로 정규화 → `SmolOndeviceVerifier` 반환.
5. Galaxy Z Flip3 실디바이스 smoke(load/generate/latency/메모리) → 상태 `smol_android_runtime_verified` 로 승격.

## 5. 상태 요약

- ✅ 온디바이스 자산(ONNX q4f16) 확보, 인터페이스/오케스트레이터/브릿지 스텁 구현, 서버 fallback 계약 확정.
- ❌ 실디바이스 ONNX 추론은 미구현(현 환경에 디바이스/빌드 없음) → **stubbed**.
- 원칙: Smol verified(특히 water)는 로컬 단독 확정 금지 → 서버 fallback/`review_required` 로. exercise/study 만 local accept 적극 허용 가능.
