# SmolVLM-500M 최종 평가 런북 (real-only, FP=0 게이트)

목적: 사용자 최종 검수 데이터셋으로 SmolVLM-500M 을 평가해 **온디바이스 진입 조건**을 판정.
원칙: VLM 은 evidence 만, 최종 판정은 Rule Engine. FP=0 최우선. synthetic/AI/illustration 절대 미사용.

경로:
- 후보셋: `local_eval/real_validation_dataset_150_candidate/`
- 평가기(고급): `local_eval/real_validation_dataset/evaluate_real_dataset_advanced.py`
- 추론 러너(기존, GGUF/transformers 공용): `local_eval/real_validation_dataset/evaluate_minicpm_v46_gguf.py`
  (`--model-name`/`--gt` 지원. SmolVLM ONNX 추론 러너가 별도로 필요하면 동일 출력 스키마로 predictions 생성.)

---

## 1. final_manifest 생성
사용자 최종 검수 CSV(`labeled_candidate_final_reviewed.csv`) 준비 후:
```bash
cd local_eval/real_validation_dataset_150_candidate
python build_final_manifest.py --input labeled_candidate_final_reviewed.csv
# → final_manifest.csv / final_manifest.json / FINAL_DATASET_SUMMARY.md
```
확인: `FINAL_DATASET_SUMMARY.md` 에서 **contamination=0**, task별 수량, UNLABELED/include=N 제외 여부.
- contamination>0 이면 ERROR → 원본 라벨/소스 정정 후 재실행(평가 진행 금지).

## 2. SmolVLM-500M inference 실행 → predictions 생성
predictions 는 **이미지별 Rule Engine 결과**를 담아야 한다(pred_result, got_evidence, rule_evidence, score, mandatory_passed, latency).
- 데스크톱(transformers, qwen-vlm env)에서 SmolVLM 어댑터로 추론하는 러너를 final_manifest 대상으로 실행.
  (기존 `run_ondevice_eval.py`/adapter 흐름 재사용 또는 final_manifest 를 읽어 `smolvlm_adapter.analyze`→Rule Engine 호출하는 스크립트.)
- 출력 스키마(권장, evaluate_real_dataset_advanced 가 읽는 필드):
```json
{"image_id":"water_001","image":"images/water/water_001.png","verification_type":"water",
 "pred_result":"verified","got_evidence":["visible_water","filled_container"],
 "rule_evidence":["water_evidence:visible_liquid"],"score":100,"mandatory_passed":true,
 "model_load_time":..,"inference_time":..,"parse_time":..,"rule_engine_time":..,"total_time":..}
```
- **주의**: pred_result 는 반드시 Rule Engine(evaluate_image_verification) 출력. VLM raw 로 PASS/FAIL 직접 생성 금지.

## 3. predictions.jsonl 생성 위치
`local_eval/real_validation_dataset/results/<run>/predictions.jsonl` (또는 per_image.csv). 이미지 키는 image_id 또는 파일명.

## 4. advanced metrics 실행
```bash
cd /home/piai/AI_Secretary_FeatureJW_Qwen
python local_eval/real_validation_dataset/evaluate_real_dataset_advanced.py \
  --manifest local_eval/real_validation_dataset_150_candidate/final_manifest.json \
  --predictions local_eval/real_validation_dataset/results/smolvlm500_final/predictions.jsonl \
  --run-name smolvlm500_final \
  --output-dir local_eval/real_validation_dataset/results
```
산출: metrics_summary.(json/csv), safety_summary.json, false_positive_cases.json, false_negative_cases.json,
borderline_cases.json, evidence_metrics.json, rule_diagnostics.json, latency_summary.json,
dataset_hygiene.json, per_image.csv, experiment_report.md.

## 5. FP=0 확인
- `safety_summary.json` → `FP_count` **== 0** 확인. (borderline_as_fail 모드 기준이 가장 보수적.)
- `metrics_summary.csv` 의 ALL/water/exercise/study 행 `fp` 열 모두 0.
- `dataset_hygiene.json` → `synthetic_generated_contamination_count == 0` 확인(오염 시 결과 무효).

## 6. false_positive_cases.json 확인
FP 가 있으면 각 케이스의 `ground_truth / pred_result / got_evidence / rule_evidence` 를 보고 원인 분류:
1. **라벨 오류**(실제 PASS인데 FAIL 라벨) → 라벨 수정 후 재평가.
2. **parser 오류**(raw엔 부정인데 evidence 과추출) → smolvlm_adapter 파서 규칙 보강(용기명만 금지 등).
3. **prompt 문제**(부정어 주입/echo) → 프롬프트 중립화.
4. **rule threshold 문제** → Rule Engine 정책은 수정 금지(관찰만), 필요 시 별도 이슈로 보고.
5. **모델 hallucination**(raw 자체가 없는 물/기구를 서술) → 파서로 불가 → **온디바이스 단독 후보 보류**.

## 7. task별 결과 해석
- water/exercise: FP=0 + accuracy 안정(≥ 기존 desktop 수준)이면 **온디바이스 종결 가능**.
- study: recall 확인. 낮으면(FN 과다) 온디바이스 단독으로 study 종결하지 말 것.

## 8. study fallback 판단 기준
- study FP=0 이지만 recall 낮음 → **Qwen2.5-VL-3B-AWQ 서버 fallback 유지**(backend study fallback 골격 존재).
- study FP>0(모델 hallucination) → study 온디바이스 evidence 신뢰 불가 → 서버 우선 + 재촬영.
- borderline: `borderline_cases.json` 로 애매 케이스 분리 확인(as_fail/excluded 두 모드 비교).

## 9. 최종 온디바이스 진입 조건 (모두 충족해야 GO)
- [ ] final_manifest 기준 **synthetic/generated/illustration contamination = 0**
- [ ] water/exercise/study 각 **50장 이상 또는 충분 근접**, include_in_eval=Y 만 평가
- [ ] ground_truth 확정(UNLABELED/TODO = 0)
- [ ] SmolVLM-500M **real-only FP = 0**(safety_summary)
- [ ] water/exercise 정확도 안정
- [ ] study recall 낮으면 **Qwen2.5-VL-3B-AWQ fallback 유지**로 보완(단독 종결 금지)
→ 위 충족 시 `SMOLVLM_ONDEVICE_PLAN.md` 의 Android 패키징(ORT Mobile, 조합 A)으로 진행.

## 실패 시
- FP 발생 → 6절 순서(라벨→parser→prompt→threshold→hallucination)로 분석.
- FP 가 모델 hallucination → 온디바이스 단독 후보 보류(서버 경유/재설계).
- study FN 과다 → fallback 유지(구조 변경 없이 서버 재확인).
- runtime 불안정/오염 발견 → 평가 결과 무효 처리 후 원인 제거 재실행.
