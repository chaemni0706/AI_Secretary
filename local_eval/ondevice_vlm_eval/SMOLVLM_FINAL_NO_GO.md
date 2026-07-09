# SmolVLM-500M 온디바이스 단독 인증 — 최종 NO-GO

결정일: 2026-07-09. 데이터: final real-only dataset **171장**(contamination=0). 판정: **탈락(NO-GO)**.

## 결론 (확정)
SmolVLM-500M 은 **온디바이스 단독 이미지 인증 후보에서 탈락**한다.
- final real-only 171장에서 **FP=9** (water 6, study 3, exercise 0) → 통과 기준 **FP=0 미달**.
- 사용자 FP 이미지 직접 검토 결과: **단순 hallucination 완화 문제가 아니라 기본 시각 분별력 부족**.
  - 게임 화면 / 공부 화면 구분 실패
  - 색 음료 / 물 구분 실패
  - 빈 컵 / 물컵(빈-찬), 불투명 용기 내부 구분 실패
- 파서/프롬프트/threshold 로 교정 불가(raw text 자체가 "a glass of water"·"open textbook"·"coding screen" 처럼 정답을 지어냄).

## 근거 지표 (borderline=as_fail)
| task | n | TP | TN | FP | FN | acc | precision | recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| water | 57 | 5 | 31 | **6** | 15 | 0.632 | 0.455 | 0.250 | 0.323 |
| exercise | 60 | 3 | 28 | **0** | 29 | 0.517 | 1.000 | 0.094 | 0.171 |
| study | 54 | 12 | 22 | **3** | 17 | 0.630 | 0.800 | 0.414 | 0.545 |
| **ALL** | 171 | 20 | 81 | **9** | 61 | 0.591 | 0.690 | 0.247 | 0.364 |
- rule 결과 분포: rejected 122 / verified 29 / retake 20, mandatory_passed_rate 0.257.
- borderline_excluded 시 FP=8. 추론 에러 0, model load 6.3s.
- exercise FP=0 이나 recall 0.094(final_manifest 에 activity 미포함 → evidence 로 추정, Rule Engine gym 요건 엄격 → 대량 FN). exercise 자체가 GO 라는 뜻은 아님(민감도 부족).

## FP 9건 실패 유형 (상세: SMOLVLM_FP_FAILURE_TAXONOMY.csv)
- empty_vs_full ×2 (water_009 빈 크리스탈잔, water_035 거의 빈 물병) + empty_vs_full_ambiguous ×1 (water_004)
- colored_beverage_vs_water ×1 (water_020 노란 액체→물)
- opaque_container_hallucination ×1 (intake_010 불투명 텀블러 내부 물 환각)
- container_misidentification ×1 (intake_009 블렌더→물컵)
- closed_vs_open_book ×1 (intake_032 닫힌 책→"open textbook+handwritten notes")
- screen_content_misread ×2 (study_011 추상 책장사진→coding screen, exercise_012 잡동사니 책상→textbook highlighted)
- 공통 root cause: **model_visual_discrimination(시각 분별력 부족)**.

## 함의 / 다음 단계
- 온디바이스 **단독 verify 금지**. SmolVLM-500M 을 프로덕션 인증 판정에 연결하지 않는다.
- 대안 방향(별도 문서):
  1. `NEXT_ONDEVICE_MODEL_SEARCH_PLAN.md` — 더 강한 소형 온디바이스 후보(Gemma 3n, SmolVLM2-2.2B 재평가, Qwen3-VL-4B, **CLIP/SigLIP/MobileCLIP image-text scoring**).
  2. `SERVER_FALLBACK_MODEL_PLAN.md` — 서버 7B/8B+ (Qwen2.5-VL-7B, Qwen3-VL-8B, InternVL 8B, 필요 시 72B teacher).
  3. 하이브리드: 온디바이스는 명백 negative 선(先)거절 pre-filter, **PASS 확정은 서버 고성능 모델(FP=0 검증)**.
- 기존 backend API / Flutter / Rule Engine core 는 수정하지 않는다. VLM 은 evidence 만, 판정은 Rule Engine.

## 보존 아카이브
`report_archive_20260709/` (+ `report_archive_20260709.tar.gz`): final_manifest(csv/json), FINAL_DATASET_SUMMARY,
metrics_summary(json/csv), safety_summary, false_positive/negative_cases, FP_montage.png, experiment_report,
ONDEVICE_INTEGRATION_SAFETY_PLAN, SMOLVLM_FINAL_NO_GO, SMOLVLM_FP_FAILURE_TAXONOMY.
