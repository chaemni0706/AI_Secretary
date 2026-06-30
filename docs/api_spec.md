# AI Secretary Backend — API Spec

모든 응답은 공통 envelope를 따릅니다.

```json
{ "success": true, "message": "...", "data": { } }
```

- `success`: 처리 성공 여부 (bool)
- `message`: 사람이 읽는 메시지 (string)
- `data`: 엔드포인트별 실제 데이터 (object | null)

오류 시 `success=false`, `data=null`(검증 오류는 `data`에 상세), HTTP 상태코드로 구분합니다.
Base URL: `http://127.0.0.1:8000`, API prefix: `/api/v1` (health 제외).

---

## GET /health

응답:
```json
{
  "success": true,
  "message": "Backend server is running",
  "data": { "status": "ok", "service": "AI Secretary Backend" }
}
```

---

## POST /api/v1/ai/schedule/parse — 자연어 일정 파싱

Request:
```json
{
  "input": "내일 오후 2시에 병원 예약 잡아줘",
  "input_type": "text",
  "current_datetime": "2026-06-29T10:00:00+09:00",
  "timezone": "Asia/Seoul"
}
```

Response `data`:
```json
{
  "intent": "create_schedule",
  "confidence": 0.94,
  "slots": {
    "title": "병원 예약", "date_expression": "내일", "time_expression": "오후 2시",
    "date": "2026-06-30", "start_time": "14:00", "end_time": "15:00",
    "category": "hospital", "location": null
  },
  "schedule_draft": {
    "title": "병원 예약", "category": "hospital", "date": "2026-06-30",
    "start_time": "14:00", "end_time": "15:00", "location": null, "memo": null,
    "priority": "high", "source": "ai"
  },
  "missing_fields": []
}
```

- 날짜/시간/제목이 없으면 `missing_fields`에 `"date"`, `"time"`, `"title"` 추가.
- 오전/오후 표기 없는 시각(예 "3시")은 오후로 추정(15:00)하고 `missing_fields`에 `"time_ambiguity"`.
- 잘못된 시각(분 0~59·시 0~23 초과, "3시간" 같은 기간 표현)은 시간으로 인식하지 않음.

---

## POST /api/v1/reservations/candidates — 예약 후보 추천

Request:
```json
{
  "current_datetime": "2026-06-29T10:00:00+09:00",
  "constraints": {
    "target_date": "2026-07-03", "preferred_start_time": "18:00",
    "preferred_end_time": "21:00", "duration_minutes": 60, "category": "beauty"
  },
  "existing_schedules": [
    {"id": "sch_101", "title": "팀플 회의", "date": "2026-07-03", "start_time": "18:00", "end_time": "19:00"},
    {"id": "sch_102", "title": "저녁 약속", "date": "2026-07-03", "start_time": "20:00", "end_time": "21:00"}
  ]
}
```

Response `data`:
```json
{
  "target_date": "2026-07-03",
  "recommended_candidates": [
    {"candidate_id": "cand_001", "start_time": "19:00", "end_time": "20:00",
     "score": 93, "reason": "기존 일정 사이에 딱 맞는 빈 시간으로 예약 소요 시간 60분을 만족합니다.", "conflict": false}
  ],
  "rejected_slots": [
    {"start_time": "18:00", "end_time": "19:00", "reason": "팀플 회의와 시간이 겹칩니다."},
    {"start_time": "20:00", "end_time": "21:00", "reason": "저녁 약속과 시간이 겹칩니다."}
  ]
}
```

- 후보 없음: `recommended_candidates: []`, message `"예약 가능한 시간이 없습니다."`
- 점수: 기본 80 + 기존 일정 사이 딱 맞음(+10) + preferred_start 근접(+0~5) − 21시 이후(−5). 높은 순 정렬.
- 잘못된 시간 범위/형식은 200 + 빈 후보로 안전 처리.

---

## POST /api/v1/messages/reservation — 예약 문의 메시지 생성

Request:
```json
{
  "input": "내일 병원 예약 문의 문자 만들어줘",
  "reservation_info": {"category": "hospital", "target_date": "2026-06-30", "preferred_time": "10:00", "purpose": "진료 예약"},
  "style": {"tone": "polite", "length": "short", "channel": "sms"}
}
```

Response `data`:
```json
{
  "generated_message": "안녕하세요. 내일 오전 10시쯤 진료 예약이 가능한지 문의드립니다. 가능한 시간이 있을까요?",
  "alternatives": [
    "안녕하세요. 내일 오전 시간대에 진료 예약이 가능한 시간이 있는지 문의드립니다.",
    "안녕하세요. 내일 오전 10시 진료 예약 가능 여부를 확인 부탁드립니다."
  ],
  "style": {"tone": "polite", "length": "short", "channel": "sms"}
}
```

- `alternatives`는 항상 2개 이상. OpenAI 키 없으면 템플릿, 있으면 LLM 본문(실패 시 템플릿 fallback).
- category: hospital | beauty | restaurant | meeting | etc. tone: polite | casual | formal. length: short | medium | long. channel sms는 과도하게 긴 문장 금지.

---

## POST /api/v1/alerts/departure-plan — 준비물·출발 알림

Request:
```json
{
  "schedule": {"title": "병원 예약", "category": "hospital", "date": "2026-06-30", "start_time": "14:00", "location": "서울OO병원"},
  "context": {"weather": "rain", "estimated_travel_minutes": 35, "buffer_minutes": 10},
  "user_preference": {"notification_style": "strong", "forgetful": true, "late_prone": true}
}
```

Response `data`:
```json
{
  "leave_time": "13:15",
  "estimated_travel_minutes": 35,
  "buffer_minutes": 10,
  "checklist": [
    {"item": "신분증", "reason": "병원 일정에 필요한 기본 준비물입니다."},
    {"item": "진료카드", "reason": "병원 방문 시 필요할 수 있습니다."},
    {"item": "보험증", "reason": "병원 방문 시 필요할 수 있습니다."},
    {"item": "우산", "reason": "비 예보가 있습니다."}
  ],
  "notifications": [
    {"time": "13:00", "message": "병원 예약 준비를 시작할 시간입니다. 신분증과 진료카드를 미리 챙겨두세요."},
    {"time": "13:05", "message": "곧 출발해야 합니다. 신분증과 진료카드를 다시 한 번 확인하세요."},
    {"time": "13:15", "message": "13:15에 출발하면 병원 예약 시간에 맞출 수 있습니다."},
    {"time": "13:30", "message": "병원 예약 시간이 다가옵니다. 신분증과 진료카드를 챙기고 출발을 준비하세요."}
  ]
}
```

- `leave_time = start_time − estimated_travel_minutes − buffer_minutes`. 잘못된 start_time이면 `leave_time: null`, `notifications: []`.
- weather: rain(우산)/snow(우산·외투·장갑)/hot(물·선크림)/cold(외투·장갑)/sunny(추가 없음). 중복 준비물은 1개로.
- 알림: normal → 일정 30분 전 + 출발 시각. strong/forgetful → 일정 60·30분 전 + 출발 시각(사전 알림 강화), forgetful은 출발 10분 전 1회 추가. late_prone(선택, 기본 false) → 출발 20·10분 전 추가(출발 알림을 더 이르고 잦게). forgetful=사전 알림 강화, late_prone=출발 알림 강화로 의미가 분리됨. 중복 시각은 1개, 시각 오름차순.

---

## POST /api/v1/briefings/daily — 하루 브리핑

Request:
```json
{
  "date": "2026-06-30",
  "schedules": [
    {"title": "오전 수업", "category": "school", "start_time": "09:00", "end_time": "12:00", "priority": "medium"},
    {"title": "병원 예약", "category": "hospital", "start_time": "14:00", "end_time": "15:00", "priority": "high"},
    {"title": "팀플 회의", "category": "meeting", "start_time": "19:00", "end_time": "20:00", "priority": "high"}
  ],
  "todos": [{"title": "진료카드 챙기기", "priority": "high", "is_done": false}]
}
```

Response `data`:
```json
{
  "summary": "오늘은 오전 수업, 오후 병원 예약, 저녁 팀플 회의가 있습니다. 병원 예약 전에는 진료카드를 챙기고 이동 시간을 여유 있게 확보하는 것이 좋습니다.",
  "key_points": [
    "오후 2시 병원 예약이 가장 중요한 일정입니다.",
    "진료카드를 챙겨야 합니다.",
    "저녁에는 팀플 회의가 있습니다.",
    "오전에는 오전 수업이 있습니다."
  ],
  "priority_order": [
    {"title": "병원 예약", "priority": "high", "reason": "시간 고정 일정이며 준비물이 필요합니다."},
    {"title": "팀플 회의", "priority": "high", "reason": "협업 일정으로 지각하면 영향이 큽니다."},
    {"title": "오전 수업", "priority": "medium", "reason": "정해진 시간에 진행되는 수업 일정입니다."}
  ]
}
```

- `priority_order`는 모든 일정을 중요도(high→medium→low, 동급은 시간순)로 반환.
- 병원/회의/시험/마감/예약은 high로 보정. 미완료 high To-do는 key_points에 포함, 완료 To-do는 제외.
- 일정이 없어도 자연스러운 summary 반환. summary는 OpenAI 키 있으면 LLM(실패 시 템플릿).

---

## POST /api/v1/emotion/analyze — 감정 분석·생활 코칭 (비진단)

Request:
```json
{
  "input": "오늘 너무 피곤하고 아무것도 하기 싫어",
  "date": "2026-06-30",
  "recent_context": {"sleep_hours": 4.5, "schedule_count": 5, "todo_done_rate": 30}
}
```

Response `data`:
```json
{
  "sentiment": "negative",
  "emotion": "fatigue",
  "emotion_score": 0.88,
  "risk_level": "low",
  "coaching": "피로감이 높은 상태로 보입니다. 오늘은 저녁 일정 줄이고 수면 시간 확보하는 것을 추천합니다.",
  "recommended_actions": ["저녁 일정 줄이기", "수면 시간 확보하기", "가벼운 휴식하기"]
}
```

- emotion: fatigue | anxiety | sadness | anger | stress | positive | neutral. 키워드 없으면 neutral.
- 의학적 진단 아님. "~한 상태로 보입니다 / ~을 추천합니다"만 사용. 진단성 표현은 사용하지 않음.
- risk_level은 일반 감정에서 low/medium까지만. 자해/극단 신호 시에만 high + 전문가 상담 권유(고정 안전 메시지).

---

# 로컬 저장소 API (SQLite) — 일정 / 할 일 / 대시보드 / 알림

내부 SQLite 기반 CRUD. 외부 캘린더/구글 연동 없음. 모든 응답은 공통 envelope.
일정·할 일은 `PlannerItem` 공통 테이블 + `EventDetail`/`TodoDetail` 분리 구조에 매핑됩니다.

**계약 고정 사항(Flutter는 이 필드명을 그대로 사용):**
- `id`는 문자열(string), `priority`는 소문자 `low|medium|high`.
- 할 일은 `due_date`(마감일) + `completed`(bool) 사용.
- 알림 항목은 `{ "time": "HH:mm", "message": "..." }`.
- 예약 후보는 `reason`(string) + `conflict`(bool).

## POST /api/v1/local/schedules — 일정 생성

Request (예시):
```json
{ "title": "치과 예약", "date": "2026-07-03", "start_time": "14:00",
  "end_time": "15:00", "category": "hospital", "priority": "high", "location": "강남역 치과" }
```
Response `data`:
```json
{ "id": "d166...64", "title": "치과 예약", "date": "2026-07-03", "start_time": "14:00",
  "end_time": "15:00", "category": "hospital", "priority": "high", "location": "강남역 치과",
  "memo": null, "status": "scheduled", "source": "user", "travel_time_minutes": null,
  "created_at": "2026-06-30T12:52:57", "updated_at": "2026-06-30T12:52:57" }
```
- `end_time`/`location` 생략 가능. `end_time < start_time`이면 422(공통 envelope, `success=false`).
- 그 외: GET `/api/v1/local/schedules?date=&category=&priority=&status=` (목록, 시작시간 오름차순),
  GET·PATCH·DELETE `/api/v1/local/schedules/{id}` (없는 id는 404).

## POST /api/v1/local/schedules/from-draft — 파싱 결과로 일정 저장

Request:
```json
{ "schedule_draft": { "title": "치과 예약", "category": "hospital", "date": "2026-07-03",
  "start_time": "14:00", "end_time": "15:00", "location": "강남역 치과", "priority": "high", "source": "ai" },
  "intent": "create_schedule" }
```
- `/ai/schedule/parse` 응답의 `data.schedule_draft`를 그대로 넣으면 됩니다. Response는 일정 생성과 동일.

## POST /api/v1/local/todos — 할 일 생성

Request:
```json
{ "title": "자료 정리하기", "due_date": "2026-07-03", "priority": "medium", "category": "study" }
```
Response `data`:
```json
{ "id": "ab12...", "title": "자료 정리하기", "due_date": "2026-07-03", "priority": "medium",
  "completed": false, "category": "study", "memo": null, "status": "todo", "source": "user",
  "created_at": "...", "updated_at": "..." }
```
- 완료 토글: PATCH `/api/v1/local/todos/{id}` `{ "completed": true }`.
- 목록 GET `/api/v1/local/todos?due_date=&completed=&priority=&category=` (미완료→우선순위→마감 순).
- POST `/api/v1/local/todos/from-draft` `{ "schedule_draft": {...}, "intent": "create_todo" }` (draft의 `date`→`due_date` 매핑).

## GET /api/v1/dashboard/today — 오늘(특정 날짜) 일정/할 일 + 집계

Query: `date`(미지정 시 오늘), `current_datetime`(ISO8601, next_schedule 계산), `user_id`(선택).
Response `data`:
```json
{ "date": "2026-07-03",
  "schedules": [ /* ScheduleRead[], 시작시간 오름차순 */ ],
  "todos": [ /* TodoRead[], 미완료→우선순위→마감 순 */ ],
  "next_schedule": { /* ScheduleRead | null */ },
  "total_schedule_count": 1, "total_todo_count": 2,
  "completed_todo_count": 1, "todo_completion_rate": 0.5,
  "stats": { "schedule_count": 1, "todo_count": 2, "completed_todo_count": 1, "todo_completion_rate": 0.5 },
  "high_priority_items": [ { "type": "schedule", "id": "...", "title": "...", "priority": "high", "when": "2026-07-03" } ],
  "summary_message": "..." }
```
- `stats`는 홈 화면 편의용 묶음(추가 필드). 평탄 `total_*` 필드는 하위호환으로 유지.
- GET `/api/v1/dashboard/summary` 는 `schedules/todos` 배열 없이 `stats` 중심 요약.

## POST /api/v1/notifications/plan — 저장된 일정 기반 알림 계획

Request:
```json
{ "schedule_id": "<일정 id>", "notification_preference": "forgetful", "include_checklist": true, "persist": true }
```
Response `data`:
```json
{ "schedule_id": "<일정 id>", "user_id": null, "leave_time": "14:00",
  "checklist": [ { "item": "신분증", "reason": "병원 일정에 필요한 기본 준비물입니다." } ],
  "notifications": [ { "time": "13:30", "message": "치과 예약 시간이 다가옵니다..." } ],
  "source": "stored_schedule", "applied_preference": "forgetful",
  "applied_travel_minutes": 0, "applied_buffer_minutes": 0, "persisted_reminders": 4 }
```
- 알림 규칙(기본): `normal`=30·10분 전, `forgetful`=60·30·10분 전, `strong`은 더 촘촘, `late_prone`은 출발 전 추가.
- `persist=true`로 다시 호출해도 UNIQUE 충돌 없이 교체/유지(중복 안전).
- 조회: GET `/api/v1/notifications/plan/{schedule_id}` (없는 일정은 404).
