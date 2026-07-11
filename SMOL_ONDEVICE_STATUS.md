# SMOL_ONDEVICE_STATUS

작성일: 2026-07-11
대상: SmolVLM-500M 을 앱의 **1차 local/on-device evidence engine** 으로 사용하기 위한 상태 감사 + 온디바이스화 구현 현황.

> **중요:** Smol 은 **final verifier 가 아니다.** 빠른 1차 evidence extractor 이며, confident 하지 않으면
> **Qwen2.5-VL-7B server fallback** 으로 넘긴다. 최종 판정은 항상 **기존 Rule Engine**.
> Smol 단독 최종 인증은 과거 final171 에서 **FP=9** 이력이 있어 금지(특히 water). → [smol_evidence_engine.py](local_eval/vlm_baseline/smol_evidence_engine.py) 참조.

## 1. 현재 상태

**분류: `smol_android_evidence_spike_partial`** (2026-07-12, Galaxy Z Flip3 실기기)
(이전: … → `smol_android_generation_spike_no_cache_verified` → `smol_android_image_text_generation_spike_verified` → **generated_text → evidence code 변환 연결(부분)**.)
- ✅ **generated_text → Rule Engine 호환 evidence 변환 성공(diagnostics-only)**: [SmolEvidenceParser](frontend/android/app/src/main/kotlin/com/example/frontend/SmolEvidenceParser.kt) 가 자유형 생성 텍스트를 task별 schema evidence code + `rule_engine_payload`(VisionAnalysis dict)로 변환. Smol 결과는 **최종 인증으로 채택하지 않음**(§10).
- ✅ **water task 실기기 end-to-end 검증**: 노란 차 이미지 → `"A glass of yellow liquid."` → `evidence_codes=[non_water_beverage]`, `blockers=[non_water_beverage]`, `local_accept_candidate=false`, `parse_status=clean`, `water_visual_evidence=[non_water_beverage]` (8224ms). **water colored-liquid blocker 정상 작동**.
- ✅ **실기기 6장 task 스모크 완료(gallery picker)**: image_picker 로 선택한 이미지는 앱 cache 로 복사돼 앱 프로세스가 바로 읽으므로 EROFS/FUSE 우회(§11). water 2 + study 2 + exercise 2.
  - **water 생성 정확**: 맑은 물→`"A glass of water."`→`[visible_water]`; 오렌지주스→`"Orange juice."`→`[non_water_beverage]`. positive/blocker 모두 정확 매핑.
  - **study/exercise 는 하드코딩 water-프롬프트 때문에 생성이 beverage 로 편향**(예: 책상+노트→"Tea.", 배낭→"A glass of water.") → 파서가 **보수적으로 `weak`/`uncertain_*` 처리, false-accept 0**. 모든 6장 `local_accept_candidate=false`, 무크래시(5~8s).
- ✅ **payload backend Rule Engine 투입 확인**: `rule_engine_payload` 4종을 실제 `evaluate_image_verification` 에 투입 → 오류 없이 소비. water[visible_water]→`rejected`(단일 코드/객체 없음→mandatory 미달, Smol 이 water 를 local-accept 하면 안 되는 근거 보강), water[non_water_beverage]→`rejected`, study/exercise weak→`retake_required`.
- ⚠️ **partial 사유(갱신)**: 이미지 배포는 gallery picker 로 해결됐으나, **study/exercise 는 하드코딩 프롬프트로 생성 텍스트가 부정확**해 task-정확 evidence 생성 불가(파서는 안전하게 fallback). water 만 생성·evidence 모두 정확. → task별 정확도는 부분.
- ⏳ spike/diagnostics 전용(프롬프트 water-하드코딩·task별 프롬프트 미구현, single-512 anyres 미적용, 서버 evidence schema 자동 투입 미연결) → `fallback_required=true` 유지, 서버 fallback + water local accept 금지 유지.
- ❌ cached KV-cache loop blocked(q4 export cast, §8). evidence→Rule Engine 자동 판정·앱 인증 화면 연결 안 됨. **"온디바이스 인증 완성" 아님.**

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
- ✅ **L4 generation loop(패딩 no-cache) + image merge + detokenize → 이미지→텍스트 생성 실기기 성공**("A glass of yellow liquid", §8/§9). cached KV-cache loop 은 q4 export cast 로 blocked.
- ✅ **generated_text → evidence 변환 + 실기기 6장 task 스모크(gallery picker)**: water 생성·evidence 정확, study/exercise 는 하드코딩 프롬프트로 생성 부정확 → 파서 보수 fallback(§10/§11).
- ⏳ task별 프롬프트/동적 tokenizer/anyres 미구현, 인증 미연결 → 서버 fallback.
- ❌ "온디바이스 인증 완성" 아님(evidence→Rule Engine 연결 전까지). 현 분류: `smol_android_evidence_spike_partial`.
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

## 8. L4 generation loop blocker — 원인 & 해소 (2026-07-11, Flip3 실기기)

### 근본 원인
L4 실패 노드 `InsertedPrecisionFreeCast_/model/layers.1/attn/v_proj/repeat_kv/Reshape_4/output_0` 는
**ORT graph optimization 산물이 아니라 q4f16 decoder export 에 내재**(NO_OPT 에서도 동일 노드로 실패).
증분 디코딩 시 prefill(seq=N)→decode(seq=1) 로 shape 가 바뀌며 ORT 가 이 cast 출력 버퍼를 재사용하다
`Shape mismatch attempting to re-use buffer {1,6,960}!={1,1,960}` 로 실패.

### 실험 (decoder OrtSession opt-level sweep + 패딩 전략)
| 실험 | 결과 |
|---|---|
| cached@ALL_OPT | ❌ Cast 에러 |
| cached@EXTENDED_OPT | ❌ Cast 에러 |
| cached@BASIC_OPT | ❌ Cast 에러 |
| cached@NO_OPT | ❌ **Cast 에러 동일** (→ 최적화 산물 아님, export 내재 확정) |
| **padded_nocache@ALL_OPT (PAD=16)** | ✅ **ok — 5 tokens `[…,198,504,2443,314]`, 788ms** |

`setMemoryPatternOptimization(false)` 도 무효. `any_loop_ok=true` 는 **패딩 no-cache** 로 달성.

### 해소 방법(구현·검증됨): 고정길이 패딩 + no-cache
- 매 스텝 decoder.run 입력 shape 를 `[1,PAD]`(PAD=16) 로 **고정**(pad token=2, attention_mask 로 실제 토큰만 표시,
  past_key_values 는 항상 빈 fp16) → ORT 버퍼 재사용 shape mismatch 를 회피.
- 결과: 1~5 token greedy 생성 성공, 앱 크래시/OOM 없음. **단점**: KV-cache 미사용(매 스텝 전체 재계산)이라 느림 —
  짧은 evidence 프롬프트엔 실용적, 긴 생성엔 비효율.
- 메모리: 실험이 decoder 세션을 5개(4 opt + 1 padded) 로드해 PSS ~1.35GB 로 치솟았으나(실구현은 **세션 1개 재사용**),
  OOM/crash 없음.

### 권장 export/구현 전략
1. **단기(현 자산)**: 패딩 no-cache(PAD=적정값)로 짧은 evidence 생성. 세션 1개 재사용 + max_new 작게.
2. **KV-cache 복원 원하면**: decoder 를 **precision-free cast 없이 재-export**(또는 fp32/int8 decoder, non-merged
   past/no-past 분리). transformers.js SmolVLM ONNX 파이프라인이 동일 export 라 cache feeding 방식 참고.
3. 최신 ONNX Runtime(버퍼 재사용 shape 검증 개선)에서 cached loop 재시도.

### 다음 작업(추론 완성까지)
패딩 no-cache 위에 **image_features→inputs_embeds 병합**(image token 위치) + tokenizer/chat_template(현재 하드코딩)
+ detokenize + anyres → evidence JSON(서버 schema). 완성 시 `smol_android_runtime_verified`.

## 9. 이미지→텍스트 생성 spike (2026-07-12, Flip3 실기기 성공)

패딩 no-cache 생성 위에 **tokenizer(detokenize) + image_features 병합**을 붙여 실기기에서 이미지 기반 짧은 텍스트 생성 검증.

### 구성
- **프롬프트/이미지 토큰**: SmolVLM processor(do_image_splitting=false) 출력 input_ids(len 80) 하드코딩.
  구조: `<|im_start|>User:<image>×64 Describe the drink briefly.<end_of_utterance>\nAssistant:`.
  image_token(`49190`) 64개가 위치 5..68 (config `image_token_id=49190`).
- **image merge**: vision_encoder `image_features[1,64,960]` 를 embed_tokens 출력 `inputs_embeds[1,80,960]` 의
  image_token 위치(5..68) 임베딩에 **치환**(System.arraycopy). = SmolVLM 의 이미지 임베딩 주입 방식.
- **생성**: 고정길이 패딩 no-cache(PAD=96) greedy, EOS(`49279`=<end_of_utterance>)에서 정지.
- **detokenize**: `tokenizer.json` 의 model.vocab(49152) + added_tokens(145) 로 id→token, **GPT2 byte-level BPE** 역디코드
  (bytes_to_unicode 역맵), 특수토큰(`<...>`) skip.

### 실기기 결과 (sample = water_020.jpg, 노란 차/주스 한 잔)
| level | 결과 |
|---|---|
| vision_encoder | ok `[1,64,960]` |
| embed_tokens | ok `[1,80,960]` |
| **image_merge** | ok (64 tokens @5) |
| **generation_loop** | ok **7 tokens** `[330,4433,282,5724,5553,30,49279]` (EOS 정지) |
| **detokenize** | ok |
| **generated_text** | **`"A glass of yellow liquid."`** ← 이미지(노란 액체) 의미 정확 |
| latency | **8070 ms** (vision + 7-token no-cache 생성) |
| memory | 앱 PSS ~437MB, **OOM/crash 없음** |
| fallback_required | true (diagnostics 전용, 인증 미연결) |

→ **온디바이스 이미지→일관 텍스트 생성 파이프라인이 실기기에서 실제로 동작**함을 검증. image merge/tokenizer/detokenize 모두 정상.

### 남은 작업(인증 완성까지)
1. **evidence 자동 투입**: 현재 `rule_engine_payload`(VisionAnalysis dict)는 생성하지만 backend evaluate_image_verification 자동 호출·앱 인증 결과 반영은 미연결(diagnostics 표시만). local-first accept 배선은 다음 단계.
2. **동적 tokenizer**: 현재 프롬프트 input_ids 하드코딩 → tokenizer(encode) 온디바이스 구현(또는 고정 프롬프트 유지).
3. **anyres splitting**: 다중 타일(정확도↑). 현재 single-512.
4. **성능**: no-cache 라 8s. KV-cache 복원(decoder 재-export) 또는 PAD/토큰수 축소.
5. 완성·검증 후 `smol_android_runtime_verified` + 앱 local accept(단, water 는 정책상 여전히 서버/review).


## 10. generated_text → evidence 변환 spike (2026-07-12, Flip3 실기기 부분 성공)

**목표:** on-device `generated_text` 를 task별 **기존 Rule Engine 호환 evidence code**(schema enum) + `rule_engine_payload`(VisionAnalysis dict)로 변환(diagnostics-only). **Smol 결과를 최종 인증으로 채택하지 않는다** — `fallback_required=true`, water local accept 금지 유지.

구현: [SmolEvidenceParser.kt](frontend/android/app/src/main/kotlin/com/example/frontend/SmolEvidenceParser.kt)(rule-based, task별 positive/blocker/uncertain 토큰표) → [imageTextGeneration](frontend/android/app/src/main/kotlin/com/example/frontend/SmolVlmBridge.kt) 6단계에서 호출. 진단 화면 task 선택기(water/study/exercise) 추가.

### 정책
- **water**: colored/yellow/brown/tea/coffee/juice/beer/soda/milk… → `non_water_beverage` blocker(강). `non_water_beverage` 감지 시 `visible_water`/`visible_clear_liquid` positive 취소(모순 방지). **`local_accept_candidate` 항상 false**(정책).
- **study/exercise**: positive 있고 blocker 없고 uncertainty≠high 이면 `local_accept_candidate=true`(단 진단 표시용, 채택 안 함). blocker → `local_reject_candidate=true`.
- 근거 없음/모호 → `parse_status=weak`, `uncertainty=high`, schema uncertain code 부여.

### 실기기 결과
| task | 이미지 | raw_text(생성) | evidence_codes | accept | reject | parse | ms |
|---|---|---|---|---|---|---|---|
| water | sample(노란 차) | "A glass of yellow liquid." | `[non_water_beverage]` | false | **true** | clean | 8224 |
| study | 위 water 이미지(불일치) | "A glass of yellow liquid." | `[uncertain_screen_content]` | false | false | weak | 7800 |

water: `rule_engine_payload.water_visual_evidence=[non_water_beverage]` → backend Rule Engine 투입 시 `water_priority:non_water_beverage` → **rejected**(정합). 앱 크래시/OOM 없음.

### parser 결정론 검증(host mirror — Kotlin 토큰표 1:1)
실기기 데이터 디렉터리 EROFS(§1)로 신규 이미지 배포 불가 → 아래는 **파서 로직**을 host 에서 재현(온디바이스 생성 아님). 위 실기기 2케이스가 mirror 예측과 **정확히 일치** → mirror 충실성 확인.
| task | 텍스트(예시) | evidence_codes | accept | reject |
|---|---|---|---|---|
| water | "A glass of water on a table." | `[visible_water]` | false(정책) | false |
| water | "A cup of coffee." | `[non_water_beverage]` | false | true |
| study | "reading a textbook with handwritten notes." | `[open_textbook, handwritten_notes]` | true | false |
| study | "playing a video game." | `[gaming_content]` | false | true |
| exercise | "running on a treadmill at the gym." | `[exercise_pose_visible, gym_environment, treadmill_present]` | true | false |
| exercise | "sitting on a sofa." | `[unrelated_environment]` | false | true |

### 왜 아직 일반 사용자 인증 화면에 연결 안 하나
- Smol 단독 최종 인증은 final171 FP=9 이력(특히 water) → 위험. 본 spike 는 **evidence 생성/매핑 검증**까지만.
- 생성 텍스트가 approximate(프롬프트 하드코딩·single-512·no-cache) → 신뢰도 부족 → 서버 Qwen fallback 이 최종 담당.

### 다음 단계
diagnostics 에서 task별 정확도 충분 확인 → local-first accept 배선(단 water 는 서버/정책 유지) → `rule_engine_payload` backend 자동 투입 → 검증 후 `smol_android_runtime_verified`.


## 11. 실기기 task별 6장 evidence 스모크 (2026-07-12, Flip3, gallery picker)

**이미지 접근 해결(핵심):** diagnostics 화면에 **갤러리 선택 버튼**(image_picker) 추가. 선택 이미지는 앱 `cache/` 로 복사되어 앱 프로세스가 바로 읽으므로, 그동안 막혔던 실기기 data-dir **EROFS**(run-as write) / 외부 dir **FUSE 격리**를 우회한다. (adb 로 test 이미지를 `/sdcard/Pictures/smol_tests/` 에 push → media scan → picker 로 선택.)
> 참고: 모델(361MB) 재배포는 `run-as … dd of=files/models/smolvlm/<f>`(직접 실행, cwd=home) 로 가능. `sh -c 'cat > …'` 는 cwd 가 `/`(RO)로 리셋되어 EROFS 가 나므로 쓰지 말 것.

**결과(diagnostics-only, `image+text→evidence`):**
| # | task | 이미지 | generated_text | evidence_codes | accept | reject | parse | ms |
|---|---|---|---|---|---|---|---|---|
| 1 | water | 맑은 물잔(PASS) | "A glass of water." | `[visible_water]` | false | false | clean | 7365 |
| 2 | water | 오렌지주스(FAIL) | "Orange juice." | `[non_water_beverage]` | false | **true** | clean | 5751 |
| 3 | study | 책상+필기(PASS) | "Tea." | `[uncertain_screen_content]` | false | false | weak | 5151 |
| 4 | study | 게임(FAIL) | "A glass of orange juice." | `[uncertain_screen_content]` | false | false | weak | 7522 |
| 5 | exercise | 배낭/야외 | "A glass of water." | `[uncertain_exercise_environment]` | false | false | weak | 7038 |
| 6 | exercise | 소파 휴식(FAIL) | "A glass of water." | `[uncertain_exercise_environment]` | false | false | weak | 6983 |

**해석:**
- **water 정확**: 맑은 물↔`visible_water`, 주스↔`non_water_beverage` 정확. positive/blocker 모두 동작. `local_accept_candidate` 는 정책상 항상 false.
- **study/exercise 부정확(생성 한계)**: 프롬프트가 water-spike 에서 하드코딩된 그대로라 study/exercise 이미지에도 beverage 를 서술("Tea.", "A glass of water.") → task evidence 없음. **파서는 이를 `weak`+`uncertain_*` 로 보수 처리해 false-accept 0.** 즉 파서 문제가 아니라 **task별 프롬프트 부재**가 원인.
- **파서 보수화**: 이미 안전(오생성에도 accept 안 함) → 이번엔 파서 규칙 변경 없음.
- **무크래시/OOM**, latency 5~8s.

**payload → backend Rule Engine 투입(host):** `rule_engine_payload` 4종을 실제 `evaluate_image_verification` 에 투입 → 오류 없이 소비.
`water[visible_water]→rejected`(단일 코드+객체 없음→mandatory 미달; Smol 이 water 를 local-accept 하면 안 되는 근거 보강), `water[non_water_beverage]→rejected`, `study/exercise weak→retake_required`. → `rule_engine_compatible=true` end-to-end 확인.

**남은 조건(local-first accept 전):** (1) **task별 프롬프트**(study/exercise 용) 로 생성 정확도 확보, (2) 정확도 충분 확인 후 study/exercise local accept 후보만 배선(water 는 서버/정책 유지), (3) evidence→Rule Engine 자동 판정 연결. 이때까지 `smol_android_runtime_verified` 금지, `fallback_required=true` 유지.
