# SMOL_ONDEVICE_STATUS

작성일: 2026-07-11
대상: SmolVLM-500M 을 앱의 **1차 local/on-device evidence engine** 으로 사용하기 위한 상태 감사 + 온디바이스화 구현 현황.

> **중요:** Smol 은 **final verifier 가 아니다.** 빠른 1차 evidence extractor 이며, confident 하지 않으면
> **Qwen2.5-VL-7B server fallback** 으로 넘긴다. 최종 판정은 항상 **기존 Rule Engine**.
> Smol 단독 최종 인증은 과거 final171 에서 **FP=9** 이력이 있어 금지(특히 water). → [smol_evidence_engine.py](local_eval/vlm_baseline/smol_evidence_engine.py) 참조.

## 1. 현재 상태

**분류: `smol_android_decoder_step_verified`** (2026-07-11, Galaxy Z Flip3 실기기 spike)
(이전: … → `smol_android_session_load_verified` → **verifyImage spike L1~L3 실기기 성공**(전처리+vision_encoder / embed_tokens / decoder 1-step). L4(KV-cache 생성 loop)는 blocked.)
- ✅ L1 vision_encoder / L2 embed_tokens / L3 decoder 1-step 실기기 성공(§7 표).
- ❌ L4 generation loop blocked(merged decoder KV-cache Cast 버그). **이미지 추론 미완 → 서버 fallback 유지. "온디바이스 완성" 아님.**

### 실기기 session-load smoke 결과 (2026-07-11)
| 항목 | 값 |
|---|---|
| device | Galaxy Z Flip3 (SM-F711N), arm64-v8a, Android 15 |
| package | `com.example.frontend` (debug, run-as 가능) |
| APK install | uninstall(서명 불일치) 후 재설치 성공 |
| 모델 배치 | `run-as … cat > files/models/smolvlm/<f>` 스트리밍 → `getModelInfo`: 6/6 found, 361,194,130 bytes, `status=available`, dir=`/data/user/0/com.example.frontend/files/models/smolvlm` |
| **warmup (OrtSession load)** | **`success=true`, `sessions_loaded=3`, latency `1117 ms`** |
| vision_encoder | in `[pixel_values, pixel_attention_mask]` → out `[image_features]` |
| embed_tokens | in `[input_ids]` → out `[inputs_embeds]` |
| decoder_merged | out `[logits, present.N.key/value …]`(KV-cache) |
| memory / OOM | 앱 TOTAL PSS ~534MB, Native Heap ~196MB, **OOM/FATAL/crash 없음**(logcat clean) |
| inference | `verifyImage` = `unsupported_preprocessing`/`fallback_required`(미구현, 서버 fallback) |

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

- ✅ onnxruntime-android 통합 + fallback-safe 브릿지 + local-first 배선 + APK 빌드 + **실기기 OrtSession 로드**, 그리고 **verifyImage spike L1~L3(vision_encoder/embed_tokens/decoder 1-step) 실기기 성공**(§7).
- ⏳ **L4 generation loop blocked**(merged decoder KV-cache Cast 버그), image-merge/tokenizer/detokenize 미구현 → 서버 fallback.
- ❌ "온디바이스 완성" 아님(실기기 **완전 추론/evidence** 전까지). 현 분류: `smol_android_decoder_step_verified`.
- 원칙: Smol verified(특히 water)는 로컬 단독 확정 금지 → 서버 fallback / `review_required`(재촬영). exercise/study 만 local accept 적극 허용 가능.

## 6. 실기기 session-load smoke — 상태 & 수동 runbook (2026-07-11)

### 상태(이 세션)
- ✅ **실기기(Galaxy Z Flip3) 연결 → runbook 실행 → OrtSession 3종 로드 성공 검증 완료**(§1 표 참조).
- 진단 화면 [smol_diagnostics_screen.dart](frontend/lib/screens/smol_diagnostics_screen.dart)
  (진입: 이미지 인증 화면 AppBar 의 memory 아이콘 — `kDebugMode`)에서 getModelInfo/warmup 로 확인.

### 수동 runbook (Galaxy Z Flip3 연결 후)
```bash
# 0) 기기 인식
adb devices                 # device 목록에 Flip3 확인
adb shell getprop ro.product.model      # SM-F711* 등
adb shell getprop ro.product.cpu.abi    # arm64-v8a

# 1) debug APK 설치 (package = com.example.frontend)
adb install -r frontend/build/app/outputs/flutter-apk/app-debug.apk

# 2) 모델 배치: 원본 → /sdcard → run-as 로 앱 filesDir 로 복사 (git/assets 미포함)
PKG=com.example.frontend
adb shell rm -rf /sdcard/Download/smolvlm_tmp
adb shell mkdir -p /sdcard/Download/smolvlm_tmp
adb push /data/models/SmolVLM-500M-Instruct/onnx/vision_encoder_q4f16.onnx        /sdcard/Download/smolvlm_tmp/
adb push /data/models/SmolVLM-500M-Instruct/onnx/embed_tokens_q4f16.onnx          /sdcard/Download/smolvlm_tmp/
adb push /data/models/SmolVLM-500M-Instruct/onnx/decoder_model_merged_q4f16.onnx  /sdcard/Download/smolvlm_tmp/
adb push /data/models/SmolVLM-500M-Instruct/tokenizer.json           /sdcard/Download/smolvlm_tmp/
adb push /data/models/SmolVLM-500M-Instruct/config.json              /sdcard/Download/smolvlm_tmp/
adb push /data/models/SmolVLM-500M-Instruct/preprocessor_config.json /sdcard/Download/smolvlm_tmp/
adb shell run-as $PKG mkdir -p files/models/smolvlm
adb shell "run-as $PKG sh -c 'cp /sdcard/Download/smolvlm_tmp/* files/models/smolvlm/'"
adb shell run-as $PKG ls -l files/models/smolvlm     # 6개 파일(3 onnx + 3 config) 확인
# (run-as 는 debug APK 에서만 동작. 실패 시 앱 최초 실행 시 다운로드/복사 로직 필요.)

# 3) 앱에서 진단 실행
#    앱 실행 → "이미지 인증" 화면 → AppBar 오른쪽 memory 아이콘 → getModelInfo / isModelAvailable / warmup
#    warmup 결과 JSON 에서 status=loaded, sessions_loaded=3, io.<file>.inputs/outputs, latency(ms) 확인

# 4) logcat (선택)
adb logcat -c
adb logcat | grep -iE "smol|onnx|ort|flutter"
```

### 성공/실패 기준
- 성공: warmup `status=loaded`, `sessions_loaded=3`, vision_encoder/embed_tokens/decoder_merged 의 input/output names 반환, 앱 크래시 없음 → 상태 `smol_android_session_load_verified` 로 승격.
- 실패(모델 못 찾음/ORT unsupported op/OOM/ABI) → 원인 기록 후 `smol_ondevice_blocked`. (tokenizer/preprocessor 누락은 warmup 실패 사유 아님 — verifyImage 단계 이슈.)

## 7. verifyImage 추론 spike 결과 (2026-07-11, Galaxy Z Flip3 실기기)

`SmolVlmBridge.verifyImage` 에 추론 경로 spike(Level 1~4) 구현 후 진단화면에서 실행(sample.jpg, task=water).
**단순화(spike caveat):** 단일 512×512(anyres splitting 미적용), image_features 를 디코더에 병합하지 않은 **text-only**,
tokenizer 미구현 → 고정 프롬프트 token ids 하드코딩(`[1,37964,260,2443,30]` = BOS+"Describe the image."). 항상 `fallback_required=true`.

### ONNX signature (핵심)
- vision_encoder: in `pixel_values f32[b,num_img,3,512,512]`, `pixel_attention_mask bool[b,num_img,512,512]` → out `image_features f32[N,64,960]`
- embed_tokens: in `input_ids i64[b,seq]` → out `inputs_embeds f32[b,seq,960]`
- decoder_model_merged: in `inputs_embeds f32`, `attention_mask i64`, `position_ids i64`, **32층×past_key_values.N.key/value fp16[b,5,past,64]** → out `logits f32[b,seq,49280]` + 32층 present.N (hidden 960, vocab 49280, 32 layers, 5 KV heads, head_dim 64)

### Level 결과
| Level | 결과 | 상세 |
|---|---|---|
| **L1 vision_encoder** | ✅ ok | image_features `[1,64,960]`, ~2.3s (전처리 rescale 1/255 + normalize(mean/std 0.5), pixel_attention_mask all-true) |
| **L2 embed_tokens** | ✅ ok | inputs_embeds `[1,5,960]`, ~2ms |
| **L3 decoder 1-step** | ✅ ok | 빈 KV prefill → logits `[1,5,49280]`, argmax token `198`, ~99ms |
| **L4 generation loop** | ❌ blocked | 2번째 스텝(KV-cache 재투입) 시 `ORT_RUNTIME_EXCEPTION` |
| 합계 | — | verifyImage 총 ~3.7s, 앱 PSS ~759MB, **OOM/crash 없음**, fallback 유지 |

### L4 blocker (정확한 원인)
```
E onnxruntime: Non-zero status code returned while running Cast node.
Name:'InsertedPrecisionFreeCast_/model/layers.1/attn/v_proj/repeat_kv/Reshape_4/output_0'
Shape mismatch attempting to re-use buffer. {1,1,960} != {1,6,960}
```
- merged decoder(q4f16)에 export 단계에서 삽입된 `InsertedPrecisionFreeCast` 가, prefill(seq=6)→decode(seq=1) 로
  sequence 길이가 바뀔 때 ORT 실행 프레임의 **버퍼 재사용**과 충돌한다.
- `SessionOptions.setMemoryPatternOptimization(false)` 시도 → **효과 없음**(이 cast/reshape 는 모델 그래프에 내장, ORT 메모리패턴만의 문제 아님).

### L4 해소 후보 (future)
1. 디코더를 **precision-free cast 없이 재-export**(또는 fp32/int8 decoder), 혹은 non-merged(past/no-past 분리) 모델 사용.
2. decode step 을 **고정 길이로 패딩**(seq 변동 제거)해 버퍼 재사용 shape 를 고정.
3. **최신 ONNX Runtime**(버퍼 재사용 shape 검증 개선 버전) 시도.
4. transformers.js 의 SmolVLM ORT 파이프라인(동일 export)이 참고: image-merge/tokenizer/chat_template 포함 필요.

### 남은 작업(추론 완성까지)
- 위 L4 해소 + tokenizer/chat_template(현재 하드코딩) + **image_features → inputs_embeds 병합**(image token 위치) + anyres splitting + detokenize → evidence JSON(서버 schema). 완성 시 `smol_android_runtime_verified`.
