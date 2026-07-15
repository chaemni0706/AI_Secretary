# SmolVLM-500M 온디바이스화 계획 (Z Flip3 / Android)

> ⚠️ **HOLD — SmolVLM-500M 온디바이스 단독 NO-GO (2026-07-09).** real-only 171장 실측 FP=9(시각 분별력 부족)로
> 온디바이스 단독 인증 후보 탈락. 이 패키징 계획(ORT Mobile/조합 A)은 **아키텍처 참고용으로 보존**하되, SmolVLM-500M
> 으로는 진행하지 않는다. 다음 온디바이스 후보가 real-only **FP=0** 를 통과하면(→ NEXT_ONDEVICE_MODEL_SEARCH_PLAN)
> 그 모델로 본 패키징 절차를 적용한다. 근거: SMOLVLM_FINAL_NO_GO.md.

목적: (초기) 온디바이스 1차 후보였던 **SmolVLM-500M-Instruct** 를 Z Flip3(Android)에서
실행하기 위한 패키징/런타임/측정/통합 계획. 이 문서는 계획서이며 backend/Flutter/Rule Engine 을
변경하지 않는다. 모델은 **evidence 만 추출**하고 최종 판정은 항상 **Rule Engine** 이 한다(FP=0 최우선).

작성일 2026-07-09. 근거 수치는 `/data/models/SmolVLM-500M-Instruct` 실측.

---

## 1. 현재 SmolVLM-500M 모델 구조
SmolVLM-500M-Instruct = **Idefics3 계열 경량 VLM**, 3개 논리 모듈로 분해되어 ONNX export 됨:
- **vision_encoder** — SigLIP 기반 이미지 인코더. 입력 이미지(패치) → image hidden states(embeds).
- **embed_tokens** — 텍스트 토큰 임베딩 테이블(입력 토큰 id → 임베딩). 이미지 embed 와 concat.
- **decoder_model_merged** — SmolLM2-360M급 언어 디코더(merged = KV-cache 포함 self/with-past 통합 그래프). autoregressive 토큰 생성.
- 부속: `tokenizer.json`/`vocab.json`/`merges.txt`(BPE), `preprocessor_config.json`(이미지 resize/normalize), `config.json`/`chat_template.json`.

추론 흐름(현 파이프라인과 동일): image → vision_encoder → image_embeds; prompt tokens → embed_tokens;
[image_embeds ⊕ text_embeds] → decoder(loop, KV cache) → tokens → detokenize → raw_text
→ **파서(to_vision_analysis)** → VisionAnalysis evidence → **Rule Engine** → verified/rejected/retake.

## 2. `/data/models/SmolVLM-500M-Instruct` 가 6.5GB 인 이유
전체 6.5GB = `model.safetensors`(968MB, PyTorch 원본) + `onnx/`(5.5GB). **onnx/ 가 큰 이유는 동일 3개
모듈을 8가지 정밀도로 중복 저장**하기 때문(HF onnx-community 배포 관례):

| 모듈 | 정밀도 변형(각 1개씩) | 대표 크기 |
| --- | --- | --- |
| decoder_model_merged | (fp32)1383MB, fp16 692MB, int8/uint8/quantized 각 348MB, **q4 219MB**, bnb4 197MB, **q4f16 196MB** | 최대 1.38GB |
| vision_encoder | (fp32)375MB, fp16 188MB, int8/uint8/quantized 각 95MB, **q4 64MB**, bnb4 58MB, **q4f16 55MB** | — |
| embed_tokens | (fp32)181MB, bnb4 181MB, q4 181MB, fp16/q4f16 각 90MB, **int8/uint8/quantized 각 45MB** | — |

→ 8×3 = 24개 onnx 파일이 모두 들어있어 5.5GB. **실제 배포에는 각 모듈당 1개 정밀도만** 선택하면
합계 300~400MB 로 급감. 즉 6.5GB 는 "모든 정밀도 보관용"이고 온디바이스 패키지와 무관.

## 3. Android 패키징 후보 ONNX 조합 (모듈당 1개씩)
FP=0/정확도 유지를 위해 vision 은 int8(정보 손실 민감), decoder 는 q4, embed 는 int8/q4f16 권장.

| 조합 | decoder | vision | embed | 합계(모델) |
| --- | --- | --- | --- | --- |
| **A (권장)** | decoder_model_merged_q4 219MB | vision_encoder_int8 95MB | embed_tokens_int8 46MB | **~360MB** |
| B (더 작게) | decoder_model_merged_q4f16 196MB | vision_encoder_q4f16 55MB | embed_tokens_int8 46MB | ~297MB |
| C (vision 화질 우선) | decoder_model_merged_q4 219MB | vision_encoder_int8 95MB | embed_tokens_q4f16 90MB | ~404MB |
| D (decoder q4 + vision q4) | 219MB | vision_encoder_q4 64MB | embed_tokens_int8 46MB | ~329MB |
- + tokenizer/config 세트: `tokenizer.json`(3.4MB), `vocab.json`(0.8MB), `merges.txt`(0.45MB),
  `config.json`, `preprocessor_config.json`, `chat_template.json`, `special_tokens_map.json`, `added_tokens.json` ≈ **~5MB**.
- **권장 = A** (q4 decoder + int8 vision + int8 embed). vision int8 은 빈 컵/물 구분 등 시각 디테일 보존에 q4 보다 안전(FP 관점).

## 4. 예상 Android 패키지 크기: 약 330~400MB
- 모델(조합 A) ~360MB + tokenizer/config ~5MB + ONNX Runtime Mobile(.aar, arm64) ~15~25MB
  → **APK/모델 자산 합계 대략 330~400MB** (조합 B 선택 시 ~320MB, C 선택 시 ~420MB).
- 배포 옵션: (a) 모델을 APK asset 에 포함(설치 즉시 오프라인) 또는 (b) 최초 실행 시 다운로드(APK 경량화).
  인증은 오프라인 신뢰성이 중요하므로 **(a) 포함** 우선, 용량 이슈 시 (b).

## 5. ONNX Runtime Mobile 을 1순위로 추천하는 이유
1. **SmolVLM 이 이미 ONNX(모듈별)로 배포**됨 → 별도 변환/그래프 수술 불필요(즉시 사용).
2. **3-모듈 분해 실행에 자연스럽게 맞음**(vision/embed/decoder 각 InferenceSession + 앱에서 KV-cache 루프 제어).
3. **양자화 자산이 이미 존재**(q4/int8/q4f16) → 추가 캘리브레이션 없이 크기/속도 확보.
4. Android arm64 **NNAPI/XNNPACK EP** 지원, 성숙한 Kotlin/Java API, 안정적.
5. transformers.js/optimum 파이프라인과 동일 자산 → 데스크톱 결과와 **행위 재현성** 높음(파서/프롬프트 그대로).
6. llama.cpp/MLC 처럼 SmolVLM 전용 그래프 포팅/컨버전 리스크가 없음(MiniCPM GGUF에서 vision abort 겪은 전례).

## 6. 런타임 비교 (SmolVLM-500M 기준)
| 런타임 | 장점 | 단점 | SmolVLM 적합성 |
| --- | --- | --- | --- |
| **ONNX Runtime Mobile** ★1순위 | 기존 onnx 자산 그대로, 양자화 완비, NNAPI/XNNPACK, 안정 | 3모듈 orchestration 앱단 구현 필요 | **높음(즉시)** |
| MLC-LLM | 모바일 GPU(Vulkan/Adreno) 컴파일 최적화 | SmolVLM(Idefics3) 컨버전/비전 파이프라인 포팅 필요, 리스크 | 중(변환 검증 필요) |
| llama.cpp GGUF | CPU/Vulkan 경량, 커뮤니티 | SmolVLM용 GGUF+mmproj 안정성 미검증(MiniCPM-V2 vision abort 전례), 변환 필요 | 낮음(리스크) |
| TFLite | 안드로이드 네이티브, NNAPI/GPU delegate, 작음 | ONNX→TFLite 변환(동적 KV-cache/attention) 난이도 높음 | 낮음(변환난이도) |
| ExecuTorch | PyTorch 공식 온디바이스, 미래성 | 아직 성숙도/툴체인 초기, export 수술 필요 | 중장기 후보 |
→ **1순위 ONNX Runtime Mobile, 2순위(성능 튜닝 시) MLC, 나머지는 보류.**

## 7. Z Flip3 기준 측정 항목 (Snapdragon 888 / 8GB / Adreno 660)
각 항목 목표치(잠정)와 함께 계측:
- **cold start**(앱 최초, 세션 생성+가중치 로드 포함) — 목표 ≤ 6s
- **model load time**(3개 세션 로드/메모리 매핑) — 목표 ≤ 3s
- **image preprocessing time**(resize/normalize, SmolVLM 다중 패치) — 목표 ≤ 150ms
- **warm inference**(로드 후 이미지 1장 evidence 생성 총합) — **목표 ≤ 3s(실패조건 >3s)**
- **decoder time**(토큰 생성 루프, max_new_tokens=32~48) — 항목 분리 계측
- **vision encode time** — 분리 계측
- **peak memory**(RSS + GPU) — **목표 ≤ 2GB(실패조건 >2GB)**
- **total latency**(촬영→evidence→Rule Engine 판정 반환) 및 배터리/발열(참고)
- 계측은 EP별(CPU/XNNPACK vs NNAPI) 비교, 정밀도 조합(A/B/D)별 비교.

## 8. Android inference API 초안
```kotlin
// 모델은 PASS/FAIL 판정 금지 — evidence 만 생성. 판정은 (온디바이스/서버) Rule Engine.
interface OnDeviceVLM {
  fun warmUp()                        // 세션 3개 로드(model load time 계측 지점)
  fun analyze(image: Bitmap, type: VerificationType, activity: String?): VisionEvidence
  fun isReady(): Boolean              // 세션 로드 성공 여부 → false 면 서버 fallback
}
// 내부 파이프라인 (ORT Mobile)
// 1) preprocess(image) → pixel_values (preprocessor_config: size/mean/std, 다중 패치 분할)
// 2) visionSession.run(pixel_values) → image_embeds
// 3) tokenizer.encode(buildPrompt(type)) → input_ids ; embedSession.run(input_ids) → text_embeds
// 4) inputs_embeds = concat(image_embeds, text_embeds)  (image token 위치 병합)
// 5) decoder loop: decoderSession.run(inputs_embeds, past_kv) → logits → argmax(greedy, do_sample=false)
//    append token, feed past_kv, until EOS or max_new_tokens(32~48)
// 6) raw_text = tokenizer.decode(newTokens)
// 7) evidence = parse(raw_text, type)   // 데스크톱 to_vision_analysis 와 동일 규칙 이식
// 반환: VisionEvidence(JSON, evidence only)
```
- 프롬프트/파서는 데스크톱 `smolvlm_adapter`(build_prompt/to_vision_analysis)와 **바이트 동등** 이식
  (특히 water: 용기 이름만으로 visible_water 금지, empty 명시 필요 — FP=0 규칙 유지).
- greedy(do_sample=false, temp=0)로 결정성 확보.

## 9. evidence JSON schema (backend VisionAnalysis 호환)
```json
{
  "quality": { "brightness": "normal", "blur": "low", "usable": true, "issues": [] },
  "scene": null,
  "objects": [ { "label": "glass", "confidence": 0.6, "evidence": null } ],
  "visible_text": [],
  "visual_evidence": [],
  "water_visual_evidence":   ["visible_water", "filled_container"],
  "study_visual_evidence":   [],
  "exercise_visual_evidence": [],
  "_raw_text": "a clear glass of water",
  "_engine": "smolvlm500m-onnx-a", "_latency_ms": 0
}
```
- enum 값은 backend `image_verification_schema` 의 Water/Study/ExerciseVisualEvidence 만 사용.
- **PASS/FAIL/score/decision 필드 없음**(모델은 판정 금지). Rule Engine 이 이 JSON을 받아 판정.

## 10. fallback 정책
우선순위: 온디바이스 우선, 실패/불확실 시에만 서버.
1. **런타임 불가**(`isReady()==false`, 세션 로드 실패, EP 크래시) → 서버 경로로 이미지 전송해 판정.
2. **품질 불가**(preprocess/vision 결과 usable=false) → retake_required 는 Rule Engine 이 결정, 재촬영 유도.
3. **study 불확실**(온디바이스 evidence < 기준, 또는 Rule Engine 결과 retake+study_pattern_missing/uncertain)
   → **서버 Qwen2.5-VL-3B-AWQ fallback**(11절). water/exercise 는 온디바이스로 종결(서버 불필요가 기본).
4. 네트워크 없음 + 온디바이스 실패 → retake_required 반환(가짜 PASS 절대 금지, FP=0 우선).

## 11. Qwen2.5-VL-3B-AWQ (study/server fallback) 과의 관계
- **역할 분담(확정됨)**: 온디바이스 SmolVLM-500M = water/exercise 종결 + study 1차. 서버
  Qwen2.5-VL-3B-AWQ = study 불확실 시 재확인(study accuracy/recall 1.0, FP=0 실측).
- backend 에는 이미 **study fallback 골격이 구현**되어 있음(`image_verification_service._should_study_fallback`
  + `get_study_fallback_analyzer`, provider `qwen_awq`). 온디바이스 앱은 study 불확실 신호를 서버로 넘기고,
  서버가 동일 Rule Engine 으로 재판정. **양 경로 모두 판정 주체는 Rule Engine**(모델 아님).
- 즉 온디바이스화는 이 하이브리드의 "온디바이스측(SmolVLM)"을 Android 로 옮기는 작업이며, 서버 fallback 구조는 그대로.

## 12. 구현 TODO 체크리스트
- [ ] 정밀도 조합 A(q4 decoder+int8 vision+int8 embed)로 자산 세트 구성(모듈당 1개 + tokenizer/config).
- [ ] ONNX Runtime Mobile(arm64) .aar 통합, 3개 InferenceSession 로더 + warmUp().
- [ ] preprocess 이식: preprocessor_config(size/mean/std, SmolVLM 패치 분할) 정확 재현.
- [ ] 토크나이저 이식(BPE, chat_template) + build_prompt(water/exercise/study) 이식.
- [ ] decoder KV-cache 루프(greedy, max_new_tokens 32~48) 구현.
- [ ] **파서(to_vision_analysis) Kotlin 이식** — water FP-safe 규칙(용기명만 금지/empty 명시) 포함, 유닛테스트로 데스크톱 결과와 동치 확인.
- [ ] evidence JSON 직렬화(9절 schema) → 기존 backend/API 계약과 정합.
- [ ] EP 비교(CPU/XNNPACK/NNAPI), 정밀도 조합 A/B/D 벤치(7절 항목).
- [ ] real-only 검수셋(150 candidate 확정본)으로 **FP=0 회귀 확인**(온디바이스 evidence→Rule Engine).
- [ ] fallback 배선(런타임 실패/네트워크 없음/ study 불확실 → 서버) — Flutter/API 변경 없이 앱 내부 로직.
- [ ] 발열/배터리/연속 촬영 안정성 소크 테스트.

## 13. 실패 조건 (하나라도 해당 시 해당 경로 보류/재설계)
- **real-only FP 발생**(부정 이미지가 verified) → 정밀도(특히 vision) 상향(int8→fp16) 또는 파서 강화로 FP=0 복구, 미복구 시 온디바이스 water/exercise 채택 보류.
- **warm inference > 3s**(Z Flip3) → 정밀도 하향(q4f16), max_new_tokens 축소, EP 변경(NNAPI); 그래도 초과 시 study 는 서버 우선.
- **peak memory > 2GB** → embed/vision 더 작은 정밀도, 세션 순차 로드/해제, 조합 B 채택; 초과 지속 시 온디바이스 보류.
- **Android runtime 불안정**(세션 크래시/NNAPI 비호환/디바이스별 편차) → XNNPACK(CPU) 고정 또는 서버 fallback 상시화.
- 공통 원칙: 위 어떤 실패에서도 **가짜 PASS 금지** — 불확실하면 retake_required/서버 fallback 으로 처리(FP=0 최우선).

---
참고: 본 계획은 문서 작업만 수행했고 코드/모델/데이터셋을 변경하지 않았다. 이미지 라벨은 사용자 검수 중이며
이 문서는 라벨을 확정/추정하지 않는다. 실제 온디바이스 수치(7절)는 Z Flip3 계측 후 이 문서에 갱신한다.
