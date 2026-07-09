# Qwen-3B Task Prompts (water / study / exercise)

작성 2026-07-10. VLM baseline 용 task별 prompt 정리. 원문 구현: `local_eval/vlm_baseline/prompts.py`.
공통: VLM 은 보이는 것만 근거로 하고, **FP=0 우선**(애매→retake_required, 부정근거→rejected). 출력은 `QWEN3B_UNIFIED_VERIFICATION_BASELINE.md` 의 JSON 스키마.

## 공통 지침 (모든 task)
- 보이는 것만 판단. 추측 금지. 불확실하면 uncertainty=high → **retake_required**.
- 컵/병 등 용기 "이름"만으로 내용물을 단정하지 말 것.
- result 는 verified/rejected/retake_required 중 하나. positive_evidence/negative_evidence/reason 기록.

## water prompt
- **확인(positive)**: 맑은 물/투명한 물, 투명한 컵·병에 담긴 물, 물 수면/수위, 물을 마시거나 따르는 장면.
- **verified 금지(negative/blocker)**: 빈 컵/빈 병, 불투명 텀블러, 색 있는 음료, 커피/주스/우유/차/탄산, 내용물 안 보임/반사만.
- **애매하면 retake_required**(액체 종류 불명확, 거의 빈 용기, 불확실).

## study prompt
- **확인(positive)**: 책/교재/워크북, 노트/필기, 문서/PDF/보고서, 코드/개발환경/터미널, 강의/강의자료 화면.
- **verified 금지(negative/blocker)**: 게임, 유튜브/영상/드라마, 쇼핑, SNS/인스타, 홈 화면/앱 아이콘, 노트북만 있고 학습 내용 불명, 빈 책상.
- **애매하면 retake_required**(화면 내용 불명확, 닫힌 책, 판별 불가).

## exercise prompt
- **확인(positive)**: 실제 운동 동작/자세(푸시업/스쿼트/러닝/스트레칭/요가 등), 운동기구를 **사용 중**, 헬스 머신 사용 중.
- **verified 금지(negative/blocker)**: 운동기구만 있음(동작 없음), 헬스장 배경만, 운동복만, 앉아서/쉬는 중, 셀카, 접힌/보관된 요가매트.
- **애매하면 retake_required**(동작 여부 불명확, 장비만 보임, 불확실).

## 매핑 원칙
- 각 task 에서 **positive 와 negative/blocker 가 동시에 있으면 blocker 우선(→ rejected 또는 retake)**.
- **equipment/용기 존재만으로 verified 금지** — water 는 가시 액체, exercise 는 실제 동작이 있어야 verified.
