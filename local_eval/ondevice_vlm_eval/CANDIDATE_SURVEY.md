# 온디바이스 VLM 추가 후보 조사 (Z Flip3 이미지 인증)

목표: 0.5B~3B, 양자화 checkpoint 존재, Android/edge 배포 가능성, HF/공식 repo 확인 가능한 VLM.
평가 관점: **정확도(특히 FP=0, study semantic) 대비 온디바이스 실행성.**

> ⚠️ 정직성: 이 문서의 HF id 는 에이전트 지식(cutoff 2026-01) 기준이다. **CONFIRM 표시 = 존재 신뢰 높음,
> VERIFY 표시 = 다운로드 전 반드시 HF 에서 확인.** 양자화 checkpoint/Android·MLC·ONNX 지원은 변동이 크므로
> 대부분 VERIFY 로 둔다. 존재를 확신 못 하는 것은 UNVERIFIED 로 표기하고 추측하지 않는다.
>
> 확인 명령:
> ```bash
> python -c "from huggingface_hub import model_info; print(model_info('<id>').id)"
> python -c "from huggingface_hub import list_models; print([m.id for m in list_models(search='<kw>', limit=30)])"
> ```

---

## 후보 상세

### C1. InternVL2.5-2B  ★추천
- 공식 HF id: `OpenGVLab/InternVL2_5-2B` (CONFIRM). 소형: `OpenGVLab/InternVL2_5-1B` (CONFIRM).
- parameter: ~2B (InternViT-300M + internlm2/Qwen2-0.5~1.8B 계열)
- quantized checkpoint: AWQ `OpenGVLab/InternVL2_5-2B-AWQ` (VERIFY — lmdeploy AWQ 배포가 사이즈별로 존재). GGUF (VERIFY)
- 예상 크기: fp16 ~4GB, AWQ int4 ~1.5–2GB
- vision encoder: InternViT-300M-448px
- Android 가능성: lmdeploy(AWQ)는 서버 지향. 온디바이스는 MLC/llama.cpp 변환 필요 (VERIFY)
- ONNX 가능성: 낮음(동적 타일링/비전 토큰) (VERIFY)
- MLC 가능성: internlm 계열은 MLC 사례 있음, InternVL 통합은 VERIFY
- 장점: 소형인데 **문서/OCR/차트 이해 강함 → study semantic 유리**. license MIT(관대).
- 단점: 온디바이스 런타임 경로(MLC/llama.cpp) 미검증, 타일링으로 지연 변동.
- 적합성: **study 약점 보완 1순위 후보.** FP는 실측 필요.

### C2. MiniCPM-V (2.0 / 4.6) — ❌ REJECTED after real validation
> **업데이트(2026-07-08)**: MiniCPM-V 계열은 실험 완료 후 **온디바이스 후보 제외**.
> - **2.0 GGUF**: llama.cpp vision(clip build_minicpmv) **abort → runtime 탈락**.
> - **2.6/4.5 GGUF(8B)**: Q4 ≈ 5.5~6GB → **size 탈락(>4GB)**.
> - **4.6 GGUF(ggml-org, 0.8B, ~1.2GB)**: runtime PASS 였으나 real validation 40장에서 **FP=9**
>   (물 환각 + exercise 프롬프트 복창) → **인증 후보 FAIL**. study 개선 없음(recall 0.286).
> 상세: [MINICPM_FEASIBILITY.md](MINICPM_FEASIBILITY.md), 결과 `results/minicpm_v46_gguf/`.
> (아래 원 조사 내용은 실험 전 기록으로 보존.)

- 공식 HF id: `openbmb/MiniCPM-V-2` (CONFIRM). GGUF: `openbmb/MiniCPM-V-2-gguf` (CONFIRM).
- parameter: ~2.8B (MiniCPM-2.4B + SigLIP-400M) — **2.6(8B)과 다른 소형 variant**
- quantized checkpoint: **GGUF int4 공식 존재(CONFIRM)**, int4 bnb (VERIFY)
- 예상 크기: fp16 ~5.5GB, GGUF int4 ~1.8–2.3GB
- vision encoder: SigLIP-400M
- Android 가능성: **llama.cpp GGUF 경로 있음(CONFIRM 계열 지원)** → 온디바이스 현실성 상대적 높음
- ONNX 가능성: 낮음 (VERIFY)
- MLC 가능성: VERIFY
- 장점: OCR/문서 인식 강함(study 유리), **GGUF int4 공식 → Android(llama.cpp) 경로 가장 명확**.
- 단점: 2.8B로 SmolVLM(600MB)보다 큼, custom chat API, license 등록(상업).
- 적합성: **온디바이스 경로가 가장 검증돼 있어 실험 우선순위 높음.**

### C3. Moondream2 (~1.8B)  ★추천
- 공식 HF id: `vikhyatk/moondream2` (CONFIRM)
- parameter: ~1.8B (SigLIP + Phi-1.5 계열)
- quantized checkpoint: GGUF 배포 존재(CONFIRM 계열), int8 (VERIFY)
- 예상 크기: fp16 ~3.7GB, int4/gguf ~1–1.5GB
- vision encoder: SigLIP
- Android 가능성: **edge 지향 설계**, gguf/llama.cpp 경로 (VERIFY 세부)
- ONNX 가능성: 부분 (VERIFY)
- MLC 가능성: VERIFY
- 장점: 경량·빠름·edge 목적 설계, 라이선스 관대(Apache 계열, VERIFY).
- 단점: 문서/한국어 이해가 대형 대비 약할 수 있음(study 검증 필요).
- 적합성: **크기/속도 절충 후보.** study 성능이 관건.

### C4. LLaVA-OneVision-0.5B (초경량)
- 공식 HF id: `lmms-lab/llava-onevision-qwen2-0.5b-ov` (CONFIRM 계열), `-0.5b-si` (VERIFY)
- parameter: ~0.5B (SigLIP-SO400M + Qwen2-0.5B) — **SmolVLM급 초경량**
- quantized checkpoint: 공식 int4/AWQ 미확인 (VERIFY/UNVERIFIED)
- 예상 크기: fp16 ~1GB, int4 ~0.4–0.6GB
- vision encoder: SigLIP-SO400M
- Android/ONNX/MLC: VERIFY (초경량이라 변환 부담은 작음)
- 장점: SmolVLM과 동급 크기 → 온디바이스 매우 유리, Qwen2-0.5B 기반.
- 단점: 0.5B라 study semantic이 SmolVLM처럼 약할 위험, 양자화 ckpt 공식 미확인.
- 적합성: SmolVLM 대안 비교군(같은 체급). study 개선 보장 없음.

### C5. Apple FastVLM (0.5B/1.5B)
- 공식 repo: `apple/ml-fastvlm`(GitHub, CONFIRM). HF id: `apple/FastVLM-*` (VERIFY — 정확 id 확인)
- parameter: 0.5B / 1.5B / 7B (소형 존재)
- quantized checkpoint: VERIFY (Apple MLX/CoreML 중심)
- 예상 크기: 0.5B fp16 ~1GB
- vision encoder: **FastViTHD (고속 인코더, on-device 목적 설계)**
- Android 가능성: Apple 생태계(CoreML/MLX) 중심 → **Android 경로 VERIFY(불리할 수 있음)**
- ONNX/MLC: VERIFY
- 장점: **비전 인코딩 속도 최적화(on-device 목적)**, 소형 존재.
- 단점: Apple/iOS 편향 → Android(Z Flip3) 런타임 경로 불확실.
- 적합성: 속도는 매력적이나 Android 배포 검증 필요.

### C6. Phi-3.5-Vision (참고, 범위 초과)
- 공식 HF id: `microsoft/Phi-3.5-vision-instruct` (CONFIRM)
- parameter: ~4.2B (**0.5–3B 범위 초과**)
- quantized: GPTQ/AWQ 커뮤니티 (VERIFY), ONNX Runtime GenAI 예제 존재(VERIFY)
- vision encoder: CLIP ViT-L/14-336
- 장점: 문서/차트 강함(study 유리), MS ONNX Runtime 생태계.
- 단점: **4.2B로 범위 초과**, Z Flip3 부담.
- 적합성: 서버 anchor 대안. 온디바이스 1순위 아님.

### C7. PaliGemma-3B (참고)
- 공식 HF id: `google/paligemma-3b-mix-224` (CONFIRM)
- parameter: 3B (SigLIP-So400m + Gemma-2B)
- quantized: 공식 int4/gguf 제한적 (VERIFY)
- 장점: OCR/캡션 강함.
- 단점: **Gemma license 제약**, 온디바이스 양자화/런타임 경로 제한적.
- 적합성: 낮음(license + 변환).

---

## 제외 목록 (사유)

| 모델 | 제외 사유 |
| --- | --- |
| MiniCPM-V 2.6 (8B) | 너무 큼(8B) — Z Flip3 부적합 |
| MiniCPM-V 2.0 (2.8B) | 실험됨 → llama.cpp vision abort(runtime 탈락) |
| MiniCPM-V-4.6-GGUF (0.8B) | 실험됨 → runtime PASS 이나 real validation FP=9(물 환각+프롬프트 복창) 탈락 |
| Phi-3 / Phi-3.5-Vision (~4.2B) | 범위(0.5–3B) 초과, 온디바이스 부담 — 서버 참고만 |
| Qwen2-VL-2B-AWQ | 이미 실험: **FP=3** → 인증 서비스(FP=0) 기준 부적합 |
| MobileVLM-V2 계열 | 이미 실험: water FP + 통합 난이도 높음(재평가 제외) |
| MagicVL | HF 공개 checkpoint 확인 실패(UNVERIFIED) |
| InternVL2/2.5-8B·26B, LLaVA-1.5/1.6-7B+, CogVLM, Yi-VL | 너무 큼(≥7B) |
| GPT-4V/Gemini/Claude 등 API VLM | 온디바이스 불가(네트워크 의존) |
| PaliGemma-3B | Gemma license 제약 + 온디바이스 변환 경로 제한 → 성능 대비 의미 낮음 |

---

> **진행 상태(2026-07-08)**: MiniCPM-V 계열은 실험 완료 후 전부 제외(위 C2). 아래 TOP3/우선순위는
> MiniCPM 제거 후 갱신본이다.

## A. 추가 실험 가치 높은 모델 TOP3 (MiniCPM 제외 후)
1. **InternVL2.5-2B** (`OpenGVLab/InternVL2_5-2B`) — 소형인데 문서/OCR 강함 → **study 약점 직접 보완**, MIT license. (AWQ/온디바이스 경로 VERIFY)
2. **Moondream2** (`vikhyatk/moondream2`, ~1.8B) — edge 목적 설계, 경량/고속, 라이선스 관대(VERIFY).
3. **LLaVA-OneVision-0.5B** (`lmms-lab/llava-onevision-qwen2-0.5b-ov`) — SmolVLM 동급 초경량 비교군.
- ~~MiniCPM-V 2.0/4.6~~ — 실험 후 제외(runtime abort / FP=9).

## B. 실험 우선순위 (갱신)
1) **InternVL2.5-2B** — study semantic 상한 기대치 최고(소형 중), FP=0 유지 확인이 관건.
2) **Moondream2** — 크기/속도 최적, study 성능이 충분한지 확인.
3) (초경량 비교군) **LLaVA-OneVision-0.5B** — SmolVLM 동급 체급 대안.
- 공통 채택 기준: **FP=0 유지 + study recall 개선 + Z Flip3 실행성**. MiniCPM 사례에서 보듯
  "실행 가능(feasible)"과 "인증 가능(FP=0)"은 별개이므로, 반드시 real validation(FP) 로 검증한다.
- **교훈**: 소형 VLM 은 프롬프트의 옵션 나열을 복창(parroting)하거나 없는 물을 환각하는 경향 → 프롬프트에
  선택지 나열을 피하고, real validation 으로 FP 를 먼저 본다.

## C. SmolVLM-500M 개선 방향 (모두 온디바이스 가능해야 함)
1. **Prompt 개선**: 부정 토큰 주입 금지(과거 'empty' parroting 교훈), 타입별 evidence-중심 서술 프롬프트 유지. 효과 상한 작음(모델 용량 한계).
2. **Parser/evidence 개선**: study 문구→enum 매핑 확장(교재 페이지/워크시트/필기), 복합 evidence 강화. **비용 0, 즉시 가능**하나 모델이 안 뽑으면 한계.
3. **OCR 추가 (권장, 최고 레버리지)**: study 는 텍스트 중심 → **Android 온디바이스 OCR**로 텍스트 신호 추출.
   - **ML Kit Text Recognition v2**(Google, 완전 on-device, 무료, 한국어 지원) 또는 PaddleOCR-mobile / Tesseract.
   - OCR 텍스트에서 "문제/정답/단원/필기/교재" 등 키워드 → study evidence 보강. VLM 실패해도 텍스트로 회수.
4. **Lightweight classifier 추가**: **TFLite 양자화 분류기**(MobileNetV3-small/EfficientNet-lite, ~5–10MB, NNAPI/GPU delegate)로
   (a) study vs non-study, (b) empty vs filled container 이진 판별을 보조 evidence로.
   - 소량 데이터로 파인튜닝 가능, Z Flip3에서 수 ms. FP 제어에 유리(빈 컵 판별 등).
   - 단, 학습 데이터/유지보수 비용 발생.

> 보조 모듈 온디바이스 적합성: ML Kit OCR = Android 네이티브 on-device(적합), TFLite 분류기 = NNAPI on-device(적합).
> 둘 다 네트워크 불필요. VLM(evidence) + OCR(text) + classifier(보조)를 **Rule Engine이 통합 판정**(모델은 판정 안 함) 원칙 유지.

## D. 최종 예상 아키텍처 3개 제안

**아키텍처 1 — SmolVLM-500M + 온디바이스 OCR (완전 on-device, 권장 1순위)**
```
Camera → SmolVLM-500M (objects/scene evidence)
       → ML Kit OCR (on-device text) → study 키워드 evidence
       → [merge] → Rule Engine → verified/rejected/retake
```
- 장점: 완전 오프라인, 경량(600MB+OCR 네이티브), **study 약점을 텍스트로 저비용 보완**, FP0 유지 용이.
- 단점: OCR이 텍스트 없는 study(강의 영상 등)엔 무효 → 그 경우 VLM/분류기 의존.

**아키텍처 2 — SmolVLM-500M + OCR + TFLite 보조 분류기 (완전 on-device, 정밀)**
```
Camera → SmolVLM(evidence) + OCR(text) + TFLite classifier(study?/filled?)
       → [merge weighted evidence] → Rule Engine
```
- 장점: 완전 온디바이스로 정확도/‑FP 동시 개선(빈 용기·study 이진판별 보조), Z Flip3 실행 여유.
- 단점: 분류기 학습/데이터/유지보수 비용, 파이프라인 복잡도↑.

**아키텍처 3 — 소형 VLM 업그레이드 + 서버 fallback (하이브리드, 정확도 최우선)**
```
Camera → 온디바이스 소형 VLM(SmolVLM 또는 InternVL2.5-2B/MiniCPM-V2 int4)
       → Rule Engine
       → (study 불확실 시) 서버 Qwen2.5-VL-3B-AWQ fallback → Rule Engine 재판정
```
- 장점: study 정확도 최고(서버 3B), 온디바이스 1차로 대부분 처리. **현 backend에 study fallback 이미 구현됨.**
- 단점: study fallback 시 네트워크 필요, 서버 비용. 온디바이스 VLM을 2B급으로 올리면 크기↑(int4 변환 검증 필요).

### 종합 권고
- **즉시(무모델추가)**: 아키텍처 1 방향 — SmolVLM 유지 + ML Kit OCR 로 study 보강(FP0 유지, 완전 on-device). 가장 빠른 개선.
- **병행 실험**: TOP3(MiniCPM-V2 → InternVL2.5-2B → Moondream2)를 `run_ondevice_eval.py` 로 벤치마크해 "FP0 + study recall 개선 + Z Flip3 int4 실행성"을 만족하는 모델이 나오면 아키텍처 3의 온디바이스 VLM 교체 검토.
- **정확도 최우선 서비스**면: 아키텍처 3(온디바이스 1차 + 서버 3B fallback) — 이미 backend에 study fallback 골격 존재.
