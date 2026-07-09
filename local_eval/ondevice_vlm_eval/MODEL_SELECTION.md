# 온디바이스 VLM 모델 선택 비교

목표 기기: **Samsung Galaxy Z Flip3 5G** (Snapdragon 888, 8GB RAM).
용도: water / exercise / study 이미지 인증. 모델은 **시각 evidence 만 추출**하고,
최종 verified/rejected/retake_required 판정은 **Rule Engine** 이 수행한다.

## 선택 기준 (우선순위)

1. **인증 안전성 = False Positive 최소화 (FP=0 이 최우선)**
2. water/exercise/study 전반 정확도
3. 추론 속도(latency)
4. 모델 크기
5. Z Flip3 온디바이스 실행 가능성
6. 통합/구현 난이도

> FP(가짜 인증 통과)는 인증 신뢰를 직접 해치므로 다른 지표보다 우선한다.
> study recall 이 올라가더라도 FP 가 생기면 채택 근거가 약해진다.

## 결과 비교표

| Model | Water Acc | Water FP | Exercise Acc | Exercise FP | Study Acc | Study FP | Study Recall | Avg Latency | Size | Integration | Current Judgment |
| ----- | --------- | -------- | ------------ | ----------- | --------- | -------- | ------------ | ----------- | ---- | ----------- | ---------------- |
| **SmolVLM-500M** | 0.944 | **0** | 0.917 | **0** | 0.500 | **0** | 0.286 | ~749–852ms | ~600MB | 낮음(쉬움) | water/exercise 유력, study 부족 |
| **MobileVLM-V2-1.7B** | 0.833 | **3** | 1.000 | **0** | 0.500 | **0** | 0.286 | ~767–1155ms | ~1100MB | 높음(어려움) | exercise 우수하나 water FP·통합난이도로 우선 후보 아님 |
| **SmolVLM2-2.2B** | **1.000** | **0** | 0.833 | **1** | 0.500 | **0** | 0.286 | ~663–696ms | ~4400MB | 낮음(500M 재사용) | water 최우수·속도 최상이나 exercise FP 1·study 미개선·크기 큼 → 1순위 아님 |
| **Qwen2-VL-2B-AWQ** | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | ~1800MB(추정) | 낮음(500M 재사용) | 500M↔3B 절충 후보. study 개선+온디바이스 가능성 검증 중 |
| **Qwen2.5-VL-3B-AWQ** | 0.944 | **0** | **1.000** | **0** | **1.000** | **0** | **1.000** | ~607–1244ms | ~2300MB | 낮음(500M 재사용) | 성능 최우수·study 병목 해결. 크기·AWQ 의존성·온디바이스 부담 → study fallback/성능 anchor |
| **MiniCPM-V-4.6-GGUF** | 0.611 | **4** | 0.500 | **5** | 0.500 | 0 | 0.286 | ~3.5s/img(GPU) | ~1.2GB | 중간(llama.cpp) | ❌ **탈락**: runtime PASS 이나 real validation FP=9(물 환각+프롬프트 복창) |
| **MiniCPM-V-2.0** | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | ~1900MB(int4 추정) | 중간(custom chat API) | GGUF vision(clip build_minicpmv) abort → runtime 탈락 |
| **MiniCPM-V-2.6** | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | ~6000MB(int4 추정) | 중간(custom chat API) | 8B 고정밀 레퍼런스. 크기 커 Z Flip3 부담 → 정확도 상한/서버 후보 |
| **MagicVL-2B** | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | unknown | UNVERIFIED | id/API/라이선스 미확정 — 존재확인 후 평가 |

> SmolVLM2-2.2B 는 프롬프트/파서/어댑터를 SmolVLM-500M 과 동일하게 재사용하고 로딩 경로/dtype 만
> 분리했다(어댑터 key `smolvlm2_2b`). 실행 절차는 [SMOLVLM2_RUNBOOK.md](SMOLVLM2_RUNBOOK.md) 참고.

## 세부 지표

### SmolVLM-500M (실제 no-simulate 평가 완료)

| type | accuracy | FP | recall | avg latency |
| --- | --- | --- | --- | --- |
| water | 0.944 | 0 | 0.909 | 749ms |
| exercise | 0.917 | 0 | 0.833 | 827ms |
| study | 0.500 | 0 | 0.286 | 852ms |

- 모든 타입 FP=0. water/exercise 유력. study recall 낮음.
- 크기/속도/통합 난이도 모두 유리 → Z Flip3 후보로 현실적.

### MobileVLM-V2-1.7B (실제 infer-dump + from-dump 평가 완료)

| type | accuracy | TP/TN/FP/FN | FP | recall | avg latency |
| --- | --- | --- | --- | --- | --- |
| water | 0.833 | 11/4/3/0 | 3 | 1.000 | 1111ms |
| exercise | 1.000 | 6/6/0/0 | 0 | 1.000 | 1155ms |
| study | 0.500 | 2/3/0/5 | 0 | 0.286 | 767ms |
| ALL | 0.800 | 19/13/3/5 | 3 | 0.792 | 1038ms |

- exercise 우수. 그러나 water 에서 **FP 3건**(빈 컵 물 환각) 발생.
- study 는 SmolVLM-500M 대비 개선 없음.
- custom repo(mtgv), pydantic v1/v2 분리, 2-stage dump 필요(통합 난이도 높음).
- 현재 기준으로 SmolVLM-500M 보다 우선 후보 아님.

### SmolVLM2-2.2B-Instruct (실제 no-simulate 평가 완료)

| type | accuracy | TP/TN/FP/FN | FP | recall | avg latency |
| --- | --- | --- | --- | --- | --- |
| water | 1.000 | 11/7/0/0 | 0 | 1.000 | 663ms |
| exercise | 0.833 | 5/5/1/1 | 1 | 0.833 | 668ms |
| study | 0.500 | 2/3/0/5 | 0 | 0.286 | 696ms |
| ALL | 0.825 | 18/15/1/6 | 1 | 0.750 | ~676ms |

- **water 최우수**(accuracy 1.000, FP=0, recall 1.000) + 후보 중 latency 최저(~663–696ms).
- **exercise 에서 FP 1건** 발생 → 인증 안전성(FP=0) 위반.
- **study 는 SmolVLM-500M/MobileVLM 대비 개선 없음**(accuracy 0.500, recall 0.286).
- 모델 크기 ~4400MB 로 커서 Z Flip3(8GB) 온디바이스 부담(양자화 전제).
- 목적이었던 study recall 개선을 달성하지 못했고 exercise FP 까지 생겨 **1순위 아님**.

### MiniCPM-V 2.0 (2.8B 소형 — 미측정, 실험 우선순위 1순위)

- `openbmb/MiniCPM-V-2` (2.8B = MiniCPM-2.4B + SigLIP-400M), **GGUF int4 공식 `openbmb/MiniCPM-V-2-gguf`**.
- 온디바이스: **llama.cpp GGUF int4 경로가 명확**(~1.9GB 추정) → 2.6(8B)보다 Z Flip3 현실성 높음. ONNX 난이도 높음(VERIFY).
- 목적: SmolVLM study 약점 보완(OCR/문서 인식 강함) + 온디바이스 가능성. 어댑터 key `minicpm_v2`(2.0 chat API).
- 실행 절차: [MINICPM_V2_RUNBOOK.md](MINICPM_V2_RUNBOOK.md). 측정 후 위 표/세부 지표를 채운다.

### MiniCPM-V 2.6 (8B 고정밀 레퍼런스 — 미측정)

- `openbmb/MiniCPM-V-2_6` (int4 `-int4`, GGUF `-gguf`). ~8B(Qwen2-7B+SigLIP), custom `model.chat()` API(trust_remote_code).
- 온디바이스: llama.cpp GGUF int4 공식 지원(경로 있음)이나 8B라 Z Flip3(8GB) 부담. ONNX export 난이도 높음.
- 위치: 정확도 상한선/서버 후보. SmolVLM 대체보다는 study 상한 확인용. 실행 절차 [MINICPM_MAGICVL_RUNBOOK.md](MINICPM_MAGICVL_RUNBOOK.md).

### MagicVL-2B (UNVERIFIED — 미측정)

- **정직성 고지**: 정확한 공식 HF id/추론 API/라이선스/양자화 checkpoint 존재를 아직 확인하지 못함.
- 어댑터 `magicvl_2b` 는 trust_remote_code + MiniCPM류 `.chat()` 을 가정한 **스캐폴드**. 런북 §0 존재확인 후
  정확한 id/API 로 `magicvl_adapter._infer`·yaml 을 갱신한 뒤에만 벤치마크 유효.

### Qwen2-VL-2B-AWQ (2B 절충 후보 — 미측정)

- 목적: SmolVLM-500M(600MB, study 약함)과 Qwen2.5-VL-3B-AWQ(2.3GB, study 최고) 사이에서
  **"정확도 대비 온디바이스 가능성"** 절충점을 찾는다. 2B AWQ(int4) ~1.8GB 로 3B 보다 작아
  Z Flip3 온디바이스 가능성이 더 높고, SmolVLM 대비 study 개선을 기대.
- 어댑터 key `qwen2vl_2b` (모델 클래스만 `Qwen2VLForConditionalGeneration`, 로딩/추론/프롬프트/파서는 3B와 동일 재사용).
- 실행 절차: [QWEN2VL_2B_RUNBOOK.md](QWEN2VL_2B_RUNBOOK.md). 측정 후 위 표/세부 지표를 채운다.
- 온디바이스 메모: ONNX export 난이도 높음(동적 비전 토큰), MLC/llama.cpp int4 변환은 커뮤니티 지원 존재(실측 필요).

### Qwen2.5-VL-3B-AWQ (실제 no-simulate 평가 완료 — anchor/서버 fallback)

| type | accuracy | TP/TN/FP/FN | FP | recall | avg latency |
| --- | --- | --- | --- | --- | --- |
| water | 0.944 | 10/7/0/1 | 0 | 0.909 | 607ms |
| exercise | 1.000 | 6/6/0/0 | 0 | 1.000 | 818ms |
| study | 1.000 | 7/3/0/0 | 0 | 1.000 | 1244ms |
| ALL | 0.975 | 23/16/0/1 | 0 | 0.958 | ~890ms |

- **성능 최우수**: 전 타입 **FP=0** + accuracy 0.944~1.000 + ALL recall 0.958.
- **study 병목 해결**: 소형 3종이 모두 study recall 0.286 에 막혔는데 Qwen 은 **study accuracy 1.000 / recall 1.000**.
  → study 한계의 원인은 파서/데이터가 아니라 **모델 용량(시각·텍스트 이해력)** 이었음이 확인됨.
- 프롬프트/파서는 SmolVLM 과 동일 재사용(어댑터 key `qwen_awq`), 추론은 기존 Qwen batch runner의
  `Qwen2_5_VLForConditionalGeneration` + `qwen_vl_utils.process_vision_info` 흐름 미러링.
  (AWQ 는 fp16 고정 + 입력 float 텐서 fp16 캐스팅으로 Triton kernel dtype 충돌 해결.)
- **다만 온디바이스 1순위는 아님**: 모델 크기 ~2300MB, AWQ/AutoAWQ 의존성, study latency ~1244ms 로
  Z Flip3 온디바이스 부담. → **study fallback / 성능 anchor** 로 정리.
- 실행 절차는 [QWEN_AWQ_RUNBOOK.md](QWEN_AWQ_RUNBOOK.md) 참고.

## 판단 기준 (SmolVLM2-2.2B 채택 여부)

```text
1. FP=0 유지 여부                (최우선 — study/water/exercise 모두)
2. study recall 개선 여부         (> 0.286, 목표 ≥ 0.6)
3. water/exercise 성능 유지 여부   (기존 대비 하락 없어야 함)
4. latency                        (온디바이스 실사용 가능 범위)
5. model size                     (~4.4GB → Z Flip3 8GB RAM 부담, 양자화 전제)
6. integration difficulty         (500M 어댑터 재사용 → 낮음)
7. Z Flip3 feasibility            (fp16 데스크톱 우선, ONNX/MLC int8/int4 후속)
```

### 채택 시나리오

- **SmolVLM2-2.2B 가 FP=0 유지 + study recall 개선**: study 담당 후보로 유력.
  단 크기(~4.4GB)로 Z Flip3 는 양자화(int8/int4) 필요 → 온디바이스 feasibility 재평가.
- **개선되나 크기/속도가 부담**: water/exercise=SmolVLM-500M, study=상위 모델의 **하이브리드** 검토.
- **개선 없음 / FP 발생**: 미채택 기록. study 는 프롬프트/파서 튜닝(`--reparse`) 또는
  Qwen2.5-VL-3B-AWQ anchor 로 상한 확인 후 재판단.

## 최종 결론 (현재 선정 상태 — 2026-07-08 갱신)

역할 분담으로 확정한다.

- **온디바이스 1차 후보(유지): SmolVLM-500M** — 전 타입 FP=0 + 최소 크기(~600MB) + 통합 난이도 최저.
  water 0.944 / exercise 0.917 로 정확도 충분, latency 도 온디바이스 실사용 범위. study 만 약함.
- **study fallback / 성능 anchor(유지): Qwen2.5-VL-3B-AWQ** — 전 타입 FP=0, study accuracy/recall 1.000 으로
  소형 모델 study 병목을 해결. 다만 크기 ~2300MB + AWQ 의존성 + study latency ~1244ms 로 온디바이스 1순위는 아님.
  → study 는 **서버 fallback** 또는 온디바이스(500M) + 서버(Qwen) **하이브리드** 로 처리.
- **제외(runtime feasible but rejected): MiniCPM-V-4.6-GGUF** — llama.cpp 로 실행은 되고 크기 ~1.2GB(≤3GB)로
  runtime feasibility 는 PASS 였으나, real validation(40장)에서 **FP=9**(물 환각 + exercise 프롬프트 복창)로
  **FP=0 최우선 기준 위반 → 온디바이스 후보 제외.** study 개선도 없음(recall 0.286). MiniCPM-V 계열(2.0 runtime 탈락,
  2.6/4.5 size 탈락 포함) 전부 제외.
- **보류: MobileVLM-V2-1.7B, SmolVLM2-2.2B, Qwen2-VL-2B-AWQ** — 각각 water FP 3 / exercise FP 1 / (FP 이슈)로
  안전성 위반 또는 SmolVLM-500M 대비 종합 우위가 없어 채택하지 않음.

모델별 정리:

| 모델 | 역할 | FP=0 | study recall | 크기 | 통합 | 요약 |
| --- | --- | --- | --- | --- | --- | --- |
| **SmolVLM-500M** | ✅ 온디바이스 1차 | 전타입 0 | 0.286 | ~600MB | 쉬움 | 안전성·크기·통합 우위. study 만 약함 |
| **Qwen2.5-VL-3B-AWQ** | ✅ study fallback/anchor | 전타입 0 | **1.000** | ~2300MB | 쉬움(재사용) | 성능 최우수·study 해결. 크기·의존성으로 온디바이스 1순위 아님 |
| **MiniCPM-V-4.6-GGUF** | ❌ 제외(FP) | water FP4·exercise FP5 | 0.286 | ~1.2GB | 중간(llama.cpp) | runtime PASS·validation FAIL(FP=9: 물 환각+프롬프트 복창) |
| MobileVLM-V2-1.7B | 보류 | water FP 3 | 0.286 | ~1100MB | 어려움 | exercise 우수하나 water FP·custom repo 부담 |
| SmolVLM2-2.2B | 보류 | exercise FP 1 | 0.286 | ~4400MB | 쉬움(재사용) | water 최우수·최속이나 exercise FP·study 미개선·크기 과다 |

- **study 병목의 원인 규명**: 소형 3종(500M/1.7B/2.2B)은 모두 study recall 0.286 이었으나 Qwen(3B)에서
  1.000 으로 해결됨 → 병목은 파서/데이터가 아니라 **모델 용량**. 온디바이스만으로 study 를 올리기는 어렵고,
  study 는 상위 모델(서버) 경유가 현실적.

### 권장 아키텍처

- **water / exercise**: 온디바이스 SmolVLM-500M (FP=0, 저지연, 소형).
- **study**: 온디바이스로 1차 시도 후 불확실하면 **서버 Qwen2.5-VL-3B-AWQ fallback**,
  또는 study 는 처음부터 서버 경유. 최종 verified/rejected/retake_required 판정은 두 경로 모두 **Rule Engine** 이 수행.
- study 온디바이스 자체 성능을 더 끌어올리려면(선택): OCR 텍스트 신호를 evidence 로 추가 +
  study 전용 프롬프트/파서 튜닝을 `infer_dump.py` + `--reparse` 로 재추론 없이 반복.
