# Integration Guide — 프론트엔드(Flutter) 연동

## 1. 서버 주소 (환경별)

| 환경 | Base URL |
|------|----------|
| PC 로컬(같은 PC) | `http://127.0.0.1:8000` |
| Android Emulator | `http://10.0.2.2:8000` |
| 실제 기기(같은 Wi-Fi) | `http://{PC_IP}:8000` (예: `http://192.168.0.10:8000`) |
| Swagger 문서 | `http://127.0.0.1:8000/docs` |

- 실제 기기/에뮬레이터에서 접속하려면 서버를 `--host 0.0.0.0`으로 실행하세요.
- `{PC_IP}`는 서버 PC의 LAN IP (Windows `ipconfig`, mac/linux `ifconfig`/`ip addr`).
- CORS는 개발 기본값으로 모든 origin 허용(`CORS_ORIGINS=*`).

## 2. 공통 응답 구조

모든 응답은 동일한 envelope입니다.

```json
{ "success": true, "message": "...", "data": { } }
```

권장 처리: `success`가 true인지 먼저 확인 → `data`에서 필요한 필드 사용. `message`는 사용자 안내/토스트에 활용.
오류 시 `success=false`이고 HTTP 상태코드(404/422/500 등)로 구분됩니다.

## 3. 엔드포인트 & 프론트 핵심 필드

| 기능 | Method · Path | 프론트가 읽는 핵심 필드 |
|------|---------------|------------------------|
| 일정 생성(파싱) | POST `/api/v1/ai/schedule/parse` | `data.schedule_draft` (title/category/date/start_time/end_time/priority), `data.missing_fields` |
| 예약 후보 | POST `/api/v1/reservations/candidates` | `data.recommended_candidates[]` (candidate_id/start_time/end_time/score), `data.rejected_slots[]` |
| 예약 메시지 | POST `/api/v1/messages/reservation` | `data.generated_message`, `data.alternatives[]` |
| 준비물·출발 알림 | POST `/api/v1/alerts/departure-plan` | `data.leave_time`, `data.checklist[]`, `data.notifications[]` |
| 하루 브리핑 | POST `/api/v1/briefings/daily` | `data.summary`, `data.key_points[]`, `data.priority_order[]` |
| 감정 코칭 | POST `/api/v1/emotion/analyze` | `data.emotion`, `data.coaching`, `data.recommended_actions[]` |
| 헬스 체크 | GET `/health` | `data.status == "ok"` |

요청/응답의 상세 예시는 `docs/api_spec.md`와 `mock/*.json`을 참고하세요. (mock은 실제 응답과 동일 구조)

## 4. 날짜·시간 규약

- 날짜: `"YYYY-MM-DD"` (예: `"2026-06-30"`)
- 시간: `"HH:mm"` 24시간제 (예: `"14:00"`)
- 상대 표현 해석을 위해 일정 파싱 요청에는 `current_datetime`(ISO8601)을 함께 보내세요.

## 5. 로컬 저장소(SQLite) — 일정 / 할 일 / 대시보드 / 알림

내부 SQLite에 저장되는 CRUD 엔드포인트입니다. (외부 캘린더/구글 연동 없음)

| 기능 | Method · Path | 프론트가 읽는 핵심 필드 |
|------|---------------|------------------------|
| 일정 생성 | POST `/api/v1/local/schedules` | `data.id`, `data.title`, `data.date`, `data.start_time`, `data.end_time`, `data.priority`, `data.status` |
| 일정 목록 | GET `/api/v1/local/schedules?date=&category=&priority=&status=` | `data[]` (시작시간 오름차순) |
| 일정 단건 | GET `/api/v1/local/schedules/{id}` | `data` (없으면 404) |
| 일정 수정 | PATCH `/api/v1/local/schedules/{id}` | 보낸 필드만 갱신 |
| 일정 삭제 | DELETE `/api/v1/local/schedules/{id}` | `data.deleted == true` |
| 일정 저장(파싱결과) | POST `/api/v1/local/schedules/from-draft` | body: `{ "schedule_draft": {...} }` → `data` (저장된 일정) |
| 할 일 생성 | POST `/api/v1/local/todos` | `data.id`, `data.title`, `data.due_date`, `data.priority`, `data.completed` |
| 할 일 목록 | GET `/api/v1/local/todos?due_date=&completed=&priority=&category=` | `data[]` (미완료→우선순위→마감 순) |
| 할 일 단건/수정/삭제 | GET·PATCH·DELETE `/api/v1/local/todos/{id}` | 일정과 동일 패턴 |
| 할 일 저장(파싱결과) | POST `/api/v1/local/todos/from-draft` | body: `{ "schedule_draft": {...}, "intent": "create_todo" }` |
| 오늘 대시보드 | GET `/api/v1/dashboard/today?date=&current_datetime=&user_id=` | `data.date`, `data.schedules[]`, `data.todos[]`, `data.stats`, `data.next_schedule`, `data.high_priority_items[]` |
| 대시보드 요약 | GET `/api/v1/dashboard/summary` | `data.stats`, `data.next_schedule`, `data.summary_message` |
| 알림 계획 생성 | POST `/api/v1/notifications/plan` | body: `{ "schedule_id", "notification_preference", "persist" }` → `data.notifications[]`, `data.checklist[]`, `data.leave_time` |
| 알림 계획 조회 | GET `/api/v1/notifications/plan/{schedule_id}` | 위와 동일 |

### 대시보드 `stats` 블록 (홈 화면 권장)

```json
"stats": {
  "schedule_count": 1,
  "todo_count": 2,
  "completed_todo_count": 1,
  "todo_completion_rate": 0.5
}
```

> `stats`는 홈 화면 편의용으로 추가된 묶음이며, 기존 평탄 필드(`total_schedule_count`, `total_todo_count`, `completed_todo_count`, `todo_completion_rate`)도 하위호환을 위해 그대로 유지됩니다.

## 6. 핵심 저장 흐름 (호출 순서)

### (A) 자연어 → 일정/할 일 저장

```text
1) POST /api/v1/ai/schedule/parse   { "input": "내일 오후 2시 치과 예약", "current_datetime": "<ISO8601>" }
   → data.schedule_draft  (title/category/date/start_time/end_time/location/priority/source)
   → data.intent          ("create_schedule" | "create_todo" | ...)  ← 일정/할 일 분기용
   → data.missing_fields  (비어있으면 바로 저장 가능)
2) 일정이면 POST /api/v1/local/schedules/from-draft  { "schedule_draft": <위 draft 그대로> }
   할 일이면 POST /api/v1/local/todos/from-draft      { "schedule_draft": <draft>, "intent": "create_todo" }
3) GET /api/v1/dashboard/today?date=<draft.date> 에서 즉시 조회됨
```

> `schedule_draft`는 parse 응답을 **그대로** from-draft 요청의 `schedule_draft`에 넣으면 됩니다(키 호환). EVENT/TODO 구분은 `intent`로 판단하세요.

### (B) 예약 후보 → 일정 저장

```text
1) POST /api/v1/reservations/candidates 또는 /candidates/from-store
   → data.recommended_candidates[]  (candidate_id / start_time / end_time / score / reason / conflict)
   → data.rejected_slots[]          (겹치는 시간은 여기로, 후보에서 제외됨)
2) 사용자가 후보 1개 선택 → schedule_draft 로 변환:
   { "title": "...", "date": "<target_date>", "start_time": <후보.start_time>,
     "end_time": <후보.end_time>, "category": "...", "priority": "medium" }
3) POST /api/v1/local/schedules/from-draft  → 일정 저장
4) GET /api/v1/dashboard/today 에서 조회
```

### (C) 알림 계획 생성/조회

```text
1) POST /api/v1/notifications/plan  { "schedule_id": <저장된 일정 id>,
     "notification_preference": "normal|strong|forgetful|late_prone", "persist": true }
   → data.notifications[] = [{ "time": "HH:mm", "message": "..." }]
   → data.checklist[]     = [{ "item": "...", "reason": "..." }]
2) GET /api/v1/notifications/plan/{schedule_id} 로 재조회
   (persist=true 로 다시 호출해도 UNIQUE 충돌 없이 교체/유지됩니다)
```

### Flutter 연동 주의사항

알림 조회 API는 다음 경로를 사용합니다.

```text
GET /api/v1/notifications/plan/{schedule_id}
```

예를 들어 schedule_id가 `abc-123`이면 Flutter에서는 다음 URL로 호출합니다.

```text
/api/v1/notifications/plan/abc-123
```

`GET /api/v1/notifications/plan?schedule_id=abc-123` 방식이 아닙니다.

## 7. 주의할 필드명 (계약 고정)

Flutter는 아래 **실제 필드명**을 그대로 사용하세요.

- 일정/할 일 `id`는 **문자열(string)** 입니다 (정수 아님).
- `priority`는 소문자 `"low" | "medium" | "high"` 입니다.
- 할 일은 `due_date`(마감일)와 `completed`(bool)를 씁니다. (`due_time`/`is_completed` 아님)
- 알림 항목은 `{ "time": "HH:mm", "message": "..." }` 형태입니다. (`notify_at`/`type` 아님)
- 예약 후보는 단일 `reason`(string) + `conflict`(bool)를 씁니다. (`reason_codes` 배열 아님)
- parse 응답은 `intent`로 EVENT/TODO를 구분합니다. (`item_type` 필드는 없음)

## 8. Swagger로 바로 테스트

- 문서: `http://127.0.0.1:8000/docs`
- 주요 요청 스키마에 예시가 채워져 있어 **“Try it out” → “Execute”** 만으로 호출됩니다.
- 권장 순서: `local/schedules` 생성 → 반환된 `data.id` 복사 → `notifications/plan`의 `schedule_id`에 붙여넣기.

## 9. 연동 팁

- 필드는 **추가될 수는 있어도 이름은 바뀌지 않습니다**. 파싱 시 모르는 필드는 무시하도록 구현하세요.
- 빈 결과(예: 예약 후보 없음)는 오류가 아니라 `success=true` + 빈 배열입니다. message로 사용자 안내.
- 감정 코칭은 의학적 진단이 아니며, 위험 신호 시 `risk_level: "high"`와 전문가 상담 권유 메시지가 옵니다.
- 로컬 개발 시 mock JSON으로 UI를 먼저 붙이고, 동일 구조의 실제 API로 교체하면 됩니다.
- 없는 `id` 조회 시 서버는 **404 + 공통 envelope**(`success=false`)를 반환하며 절대 500을 내지 않습니다.
