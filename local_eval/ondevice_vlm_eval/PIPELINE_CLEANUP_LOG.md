# Pipeline Cleanup Log (실험 위생 정리)

작성 2026-07-09. PIPELINE_INTEGRITY_AUDIT 의 MEDIUM 항목(P1/P4/P5) 처리. **파일 정리 + metadata 추가만 수행.**
> **평가 로직 변경 없음. 성능 수치 불변.** parser/guard/Rule Engine core/backend/Flutter/라벨/include/final_manifest **미변경.** 이미지 이동·삭제 **없음.** 새 평가/모델 재실행/Gate3 **없음.**

## P1 — stale harness 정리
- `run_candidate_final_eval_curated.py` 는 guard 플래그(`--option-r/--exclude-ids/apply_exercise_pose/apply_option_r_guards`) **0개** = 구버전/stale 사본 확인.
- 코드 참조 없음(문서 언급만) 확인 → **삭제 대신 archive 이동**:
  - `local_eval/real_validation_dataset/run_candidate_final_eval_curated.py`
    → `local_eval/ondevice_vlm_eval/_archive/run_candidate_final_eval_curated.py.stale`
- **정본 runner = `local_eval/real_validation_dataset/run_candidate_final_eval.py` 하나만 유지**(존재 확인).

## P4 — root stray script 정리
- root 임시 분석 스크립트 이동:
  - `make_fp_review_montage.py` (repo root) → `local_eval/ondevice_vlm_eval/tools/make_fp_review_montage.py`
- repo root 에 stray `*.py` **없음** 확인.

## P5 — run별 metadata.json 추가 (신규 sidecar, 결과파일 미변경)
아래 4개 결과 폴더에 `metadata.json` 생성(필드: model_name/model_path/mmproj_path/engine/runtime/guard_config/probe_scope/n_total/excluded_ids/curated_or_original/command/output_dir/predictions_path/per_image_path/failure_cases_path/raw_outputs_count/report_path/gate/gate3_allowed=false/notes):
| run | n_total | excluded_ids | guard_config(요약) |
| --- | --- | --- | --- |
| internvl2_5_1b_gate2_probe | 48 | [] | none (pre-R baseline) |
| internvl2_5_1b_gate2_option_r_original48 | 48 | [] | water only (exercise OFF) |
| internvl2_5_1b_gate2_option_r_exercise_original48 | 48 | [] | water + exercise |
| internvl2_5_1b_gate2_option_r_original47_exclude_intake021 | 47 | [intake_021] | water only (exercise OFF) |
- 모든 metadata 에 `gate3_allowed: false` 명시.

## 무결성 확인
- 4개 폴더 `predictions.jsonl`/`per_image.csv` **mtime 불변**(15:06/17:11/17:33/17:44) — metadata.json 만 신규(19:15). **성능 수치 불변.**
- 이동 대상은 **스크립트 파일**뿐(이미지 아님). curated manifest/원본 manifest/라벨/include 미변경.

## 변경 없음 명시
- backend API / Flutter / Rule Engine core: **미변경**
- 이미지 라벨 / include / final_manifest: **미변경**
- parser 로직 / guard 로직: **미변경**
- **Gate3 금지 유지.**

## 이동/생성 요약
- 이동(archive): `run_candidate_final_eval_curated.py` → `_archive/…​.stale`
- 이동(tools): `make_fp_review_montage.py` → `tools/`
- 생성: 4× `metadata.json`, 본 로그, AUDIT cleanup 섹션.
