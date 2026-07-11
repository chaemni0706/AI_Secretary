# SMOL_ONDEVICE_STATUS

작성일: 2026-07-11
대상: SmolVLM-500M 을 앱의 **1차 local/on-device evidence engine** 으로 사용하기 위한 상태 감사 + 온디바이스화 구현 현황.

> **중요:** Smol 은 **final verifier 가 아니다.** 빠른 1차 evidence extractor 이며, confident 하지 않으면
> **Qwen2.5-VL-7B server fallback** 으로 넘긴다. 최종 판정은 항상 **기존 Rule Engine**.
> Smol 단독 최종 인증은 과거 final171 에서 **FP=9** 이력이 있어 금지(특히 water). → [smol_evidence_engine.py](local_eval/vlm_baseline/smol_evidence_engine.py) 참조.

## 1. 현재 상태

**분류: `smol_android_runtime_integrated` (build-verified, device-unverified)**
(이전: `smol_server_python_only` → `smol_android_runtime_stubbed` → 이번 작업으로 **onnxruntime-android 통합 + OrtSession 로드/fallback-safe 브릿지 + Flutter local-first 배선 + Android APK 빌드 성공**.
아직 **실기기에서 session-load/이미지 추론은 미검증**이고, `verifyImage` 실제 추론은 미구현(전처리/생성 파이프라인) → 서버 fallback. 완성 아님.)

### 빌드 검증 (2026-07-11)
- `flutter build apk --debug` → **`✓ Built app-debug.apk` (70.3s) 성공.**
- APK 에 **`libonnxruntime.so` 번들 확인**(arm64-v8a / armeabi-v7a / x86_64). Galaxy Z Flip3=arm64-v8a 커버.
- 즉 **onnxruntime-android:1.18.0 의존성 해결 + `SmolVlmBridge.kt`(OrtEnvironment/OrtSession) 컴파일 + 런타임 패키징**이 검증됨.
- 미검증: 실기기 OrtSession 로드/추론(디바이스/전처리 필요).

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

## 3. 이번 작업에서 구현한 것 (ONNX Runtime 통합)

- Android dependency: `frontend/android/app/build.gradle.kts` 에 `com.microsoft.onnxruntime:onnxruntime-android:1.18.0` 추가
  → APK 에 `libonnxruntime.so`(arm64-v8a/armeabi-v7a/x86_64) 번들 확인.
- Android bridge: [SmolVlmBridge.kt](frontend/android/app/src/main/kotlin/com/example/frontend/SmolVlmBridge.kt)
  — `OrtEnvironment`/`OrtSession` **로드(warmup)** + 모델 가용성/정보 + **fallback-safe**(예외를 Flutter 로 안 던짐, 항상 JSON 반환).
  MethodChannel `ai_secretary/smolvlm`: `isModelAvailable`/`getModelInfo`/`warmup`/`verifyImage`(+하위호환 `isAvailable`/`inferEvidence`).
  `verifyImage` 는 **실제 추론 미구현 → `status=unsupported_preprocessing`, `fallback_required=true`** (서버 fallback).
- Android registration: [MainActivity.kt](frontend/android/app/src/main/kotlin/com/example/frontend/MainActivity.kt)
  `configureFlutterEngine` 에서 `SmolVlmBridge(applicationContext).register(...)`.
- Flutter service: [smol_ondevice_verifier.dart](frontend/lib/services/smol_ondevice_verifier.dart)
  `isModelAvailable/getModelInfo/warmup/verifyImage/inferEvidence` — 모두 fallback-safe(미지원/예외 시 null/`fallback_required`).
- Flutter orchestrator: [image_verification_service.dart](frontend/lib/services/image_verification_service.dart)
  local-first → confident accept(**water 는 로컬 채택 금지**) → 아니면 서버 `VerificationApi` fallback.
- 모델 경로: 앱 `filesDir/models/smolvlm/` (q4f16 ONNX 3종 + tokenizer.json/config.json/preprocessor_config.json). **git/assets 미포함**(.gitignore: `*.onnx`,`*.ort`, assets/models, `**/models/smolvlm/`).

## 4. 온디바이스 "실기기 추론"까지 남은 작업

1. 모델 파일(~356MB)을 실기기 `filesDir/models/smolvlm/` 로 배치(개발용 push 또는 최초 실행 시 download).
2. `verifyImage` 실제 추론 구현(Kotlin): image preprocess(SmolVLM anyres tiling) → tokenizer/chat_template →
   vision_encoder → embed_tokens → decoder autoregressive(KV-cache) → detokenize → evidence JSON(서버와 동일 schema).
3. Galaxy Z Flip3 실디바이스 smoke: `warmup`(OrtSession 로드) + `verifyImage`(load/latency/메모리) → 성공 시
   상태 `smol_android_runtime_verified` 로 승격.
4. 정확도/크기 트레이드오프(q4f16 vs int8/bnb4) 디바이스 벤치.

## 5. 상태 요약

- ✅ **onnxruntime-android 통합 + OrtSession 로드/fallback-safe 브릿지 + local-first 배선 + APK 빌드 성공(build-verified)**.
- ⏳ 실기기 session-load/이미지 추론 미검증, `verifyImage` 전처리/생성 파이프라인 미구현 → 현재는 서버 fallback.
- ❌ "온디바이스 완성" 아님(실기기 이미지 추론 성공 전까지). 현 분류: `smol_android_runtime_integrated`.
- 원칙: Smol verified(특히 water)는 로컬 단독 확정 금지 → 서버 fallback / `review_required`(재촬영). exercise/study 만 local accept 적극 허용 가능.
