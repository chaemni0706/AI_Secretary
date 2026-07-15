# 감정 기반 생활 코칭 MVP

## 1. 목적

사용자의 감정/상태 입력을 rule-based로 분석한 뒤 **오늘 일정·할 일·빈 시간·개인 preference**와
연결해, 단순 위로가 아니라 "지금 무엇을 하면 좋은지"를 카드로 제안합니다.

## 2. rule-based MVP (학습 모델 아님)

새 감정 학습 모델/파인튜닝 없음, 외부 심리·의료·지도·예약 API 없음, 실제 LLM 의존 없음.
기존 `emotion_analyzer`(crisis 키워드), `dashboard_service`(오늘 컨텍스트),
`reservation_recommender`(빈 시간 탐색), `preference_service`(개인화)를 재사용합니다.

## 3. 감정 분류 기준

키워드 기반으로 상태를 분류하고, 여러 개가 감지되면 `primary_emotion` + `secondary_emotions`로
나눕니다. 매칭이 없으면 `neutral`. `emotion_score`(0~1) 반환.

상태: `stress, tired, overwhelmed, anxious, sad, unmotivated, angry, positive, neutral`.
(기존 `/emotion/analyze` 계약을 깨지 않도록 별도 키워드 세트로 구현.)

## 4. 일정/To-do 연결

`dashboard_service.get_today(date=..., current_datetime=date+T00:00)`로 오늘 컨텍스트를 조회해
`context_summary`(schedule_count, todo_count, next_schedule, due_todos)를 채웁니다. 마감 임박
할 일이 있으면 `break_down_task` 카드를 우선 추가합니다.

## 5. 빈 시간 추천

`reservation_recommender.recommend_candidates`를 재사용해 09:00~21:00 창에서 오늘 일정
(start/end)을 busy로 두고 30분 단위 빈 슬롯을 찾습니다. `avoid_times`에 해당하는 시간대는
제외하고, 없으면 "5분 짧은 휴식" fallback 카드를 제공합니다. 응답 `free_time_slots`.

## 6. 장소 추천 (rule-based)

실제 지도 API 없이 감정별 장소 유형을 제안합니다(tired→카페/산책로, stress→산책로/카페,
overwhelmed→산책로, sad→따뜻한 카페, unmotivated→가벼운 운동 공간). 실제 거리 계산은
하지 않습니다. 응답 `place_recommendations`(place_type/name/reason).

## 7. 예약 후보 추천 연결

감정 상태를 **기존 가상 업체 카테고리**로 매핑해 `reservation_suggestions`(category,
time_preference, reason, next_api)를 optional로 제공합니다. tired/stress→`pt`,
unmotivated→`studyroom`, 미용/네일 발화→`hair`/`nail`. 사용자가 선택하면
`POST /api/v1/reservations/business-candidates`(category/date/time_preference)로 이어집니다.
실제 예약 확정은 하지 않습니다.

## 8. 개인 preference 반영

`preference_service` 재사용: `preferred_tone`(gentle/warm→부드러운 말투),
`coaching_style`(supportive→공감형 마무리), `rest_recommendation_enabled=false`→rest 액션 대체,
`avoid_times`→빈 시간/예약 제외, `preferred_reservation_times`→추천 시간대,
`stress_triggers`→입력에 포함 시 stress 강화. `personalization.used_preferences`에 반영 목록.

## 9. 안전 표현 기준

의료/심리 진단 표현 금지("우울증입니다", "치료가 필요합니다" 등). "스트레스가 높아 보입니다"
같은 제안형 표현만 사용. 자해/위기 키워드(죽고 싶/자해/사라지고 싶 등) 감지 시 진단 없이
`safety.risk_level="high"` + `support_message`로 도움 요청을 안내하고 일반 코칭 대신 지지 카드만
반환합니다. `safety.diagnosis=false`, `medical_advice=false` 고정.

## 10. API 요청/응답 예시

요청 `POST /api/v1/coaching/life`:

```json
{ "user_id": "local-user", "text": "오늘 너무 지치고 머리가 복잡해", "date": "2026-07-01", "timezone": "Asia/Seoul" }
```

응답 `data`(요약): `primary_emotion`, `secondary_emotions`, `emotion_score`, `context_summary`,
`coaching_cards[]`(action_type/title/message/reason), `free_time_slots[]`,
`place_recommendations[]`, `reservation_suggestions[]`, `personalization`, `safety`, `warnings`.

`coaching_cards`의 action_type: `rest, reschedule, break_down_task, start_small, prepare_now,
find_free_time, recommend_place, recommend_reservation, encourage`.

## 11. Flutter에서 사용할 필드

`primary_emotion`(감정 뱃지), `coaching_cards`(카드 UI), `free_time_slots`("이 시간에 쉬기"),
`place_recommendations`("장소 추천 보기"), `reservation_suggestions`(예약 후보 API 연결),
`personalization`, `safety`. `safety.risk_level=="high"`면 일반 코칭보다 안전 안내를 우선 표시.

## 12. 현재 MVP 한계

rule-based 분류(문맥/부정어 미세 처리 제한), 장소는 가상 rule 추천(실제 지도/거리 없음),
빈 시간 창은 09:00~21:00 고정·30분 단위, `user_id`는 단일 `local-user`, next_schedule은
해당 날짜 00:00 기준 "가장 이른 일정"으로 계산, 예약 후보는 힌트만 제공(자동 조회/확정 없음).

## 13. 추후 개선 방향

감정 분류 고도화(가중치/부정어/문맥, 필요 시 비진단 가드 하에 LLM 보조), 실제 free-busy·지도
연동, reservation_suggestions에서 실제 후보를 미리 조회해 첨부, 위기 대응 시 지역 긴급 연락처
연계, 사용 로그 기반 개인화 학습.
