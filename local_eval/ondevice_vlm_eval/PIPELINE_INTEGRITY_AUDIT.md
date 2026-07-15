# Pipeline Integrity Audit — InternVL2.5-1B eval 파이프라인

작성 2026-07-09. **정적 점검·파일 무결성만** 수행(모델 재실행/새 평가/Gate3 없음). 목적: 성능이 아니라 구조 오염 여부 감사.

## 1. Audit 목적
여러 eval-only guard(Option R water/exercise) + curation/exclusion 처리 후, **backend/Flutter/Rule Engine core/라벨/include/final_manifest 오염 여부**와 eval/prod 경계, 재현성, parser 안정성을 점검.

## 2. 현재 실험 상태 요약
InternVL2.5-1B Q8: Gate1 smoke=pass_to_gate2 / original48 pre-R FP5 / water OptR FP2 / water+ex OptR FP1(단 PASS 4→1 붕괴) / original47(intake_021 제외)+water OptR FP1(water_045만, PASS4 유지, exercise recall 0.60). **Gate3 계속 금지.**

## 3. 변경 파일 목록 (git 기준)
- **tracked modified(M)**: `MODEL_SELECTION.md`, `SMOLVLM_ONDEVICE_PLAN.md`, `report_archive_20260709.tar.gz`, `real_validation_dataset_150_candidate/{final_manifest.csv, final_manifest.json, build_final_manifest.py, FINAL_DATASET_SUMMARY.md}` — **전부 local_eval 내부**.
- **untracked(??)**: 다수 eval 리포트/CSV + `internvl_mtmd_adapter.py`, `calibrate_gate2_5.py`, `run_candidate_final_eval_curated.py`(root의 `make_fp_review_montage.py` 포함) — 전부 eval 산출물.
- **07-09(감사 대상 eval 작업일) 실제 수정**: `internvl_mtmd_adapter.py`(17:29), `run_candidate_final_eval.py`(17:41), 4개 이미지 복원(17:08), curated manifest 생성(16:33) 등 — **전부 local_eval / 이미지 복원**.

## 4. production path 오염 여부 → **없음**
- **backend/services/**(image_verification_rule_engine.py, image_verification_service.py, local_vlm_analyzer.py) mtime = **2026-07-07 22:27**. eval 작업은 07-09 11:00–17:47 → **eval 이 Rule Engine core 를 수정하지 않음**(07-07 은 사전 baseline).
- backend/flutter/lib/app **07-09 수정 0건**.
- guard 식별자(`option_r/apply_option_r/exercise_guard/uncertainty_gate/opaque_or_empty/apply_exercise_pose/internvl_mtmd`) grep → **전부 local_eval 하위 3개 py 에만** 존재. production import 경로 없음.

## 5. dataset/manifest 무결성
- `final_manifest.csv`: HEAD 171 ↔ CUR 171 행. **image_id/task/ground_truth tuple 변경 0건**(HEAD-only 0, CUR-only 0). diff 원인 = **`source` 컬럼 1개 추가**(earlier dataset-build 단계, mtime 07-09 09:43 = 이번 eval 세션 이전). **라벨/정답 불변, include 컬럼 없음.**
- missing image: `final_manifest.csv` **0** / `final_manifest_curated44.csv` **0**.
- quarantine 후 복원된 4장(intake_009/021, water_014/045) **모두 원본 위치에 존재**, quarantine 사본도 유지. **intake_021 물리 삭제 안 됨.**
- 판정: 라벨/manifest 라벨값 오염 없음. `source` 컬럼 추가는 eval 이전 dataset 작업이며 평가에 영향 없음(ground_truth 불변).

## 6. eval/prod 경계 점검
1. Option R guard 가 eval-only 경로에만? → **예**(internvl_mtmd_adapter.py + run_candidate_final_eval.py). 
2. production inference 에서 import? → **아니오**(guard 식별자 backend/flutter 부재).
3. Rule Engine core 수정? → **아니오**(07-07 baseline, eval 미수정).
4. adapter 가 모델 호출 이상 판정 로직 포함? → **부분적으로 포함**(guard 함수가 adapter 파일에 있음, §7 참조). 단 최종 verdict 는 Rule Engine 이 냄(guard 는 evidence 억제만).

## 7. adapter/guard/Rule 역할 분리 점검
- 현재 `internvl_mtmd_adapter.py` 안에 (a) 모델 호출(run_cli) + (b) parser(parse_internvl) + (c) **eval guard(apply_option_r_guards, apply_exercise_pose_action_guard)** 가 **혼재**.
- guard 는 "positive evidence 억제만"이라 판정을 직접 하진 않지만, **역할 계층이 섞여 baseline/guard 혼동 위험** → **리팩토링 권고(§12)**. (지금 리팩토링은 하지 않음.)

## 8. parser/schema 안정성 (parser_audit)
- **valid_json_count = 29/48**, **fallback_parse_count = 19/48**, **parse_failure_count = 0** (모든 InternVL run 동일).
- fallback 로직: JSON 파싱 실패 시 **raw 원문 전체를 보수 파서(_mini_parse_raw)에 키워드 매칭** → positive evidence 생성 가능(예: intake_010 의 "transparent liquid"→visible_clear_liquid FP 는 malformed JSON fallback 에서 발생).
- **fallback 위험성: MEDIUM.**
  - parse_failure=0 은 **오해 소지**: 실패가 없는 게 아니라 fallback 이 항상 무언가를 만들어 냄. valid_json/fallback 분리 로깅은 `json_parsed` 필드로 가능(저장됨).
  - **uncertainty 가 normalizer 에 반영되지 않음** — 불확실("not sure") 표현이 있어도 base parser 는 positive 를 낼 수 있고, 억제는 **오직 Option R guard(eval-only)** 가 담당. base 파이프라인만 쓰면 uncertainty 무시.
  - 과거 버그(‘uncertain’이 JSON 키 "uncertainty"에 substring 매칭되어 water_007 오억제) → **수정됨**(uncertainty '값'만 정규식 추출, adapter L151–157). 재발 없음(확인).
- parsed evidence / raw output / optr_suppressed_evidence **모두 저장됨**(raw_text 전 run, optr_* 는 Option R run).
- **수정 필요**: (1) fallback 을 별도 카운트/표기, (2) uncertainty 게이트를 normalizer 로 승격 고려, (3) malformed JSON 은 더 보수적으로(positive 억제) 처리.

## 9. result reproducibility 점검
- 4개 결과 폴더 **분리 존재**(덮어쓰기 없음): `internvl2_5_1b_gate2_probe`, `_option_r_original48`, `_option_r_exercise_original48`, `_option_r_original47_exclude_intake021`.
- 각 폴더: predictions.jsonl / per_image.csv / failure_cases.json / commands.txt / raw_outputs/ **전부 존재**. 각 단계 report md 존재.
- **metadata.json 없음(MEDIUM)**: engine/guard_config/probe_scope/excluded_ids 가 구조화되어 있지 않음. commands.txt(사람 판독용) + run-name 에 암묵적으로만 인코딩. → run 별 metadata.json 권고.

## 10. 발견된 문제
| # | 문제 | 위험 |
| --- | --- | --- |
| P1 | **중복/구버전 harness** `run_candidate_final_eval_curated.py`(410줄, `--option-r/--exclude-ids`·exercise guard **없음**, grep option_r/exclude=0) — 정본과 혼동·잘못된 재현 위험 | MEDIUM |
| P2 | **parser fallback 과관대** — 19/48 malformed JSON 이 raw 키워드 매칭으로 positive 생성, uncertainty 무시(guard 로만 방어), parse_failure=0 오해소지 | MEDIUM |
| P3 | **guard 가 adapter 에 혼재** — 모델호출/parser/guard 계층 미분리 | MEDIUM |
| P4 | **root 스트레이 스크립트** `make_fp_review_montage.py`(local_eval 밖, 이전 깨진 montage) | MEDIUM |
| P5 | **run metadata.json 부재** — 재현 조건 구조화 안 됨 | MEDIUM |
| P6 | final_manifest.csv M vs HEAD(`source` 컬럼 추가, eval 이전, 라벨 불변) | LOW |
| P7 | quarantine 복원 4장 mtime 갱신(의도적, 문서화됨) / __pycache__ 존재 | LOW |

## 11. risk level → **MEDIUM (전반 LOW–MEDIUM)**
- critical/high = **0**. production/라벨/Rule Engine core **무오염**, missing image **0**.
- MEDIUM 5건은 전부 **eval 측 위생/혼동 위험**(오염 아님).

## 12. 반드시 고쳐야 할 항목 (다음 실험 전)
1. **P1**: `run_candidate_final_eval_curated.py` 제거 또는 `outputs/_deprecated/`로 이동(정본은 `run_candidate_final_eval.py` 하나로).
2. **P4**: root `make_fp_review_montage.py` 를 `local_eval/ondevice_vlm_eval/` 로 이동 또는 제거.
3. **P5**: run 별 `metadata.json`(engine, model_path, guard_config, probe_scope, excluded_ids, n_total, run command) 기록.

## 13. 다음 실험 전에 해야 할 항목 (권고)
4. **P3 리팩토링**: guard 를 `eval_guards.py`(water/exercise/clip verifier, config 이름 관리)로 분리, adapter 는 모델호출+parser+raw 저장만.
5. **P2**: fallback 을 valid_json 과 분리 로깅하고, malformed JSON 시 positive 보수화(또는 uncertainty 게이트를 normalizer 로).
6. experiment registry 표(아래) 유지.

### experiment registry (현 상태)
| run | manifest | scope | guard | FP | verified_PASS | 폴더 |
| --- | --- | --- | --- | --- | --- | --- |
| pre-R | original | 48 | none | 5 | 4 | internvl2_5_1b_gate2_probe |
| water OptR | original | 48 | water | 2 | 4 | _option_r_original48 |
| water+ex OptR | original | 48 | water+exercise | 1 | 1 | _option_r_exercise_original48 |
| orig47 ex-021 | original | 47(−intake_021) | water | 1(water_045) | 4 | _option_r_original47_exclude_intake021 |
| curated46 OptR | curated44 | 46 | water | 0 | 4 | internvl2_5_1b_gate2_probe_curated44_optR |

## 14b. Cleanup 완료 (2026-07-09, PIPELINE_CLEANUP_LOG.md)
P1/P4/P5 처리 완료 — **파일 정리 + metadata 추가만, 평가 로직/성능 수치 불변**:
- **P1**: stale `run_candidate_final_eval_curated.py` → `_archive/run_candidate_final_eval_curated.py.stale` 이동. 정본 runner 1개(`run_candidate_final_eval.py`) 유지.
- **P4**: root `make_fp_review_montage.py` → `local_eval/ondevice_vlm_eval/tools/` 이동. repo root stray .py 0.
- **P5**: 4개 결과 폴더에 `metadata.json` 생성(engine/guard_config/probe_scope/excluded_ids/n_total/command/report_path/gate3_allowed=false 등).
- 무결성: predictions/per_image mtime 불변(성능 불변). backend/Flutter/Rule Engine core/라벨/include/final_manifest/parser/guard 로직 **미변경**. Gate3 금지 유지.
- 잔여 권고(선택, 미실행): P3(guard→`eval_guards.py` 분리), P2(fallback 보수화/valid_json 분리 로깅).

## 14. 진행 가능 여부 → **proceed_after_cleanup** (P1/P4/P5 완료 → 다음 실험 진행 가능)
production/데이터 라벨/Rule Engine 은 안전하므로 실험 계속 가능. 단 **P1/P4/P5(중복 harness·스트레이 스크립트 정리·metadata 기록)를 먼저 처리**해 baseline/guard 결과 혼동을 막은 뒤 다음 실험을 진행할 것. (stop_and_refactor 아님 — 오염·손상 없음. 완전 safe_to_continue 도 아님 — 위생 이슈 존재.)
