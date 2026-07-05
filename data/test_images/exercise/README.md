# Exercise Verification Test Set (gym + home_workout MVP)

물 인증(`data/test_images/water/`)과 동일한 구조의 운동 인증 테스트셋이다.
MVP 1차 범위는 **gym + home_workout**이며, 수영/요가/필라테스/러닝은 다음 단계로 남긴다.

파이프라인:

```
image → Qwen VLM 증거 추출 → normalize_exercise_output → VisionAnalysis
      → evaluate_image_verification("exercise", …, ctx(exercise_activity_type)) → PASS/FAIL
```

VLM은 시각 증거만 추출하고 최종 판정은 Rule Engine이 한다. `exercise_activity_type`(gym|home_workout)
컨텍스트가 필요하다.

## 판정 기준 (MVP, 보수적)

- **PASS**: 운동 기구(덤벨/러닝머신/바벨/웨이트머신/벤치) 또는 홈트 근거(매트/밴드/홈트 자세)가 명확
  - gym: `gym_environment` + 기구 근거
  - home_workout: 매트/밴드/기구/홈트 자세 근거
- **FAIL**: 사무실/책상/노트북/침실/음식/빈 방 등 운동과 무관하거나 근거 부족
- **BORDERLINE**: 운동화만 등 운동 의도는 가능하나 인증 근거 부족(PASS 아님)
- 단순히 사람이 서 있거나, 운동화/물병만 보이는 것은 PASS가 아니다.

라벨 매핑: `verified → PASS`, `rejected → FAIL`, `retake_required → BORDERLINE_CASE`.

## 디렉터리 구조

```
data/test_images/exercise/
├── generated/            # 합성 이미지 12장
├── exercise_manifest.json
└── README.md
```

### 매니페스트 필드 (`exercise_manifest.json` → `images[]`)

| 필드 | 설명 |
|------|------|
| `filename` | 파일명 |
| `image_path` | 저장소 루트 기준 경로 |
| `expected_label` | `PASS` / `FAIL` / `BORDERLINE` |
| `source` | `generated` |
| `exercise_activity_type` | `gym` / `home_workout` |
| `reason` | 판정 근거 |
| `difficulty` | `easy` / `medium` / `hard` |
| `vision_analysis` | GPU 없이 Rule Engine을 검증하기 위한 사람 검수 VisionAnalysis 픽스처(`exercise_visual_evidence` 사용) |

## 이미지 생성

```bash
python scripts/generate_exercise_test_images.py
```

pytest는 `generated/` 이미지가 없으면 세션 시작 시 위 명령을 자동 실행한다.

## 테스트

```bash
python -m pytest tests/test_exercise_verification_fixtures.py -v -s
```

## 실제 Qwen 배치 실행 (GPU 필요)

```bash
python local_eval/qwen_vlm_eval/scripts/run_qwen_exercise_batch.py --limit 3
python local_eval/qwen_vlm_eval/scripts/run_qwen_exercise_batch.py
```

옵션: `--manifest`, `--output-dir`, `--model`(기본 `Qwen/Qwen2.5-VL-3B-Instruct`),
`--limit`, `--start-index`, `--skip-existing`.

산출물 (`local_eval/qwen_vlm_eval/outputs/exercise_batch/`):
`{stem}_raw.json`, `{stem}_raw_text.txt`, `{stem}_normalized.json`, `{stem}_result.json`,
`exercise_qwen_batch_report.csv`(컬럼: filename, source, exercise_activity_type, expected_label,
predicted_label, engine_result, score, mandatory_passed, ok, exercise_visual_evidence, objects,
raw_output_path, normalized_output_path, result_output_path, error).

## 관련 코드

- 배치 실행: `local_eval/qwen_vlm_eval/scripts/run_qwen_exercise_batch.py`
- 정규화: `local_eval/qwen_vlm_eval/scripts/normalize_exercise_output.py`
- 단건 Qwen 추론: `local_eval/qwen_vlm_eval/scripts/run_qwen_single.py --verification-type exercise --activity-type gym`
- Rule Engine: `backend/services/image_verification_rule_engine.py`
- Exercise 규칙: `backend/rules/image_verification/exercise.yaml`

## 판정 파서 재사용 검토

물 인증의 `water_verdict.py`는 `verified/rejected/…` → PASS/FAIL 매핑과 문자열 파서를 제공하지만
`evaluate_image_verification("water", …)`에 묶여 있다. 운동 배치는 물 배치와 동일하게 Rule Engine
결과(`verified/rejected/retake_required`)를 직접 `ENGINE_TO_PREDICTED`로 매핑하므로 별도 verdict
모듈이 필요 없다. 문자열 형태의 모델 출력을 파싱해야 할 경우 `water_verdict.parse_text_verdict`는
운동에도 그대로 재사용할 수 있다.
