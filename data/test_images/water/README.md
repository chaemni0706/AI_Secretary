# Water Verification Test Set

Qwen2.5-VL-3B 기반 물 인증 파이프라인의 PASS/FAIL 판정을 검증하기 위한 테스트셋이다.

파이프라인:

```
image → Qwen VLM 증거 추출 → normalize_water_output → VisionAnalysis → Rule Engine → PASS/FAIL
```

VLM은 최종 판정을 하지 않고 **시각 증거만** 추출한다. 최종 인증 여부(verified /
retake_required / rejected)는 `backend/services/image_verification_rule_engine.py`가 결정한다.

## 판정 기준 (MVP, 느슨하게)

- **PASS**: 물이 담긴 컵, 물컵을 든 장면, 정수기에서 물을 받는 장면, 물이 든 투명 병
- **FAIL**: 빈 컵, 물이 거의 없어 근거가 부족한 컵, 색 있는 음료(커피 등)
- **BORDERLINE**: 닫힌/불투명 병처럼 물 섭취 근거가 약한 경우 (PASS는 아님 → 실무상 FAIL로 처리, `borderline_cases`에 별도 기록)
- 단순히 "컵이 있다"는 이유만으로 PASS하지 않는다. (`test_container_alone_is_not_pass`)

라벨 매핑: `verified → PASS`, `rejected → FAIL`, `retake_required → FAIL`.

## 디렉터리 구조

```
data/test_images/water/
├── uploaded/            # 실제 제공된 인증사진 8장 (water_test_01.png ~ _08.png)
├── generated/           # 합성 이미지 10장 (generated_water_01_*.png ~ _10_*.png)
├── water_manifest.json  # 18장 매니페스트 (+ vision_analysis 픽스처, borderline_cases)
└── README.md
```

### 매니페스트 필드 (`water_manifest.json` → `images[]`)

| 필드 | 설명 |
|------|------|
| `filename` | 파일명 |
| `image_path` | 저장소 루트 기준 경로 |
| `expected_label` | `PASS` / `FAIL` / `BORDERLINE` |
| `source` | `uploaded` / `generated` |
| `reason` | 판정 근거 설명 |
| `difficulty` | `easy` / `medium` / `hard` |
| `vision_analysis` | GPU 없이 Rule Engine을 검증하기 위한, 사람이 검수한 VisionAnalysis 대체 픽스처 |

최상위 `borderline_cases[]`에 BORDERLINE 이미지가 별도로 기록된다.

## 이미지 생성

`generated/` 10장은 PIL 합성 이미지다. 아래로 생성한다:

```bash
# generated/ 10장만 생성
python scripts/generate_water_test_images.py

# uploaded/ 슬롯 중 비어 있는 곳을 placeholder로도 채움 (실제 사진은 절대 덮어쓰지 않음)
python scripts/generate_water_test_images.py --uploaded-placeholders
```

pytest는 `generated/` 이미지가 없으면 세션 시작 시 위 명령을 **자동 실행**한다
(`tests/test_water_verification_fixtures.py`의 `ensure_images` 픽스처).

### uploaded/ 실제 사진에 대한 주의

`uploaded/`의 8장은 사용자가 제공한 실제 인증사진 자리다.
실제 사진이 없는 슬롯만 `--uploaded-placeholders`가 워터마크가 찍힌 placeholder로 채우며,
**기존 파일은 절대 덮어쓰지 않는다.** 실제 photo가 준비되면 같은 파일명
(`water_test_01.png` ~ `water_test_08.png`)으로 교체하면 매니페스트/테스트가 그대로 동작한다.

## 테스트 실행

```bash
python -m pytest tests/test_water_verification_fixtures.py -v -s
```

검증 항목:

1. 매니페스트 무결성 (18장, 필수 필드, 이미지 존재)
2. 견고한 판정 파서 `water_verdict.normalize_verdict` — `PASS/FAIL`, `true/false`,
   `물 있음/물 없음`, `인증 가능/인증 불가`, dict/bool/VisionAnalysis 등 모든 형태를 표준 라벨로 정규화
3. 각 이미지의 PASS/FAIL 판정이 기대 라벨과 일치 (`filename, predicted_label, expected_label,
   confidence, reason`을 출력하고 `outputs/water_verdict_report.csv`로 저장)
4. 용기만 있고 물 근거가 없으면 PASS 아님
5. `normalize_water_output` (Qwen 증거 → VisionAnalysis) 정규화 검증
6. BORDERLINE 케이스 분리 기록

## 실제 Qwen2.5-VL-3B 배치 실행 (GPU 필요)

`torch` / `transformers` / `qwen_vl_utils`가 설치된 GPU 환경에서 18장 전체를 실제 모델로 평가한다.
모델은 배치 시작 시 한 번만 로드하고, 이미지마다 `torch.inference_mode()` + `torch.cuda.empty_cache()`로 처리한다.

```bash
# 빠른 점검(처음 3장)
python local_eval/qwen_vlm_eval/scripts/run_qwen_water_batch.py --limit 3

# 전체 18장
python local_eval/qwen_vlm_eval/scripts/run_qwen_water_batch.py

# 모델 지정 (기본값 Qwen/Qwen2.5-VL-3B-Instruct)
python local_eval/qwen_vlm_eval/scripts/run_qwen_water_batch.py --model Qwen/Qwen2.5-VL-3B-Instruct
```

산출물 (`local_eval/qwen_vlm_eval/outputs/water_batch/`):

- `{stem}_raw.json` — 파싱된 Qwen raw output (파싱 성공 시)
- `{stem}_raw_text.txt` — Qwen 원본 텍스트 (항상 저장; 파싱 실패 진단용)
- `{stem}_normalized.json` — VisionAnalysis 호환 정규화 결과
- `{stem}_result.json` — 이미지별 최종 판정 (filename, predicted_label, engine_result, score,
  mandatory_passed, ok, water_visual_evidence, objects, rule_evidence, *_output_path, error)
- `water_qwen_batch_report.csv` — 컬럼: `filename, source, expected_label, predicted_label,
  engine_result, score, mandatory_passed, ok, water_visual_evidence, objects,
  raw_output_path, normalized_output_path, result_output_path, error`

정규화(`normalize_water_output.py`)의 false positive/negative 방어:
- Qwen이 evidence를 dict(name/description)로 내도 흡수한다.
- 부정문("no other beverages", "not opaque", "does not appear to be water" 등)은 negative 근거로 매핑하지 않는다.
- `empty_container`는 명시적 빈/소량 표현("empty glass", "small amount", "few drops" 등)에서만 매핑한다.
- 강한 긍정(glass/cup + 투명 액체 + filled + hard negative 없음)이면 모순 근거를 제거한다.
- Qwen raw의 선택적 `water_amount`(none|tiny|partial|filled|uncertain): none/tiny/uncertain은 PASS 금지, partial/filled는 PASS 가능.
- 명시적 빈/반사/유리표면 신호("empty glass", "no water", "no liquid", "reflection", "glass surface", "clear glass only")는 water_amount와 무관하게 항상 empty_container(FAIL) 처리한다. (반사·광택을 물로 오인하는 false positive 방지)
- 여러 개의 컵/유리컵("two glasses", "glasses on a tray")은 단일 섭취 인증 불가로 보고 filled_container를 제거해 PASS를 막는다(→ BORDERLINE).
- **filled_container는 강한 fill 단서에서만 부여**한다: "glass/cup of water", "filled with water", "being filled with water", "clear liquid in glass", "floating in", "meaningful amount", "water line", "half full", water_stream, `water_amount="filled"`. "transparent glass containing clear liquid"·bare "clear liquid"·`water_amount="partial"` 단독으로는 부여하지 않는다(반사/투명 유리 false positive 방지).
- **가정/조건문**("would indicate", "could potentially", "if the glass were opaque", "may appear empty due to reflections")은 실제 관측이 아니므로 negative/empty 근거로 매핑하지 않는다.
- 정수기/물 받는 장면(dispenser/purifier + water_stream/receiving/being filled + cup/glass)에서는 opaque_closed_container 환각을 제거해 PASS를 허용한다(단, 실제 empty/색음료가 있으면 유지).

배치의 `predicted_label`은 `verified→PASS`, `rejected→FAIL`, `retake_required→BORDERLINE_CASE`이며,
`ok`는 PASS 게이팅 일치(기대/예측이 둘 다 PASS이거나 둘 다 non-PASS)로 계산한다.

## 관련 코드

- 배치 실행: `local_eval/qwen_vlm_eval/scripts/run_qwen_water_batch.py`
- 단건 Qwen 추론: `local_eval/qwen_vlm_eval/scripts/run_qwen_single.py --verification-type water`
- 판정 파서: `local_eval/qwen_vlm_eval/scripts/water_verdict.py`
- 정규화: `local_eval/qwen_vlm_eval/scripts/normalize_water_output.py`
- Rule Engine: `backend/services/image_verification_rule_engine.py`
- Water 규칙: `backend/rules/image_verification/water.yaml`
- 픽스처 리포트: `local_eval/qwen_vlm_eval/outputs/water_verdict_report.csv`
