# FINAL_DATASET_SUMMARY

- input: local_eval/real_validation_dataset_150_candidate/labeled_candidate_final_reviewed.csv
- total rows: 237
- final included: **171**

## task별
- water: 57
- exercise: 60
- study: 54

## ground_truth별
- PASS: 81
- FAIL: 76
- BORDERLINE: 14

## task × ground_truth
- exercise/BORDERLINE: 6
- exercise/FAIL: 22
- exercise/PASS: 32
- study/BORDERLINE: 2
- study/FAIL: 23
- study/PASS: 29
- water/BORDERLINE: 6
- water/FAIL: 31
- water/PASS: 20

## source별
- user_upload: 42
- internet_real: 94
- user_collect: 35

## batch별
- initial: 106
- gap_fill_02: 30
- final_user_collect: 35

## 제외 사유별
- include!=Y: 66

## hygiene
- synthetic/generated/AI contamination(include=Y): **0** (OK)
- missing image: 0
- duplicate(filename/hash): 0

## 성공기준 판정
- ✅ OK: 각 task>=50, contamination=0, UNLABELED/TODO/include=N 없음