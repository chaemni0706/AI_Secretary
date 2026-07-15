# real_validation_dataset

실제 사용 환경의 **실패 케이스 수집**을 위한 water/exercise/study 이미지 검증셋.
학습(fine-tuning)이 아니라, 현재 Local VLM 파이프라인의 실패를 찾아 **Rule Engine 보강 근거**를 확보하는 것이 목적.

- 모델은 PASS/FAIL 을 결정하지 않는다(시각 evidence 만 추출).
- 최종 verified/rejected/retake_required 는 항상 **Rule Engine** 이 결정한다.
- **FP(부정 케이스인데 verified) 최소화가 최우선.** 다른 음료가 물로, 비운동이 운동으로 통과되면 안 된다.

## 구조

```
real_validation_dataset/
├── images/
│   ├── water/{pass,fail}/
│   ├── exercise/{pass,fail}/
│   └── study/{pass,fail}/
├── annotations/validation_manifest.json   # 모든 이미지 annotation (아래 스키마)
├── build_validation_dataset.py            # 이미지 배치 + manifest 생성 (GPU 불필요)
├── evaluate_validation_dataset.py         # 배치 평가기 (--simulate / 실제 VLM)
├── results/{simulate,local_vlm}/          # 평가 산출물 (per_image.csv / metrics_summary.json / failure_cases.json)
└── README.md
```

> `pass/` = ground_truth PASS, `fail/` = FAIL 또는 BORDERLINE. 실제 ground_truth 값은 manifest 에 보존된다.

## 현재 구성 (50장)

| type | 총 | PASS | FAIL | BORDERLINE |
| --- | --- | --- | --- | --- |
| water | 20 | 11 | 8 | 1 |
| exercise | 15 | 8 | 6 | 1 |
| study | 15 | 10 | 5 | 0 |

- **real (40장)**: 기존 검증 이미지(data/test_images/water·exercise, study_verification_fixture_pack)에서 수집.
- **synthetic (10장)**: 부족 카테고리 보충용 placeholder(파일명 `*_synth_*`). **실제 촬영본으로 교체/증강 권장.**

## annotation 스키마 (validation_manifest.json 의 각 항목)

```json
{
  "image": "water/pass/water_real_01.png",
  "verification_type": "water",
  "ground_truth": "PASS",
  "expected_evidence": ["visible_water", "filled_container"],
  "description": "손에 든 투명 컵에 물",
  "exercise_activity_type": null,
  "source": "real",
  "difficulty": "easy",
  "reference_vision_analysis": { "...VisionAnalysis 호환 dict..." }
}
```

- `ground_truth`: `PASS` | `FAIL` | `BORDERLINE`
- `expected_evidence`: 그 이미지에서 나와야 하는 VLM evidence 토큰(해당 타입 enum)
- `exercise_activity_type`: exercise 만 (`gym`/`running`/`home_workout` 등)
- `reference_vision_analysis`: **--simulate 평가**(모델 없이 Rule Engine 검증)에 쓰는 참조 분석

## 이미지 추가/교체 방법

1. `images/<type>/<pass|fail>/` 에 실제 이미지를 넣는다(jpg/png).
2. `annotations/validation_manifest.json` 에 위 스키마로 항목을 추가한다.
   - `reference_vision_analysis` 는 --simulate 검증용이므로, 손으로 채우거나 비워도(실제 VLM 평가에는 무관) 된다.
3. 또는 원본 소스를 늘린 뒤 `build_validation_dataset.py` 를 다시 실행해 재생성한다.

## 평가 실행

### A) 즉시 확인 — 모델 없이 (데이터셋 ↔ Rule Engine 정합성)

```bash
python local_eval/real_validation_dataset/evaluate_validation_dataset.py --simulate
```

`reference_vision_analysis` → Rule Engine 만 실행. 데이터셋 라벨과 Rule Engine 판정이 일치하는지 확인.
(참조 분석이 ground_truth 를 인코딩하므로 정상 데이터셋에서는 FP/FN=0 이 기대값.)

### B) 실제 Local VLM 평가 — 외부 터미널/tmux (대형 모델)

> ⚠️ VSCode 안에서 실행하지 말 것(모델 로딩 부담). torch/모델 있는 `qwen-vlm` env 에서 실행.

```bash
tmux new -s validation_eval
conda activate qwen-vlm
cd ~/AI_Secretary_FeatureJW_Qwen

IMAGE_VERIFICATION_USE_OPENAI=false \
IMAGE_VERIFICATION_VLM_PROVIDER=smolvlm \
IMAGE_VERIFICATION_STUDY_FALLBACK=qwen_awq \
  python local_eval/real_validation_dataset/evaluate_validation_dataset.py

# 타입 한정 / 개수 제한도 가능
python local_eval/real_validation_dataset/evaluate_validation_dataset.py --types study --limit 5
```

이 경로는 backend 의 실제 파이프라인(`verify_image_upload`)을 그대로 호출한다 →
SmolVLM 1차 + study fallback(Qwen) + Rule Engine 최종 판정까지 프로덕션과 동일.

## Z Flip3 실촬영 이미지 편입 (`import_real_zflip_images.py`)

`~/real_zflip_images/*.jpg`(34장)를 검증셋으로 편입한다. 파일명이 타임스탬프뿐이라
**verification_type/ground_truth 를 자동 추정하지 않고**, 사용자가 확인·입력하도록 TODO + 분류 도구를 제공한다.

### 1) import (이미지 복사 + TODO 엔트리 + 분류 도구 생성)

```bash
python local_eval/real_validation_dataset/import_real_zflip_images.py
```

- 이미지 → `images/real_zflip/` 로 복사(분류 전 임시 보관, 기존 type 폴더 오염 방지)
- `annotations/validation_manifest.json` 에 34개 엔트리 추가(기존 50개 보존/병합), `source="real_zflip"`,
  `verification_type="TODO"`, `ground_truth="TODO"`
- `annotations/real_zflip_annotation.csv` (사용자가 채울 분류표) 생성
- `real_zflip_preview.html` (썸네일 미리보기) 생성
- 재실행 idempotent(중복 추가 없음). `verification_type=TODO` 엔트리는 evaluate 의 `--types` 필터에서 자동 제외.

### 2) 분류 (사용자 작업)

`real_zflip_preview.html` 을 브라우저로 열어 이미지를 보고,
`annotations/real_zflip_annotation.csv` 의 컬럼을 채운다:

| 컬럼 | 값 |
| --- | --- |
| verification_type | `water` / `exercise` / `study` |
| ground_truth | `PASS` / `FAIL` (필요 시 `BORDERLINE`) |
| exercise_activity_type | exercise 일 때 `gym`/`running`/`home_workout` 등 |
| expected_evidence | `;` 로 구분(선택) |
| description | 메모(선택) |

### 3) apply (CSV → 편입)

```bash
python local_eval/real_validation_dataset/import_real_zflip_images.py \
    --apply-csv local_eval/real_validation_dataset/annotations/real_zflip_annotation.csv
```

- 분류된 이미지를 `images/<type>/` 로 이동하고 manifest 엔트리 갱신(`annotated=true`).
- 미분류(빈칸) 행은 건너뛴다 → 부분 분류 후 여러 번 나눠 실행 가능.
- 편입 후에는 `evaluate_validation_dataset.py`(실제 VLM 모드)로 바로 평가된다.

> real_zflip 엔트리는 `reference_vision_analysis` 가 없으므로 `--simulate` 에서는 제외되고,
> **실제 VLM 모드**에서만 평가된다(실촬영 실패 케이스 수집이 목적).

## MiniCPM-V-4.6-GGUF 평가 결과 (2026-07-08)

평가기: [evaluate_minicpm_v46_gguf.py](evaluate_minicpm_v46_gguf.py) (llama.cpp llama-mtmd-cli → 파서 → Rule Engine).
대상: source=real 40장(synthetic/TODO 제외). 결과 파일: **`results/minicpm_v46_gguf/`**
(results.jsonl, raw_outputs.jsonl, per_image.csv, metrics_summary.json, false_positive_cases.json,
false_negative_cases.json, latency_summary.json, parse_failures.json). smoke: `results/minicpm_v46_gguf_smoke/`.

| type | n | acc | precision | recall | F1 | **FP** | FN |
| --- | --- | --- | --- | --- | --- | --- | --- |
| water | 18 | 0.611 | 0.667 | 0.727 | 0.696 | **4** | 3 |
| exercise | 12 | 0.500 | 0.500 | 0.833 | 0.625 | **5** | 1 |
| study | 10 | 0.500 | 1.000 | 0.286 | 0.444 | **0** | 5 |
| **ALL** | 40 | 0.550 | 0.625 | 0.625 | 0.625 | **9** | 9 |

latency ≈ 3.5s/img (A5000 GPU, 이미지당 모델 재로딩). parse_failures=0.

**판정: 인증 후보 FAIL(FP=9).** 원인: (1) 빈 용기 물 환각, (2) exercise 프롬프트 복창(parroting),
(3) study 개선 없음(recall 0.286). runtime feasibility 는 PASS 였으나 FP=0 기준 위반으로 온디바이스 후보 제외.
→ **SmolVLM-500M(온디바이스 1차) + Qwen2.5-VL-3B-AWQ(study/server fallback) 유지.**
상세: [../ondevice_vlm_eval/MINICPM_FEASIBILITY.md](../ondevice_vlm_eval/MINICPM_FEASIBILITY.md),
[../ondevice_vlm_eval/MODEL_SELECTION.md](../ondevice_vlm_eval/MODEL_SELECTION.md).

## 결과 해석 (results/<mode>/)

- `metrics_summary.json`: 타입별/전체 confusion(PASS=positive) — **fp 를 먼저 본다**.
- `failure_cases.json`: `false_positives`(최우선) + `all_failures`(오분류/에러).
- `per_image.csv`: 이미지별 gt/pred/score/mandatory/evidence/rule_evidence.

관점:
1. **FP=0 유지**되는가(부정 케이스가 verified 되지 않는가) — 최우선.
2. FN(진짜 PASS 인데 놓침)은 어디서 나오는가 — evidence 매핑/임계값 보강 근거.
3. study 실패 패턴 — SmolVLM 약점 확인 및 Qwen fallback 효과 검증.
4. 반복되는 rule_evidence 코드(예: `*_pattern_missing`)는 Rule Engine 매핑 누락 후보.
```
