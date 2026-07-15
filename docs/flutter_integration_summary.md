# Flutter 연동 요약 문서

> AI Secretary 백엔드 — **실제 구현된 API 계약** 기준 요약.
> 상세 레퍼런스는 `docs/integration_guide.md`, `docs/api_spec.md` 참고.
> ⚠️ 과거 논의 단계의 예시 JSON이 아니라 **이 문서(=실제 구현)** 를 기준으로 연동하세요.

모든 응답은 공통 envelope를 따릅니다.

```json
{ "success": true, "message": "...", "data": { } }
```

- 먼저 `success`를 확인 → `data`에서 필드 사용. `message`는 사용자 안내용.
- 실패 시 `success=false`, HTTP 상태코드(404/422/500)로 구분. 없는 id는 **404 + 동일 envelope**(500 아님).
- 날짜 `"YYYY-MM-DD"`, 시간 `"HH:mm"`(24시간제).

---

## 1. Base URL

| 환경 | Base URL |
|------|----------|
| PC 로컬(같은 PC) | `http://127.0.0.1:8000` |
| Android Emulator | `http://10.0.2.2:8000` |
| 실제 기기(같은 Wi-Fi) | `http://{PC_IP}:8000` (예: `http://192.168.0.10:8000`) |
| Swagger | `http://127.0.0.1:8000/docs` |

- API prefix는 `/api/v1` (단, `/health` 제외).
- 실제 기기/에뮬레이터 연동 시 서버를 `--host 0.0.0.0`으로 실행.

---

## 2. 주요 API 호출 순서

### (A) 자연어 일정 생성 → 저장 → 대시보드 조회

```text
POST /api/v1/ai/schedule/parse        (input + current_datetime)
   → data.schedule_draft, data.intent("create_schedule"), data.missing_fields
POST /api/v1/local/schedules/from-draft   ({ "schedule_draft": <위 draft 그대로> })
   → data.id (string)
GET  /api/v1/dashboard/today?date=<draft.date>
   → data.schedules[] 에 방금 저장한 일정 포함
```

### (B) To-do 생성 → 저장 → 대시보드 조회

```text
POST /api/v1/ai/schedule/parse        (할 일 성격 문장)
   → data.schedule_draft, data.intent
POST /api/v1/local/todos/from-draft   ({ "schedule_draft": <draft>, "intent": "create_todo" })
   → data.id (string), data.due_date, data.completed=false
GET  /api/v1/dashboard/today?date=<draft.date>
   → data.todos[] 에 포함
```

> 직접 입력 폼이면 parse를 건너뛰고 `POST /api/v1/local/todos`로 바로 생성해도 됩니다.

### (C) 예약 후보 추천 → 후보 선택 → 일정 저장

```text
POST /api/v1/reservations/candidates/from-store   (target_date + 시간창)
   → data.recommended_candidates[]  (겹치는 시간은 제외, data.rejected_slots[]로 보고)
사용자가 후보 1개 선택
   → schedule_draft 로 변환 (start_time/end_time = 선택 후보 값)
POST /api/v1/local/schedules/from-draft
   → data.id
GET  /api/v1/dashboard/today  로 확인
```

### (D) 알림 계획 생성 → 알림 조회

```text
POST /api/v1/notifications/plan   ({ "schedule_id": <저장된 일정 id>, "notification_preference": "...", "persist": true })
   → data.notifications[] = [{ "time": "HH:mm", "message": "..." }]
GET  /api/v1/notifications/plan/{schedule_id}
   → 동일 구조로 재조회
```

---

## 3. 실제 필드명 주의사항 (계약 고정)

| 항목 | 실제 계약 | 흔한 착각 (쓰면 안 됨) |
|------|-----------|------------------------|
| parse 요청 본문 키 | **`input`** | ~~`text`~~ |
| 일정/할 일 `id` | **string** | ~~int~~ |
| `priority` | **`low` / `medium` / `high`** (소문자) | ~~`HIGH`/`MEDIUM`~~ |
| To-do 마감/완료 | **`due_date`, `completed`(bool)** | ~~`date`/`due_time`/`is_completed`~~ |
| 예약 후보 사유 | **`reason`(string), `conflict`(bool)** | ~~`reason_codes` 배열~~ |
| 일정/할 일 구분 | **`intent`** (`create_schedule`/`create_todo`) | ~~`item_type`~~ |
| 알림 항목 | **`{ "time": "HH:mm", "message": "..." }`** | ~~`notify_at`/`type`~~ |
| 알림 조회 | **`GET /api/v1/notifications/plan/{schedule_id}`** (path 파라미터) | ~~쿼리스트링 방식~~ |

---

## 4. API별 Flutter 요청/응답 예시

> 예시 값은 실제 응답 형태 기준입니다. `id`/타임스탬프는 서버 생성값.

### 4-1. `POST /api/v1/ai/schedule/parse` — 자연어 파싱

**요청**
```json
{
  "input": "내일 오후 2시에 치과 예약 잡아줘",
  "current_datetime": "2026-07-02T10:00:00+09:00",
  "timezone": "Asia/Seoul"
}
```

**응답 `data`**
```json
{
  "intent": "create_schedule",
  "confidence": 0.94,
  "slots": {
    "title": "치과",
    "date_expression": "내일",
    "time_expression": "오후 2시",
    "date": "2026-07-03",
    "start_time": "14:00",
    "end_time": "15:00",
    "category": "hospital",
    "location": null
  },
  "schedule_draft": {
    "title": "치과",
    "category": "hospital",
    "date": "2026-07-03",
    "start_time": "14:00",
    "end_time": "15:00",
    "location": null,
    "memo": null,
    "priority": "high",
    "source": "ai"
  },
  "missing_fields": []
}
```

- `intent`로 일정/할 일 분기. `missing_fields`가 비어 있으면 바로 저장 가능.
- `schedule_draft`를 **그대로** 다음 from-draft 요청의 `schedule_draft`에 넣으면 됨(키 호환).

### 4-2. `POST /api/v1/local/schedules/from-draft` — 일정 저장

**요청**
```json
{
  "schedule_draft": {
    "title": "치과 예약",
    "category": "hospital",
    "date": "2026-07-03",
    "start_time": "14:00",
    "end_time": "15:00",
    "location": "강남역 치과",
    "priority": "high",
    "source": "ai"
  },
  "intent": "create_schedule"
}
```

**응답 `data`**
```json
{
  "id": "d166209557254601a584ce24e46c6a64",
  "title": "치과 예약",
  "date": "2026-07-03",
  "start_time": "14:00",
  "end_time": "15:00",
  "category": "hospital",
  "priority": "high",
  "location": "강남역 치과",
  "memo": null,
  "status": "scheduled",
  "source": "ai",
  "travel_time_minutes": null,
  "created_at": "2026-06-30T12:52:57",
  "updated_at": "2026-06-30T12:52:57"
}
```

- `id`는 **문자열**. 이후 알림 계획 등에서 `schedule_id`로 사용.
- `start_time`만 있고 `end_time`이 없으면 종일성 일정으로 저장 가능. `end_time < start_time`이면 422.

### 4-3. `POST /api/v1/local/todos/from-draft` — 할 일 저장

**요청**
```json
{
  "schedule_draft": {
    "title": "장보기",
    "category": "etc",
    "date": "2026-07-03",
    "priority": "medium",
    "source": "ai"
  },
  "intent": "create_todo"
}
```

**응답 `data`**
```json
{
  "id": "ab12cd34ef56...",
  "title": "장보기",
  "due_date": "2026-07-03",
  "priority": "medium",
  "completed": false,
  "category": "etc",
  "memo": null,
  "status": "todo",
  "source": "ai",
  "created_at": "2026-06-30T12:52:57",
  "updated_at": "2026-06-30T12:52:57"
}
```

- draft의 `date`가 To-do의 **`due_date`** 로 매핑됨.
- 완료 토글: `PATCH /api/v1/local/todos/{id}` 본문 `{ "completed": true }`.

### 4-4. `GET /api/v1/dashboard/today` — 오늘(특정 날짜) 조회

**요청** (쿼리스트링)
```
GET /api/v1/dashboard/today?date=2026-07-03&current_datetime=2026-07-03T09:00:00%2B09:00
```

**응답 `data`**
```json
{
  "date": "2026-07-03",
  "schedules": [
    {
      "id": "d166...64", "title": "치과 예약", "date": "2026-07-03",
      "start_time": "14:00", "end_time": "15:00", "category": "hospital",
      "priority": "high", "location": "강남역 치과", "memo": null,
      "status": "scheduled", "source": "ai", "travel_time_minutes": null,
      "created_at": "...", "updated_at": "..."
    }
  ],
  "todos": [
    {
      "id": "ab12...", "title": "장보기", "due_date": "2026-07-03",
      "priority": "medium", "completed": false, "category": "etc",
      "memo": null, "status": "todo", "source": "ai",
      "created_at": "...", "updated_at": "..."
    }
  ],
  "next_schedule": { "id": "d166...64", "title": "치과 예약", "start_time": "14:00", "...": "..." },
  "total_schedule_count": 1,
  "total_todo_count": 1,
  "completed_todo_count": 0,
  "todo_completion_rate": 0.0,
  "stats": {
    "schedule_count": 1,
    "todo_count": 1,
    "completed_todo_count": 0,
    "todo_completion_rate": 0.0
  },
  "high_priority_items": [
    { "type": "schedule", "id": "d166...64", "title": "치과 예약", "priority": "high", "when": "2026-07-03" }
  ],
  "summary_message": "2026-07-03 기준 일정 1건, 할 일 1건 ..."
}
```

- 홈 화면 집계는 `data.stats` 한 객체로 바로 사용 권장.
- `total_*` 평탄 필드도 동일 값으로 유지(하위호환). `schedules`는 시작시간 오름차순, `todos`는 미완료→우선순위→마감 순.

### 4-5. `POST /api/v1/reservations/candidates/from-store` — 저장 일정 기반 예약 후보

**요청**
```json
{
  "target_date": "2026-07-03",
  "duration_minutes": 60,
  "preferred_start_time": "13:00",
  "preferred_end_time": "18:00",
  "category": "beauty"
}
```

**응답 `data`**
```json
{
  "target_date": "2026-07-03",
  "recommended_candidates": [
    {
      "candidate_id": "cand_001",
      "start_time": "13:00",
      "end_time": "14:00",
      "score": 85,
      "reason": "선호 시간대 내 빈 시간으로 예약 소요 시간 60분을 만족합니다.",
      "conflict": false
    }
  ],
  "rejected_slots": [
    { "start_time": "14:00", "end_time": "15:00", "reason": "치과 예약과 시간이 겹칩니다." }
  ]
}
```

- 기존 일정과 겹치는 시간은 후보에서 제외되고 `rejected_slots`로 사유와 함께 반환.
- 후보를 선택하면 아래처럼 `schedule_draft`로 변환해 `POST /api/v1/local/schedules/from-draft` 호출:

```json
{
  "schedule_draft": {
    "title": "미용실 예약",
    "date": "2026-07-03",
    "start_time": "13:00",
    "end_time": "14:00",
    "category": "beauty",
    "priority": "medium"
  }
}
```

> 외부 입력 일정 배열로 후보를 받고 싶으면 `POST /api/v1/reservations/candidates`(body에 `constraints` + `existing_schedules[]`)를 사용. 응답 구조는 동일.

### 4-6. `POST /api/v1/notifications/plan` — 알림 계획 생성

**요청**
```json
{
  "schedule_id": "d166209557254601a584ce24e46c6a64",
  "notification_preference": "forgetful",
  "include_checklist": true,
  "persist": true
}
```

**응답 `data`**
```json
{
  "schedule_id": "d166209557254601a584ce24e46c6a64",
  "user_id": null,
  "leave_time": "14:00",
  "checklist": [
    { "item": "신분증", "reason": "병원 일정에 필요한 기본 준비물입니다." }
  ],
  "notifications": [
    { "time": "13:00", "message": "치과 예약 준비를 시작할 시간입니다. ..." },
    { "time": "13:30", "message": "치과 예약 시간이 다가옵니다. ..." }
  ],
  "source": "stored_schedule",
  "applied_preference": "forgetful",
  "applied_travel_minutes": 0,
  "applied_buffer_minutes": 0,
  "persisted_reminders": 4
}
```

- `notification_preference`: `normal`(30·10분 전) / `forgetful`(60·30·10분 전) / `strong`(더 촘촘) / `late_prone`(출발 전 추가).
- `persist=true`로 다시 호출해도 **UNIQUE 충돌 없이** 교체/유지(중복 안전).
- 알림 항목은 `{ "time": "HH:mm", "message": "..." }` 형태.

### 4-7. `GET /api/v1/notifications/plan/{schedule_id}` — 알림 계획 조회

**요청** (path 파라미터)
```
GET /api/v1/notifications/plan/d166209557254601a584ce24e46c6a64
```

**응답 `data`** — 4-6과 동일 구조. (조회만 시 `persist` 기본 false → `persisted_reminders: 0`)
없는 일정 id면 **404 + 공통 envelope**.

---

## 5. Flutter 개발자가 조심해야 할 점

- **`id`를 int로 파싱하지 마세요.** 항상 `String`으로 다루세요(해시형 문자열).
- **`priority` 대소문자 주의.** 비교/매핑은 소문자 `low|medium|high` 기준.
- **To-do 완료/마감 필드명 주의.** `completed`(bool), `due_date` 사용. `is_completed`/`due_time` 아님.
- **예약 후보는 `reason`(문자열) + `conflict`(bool).** `reason_codes` 배열이 아님.
- **일정/할 일 구분은 `intent`** 로 판단. `item_type` 필드는 없음.
- **알림 조회는 path 파라미터** `GET /notifications/plan/{schedule_id}`.
- 빈 결과(예: 예약 후보 없음)는 오류가 아니라 `success=true` + 빈 배열. `message`로 안내.
- 모르는 필드는 무시하도록 구현(필드는 추가될 수 있어도 이름은 바뀌지 않음).
- **과거 논의용 예시 JSON이 아니라 `docs/integration_guide.md`(및 이 문서) 기준으로 연동하세요.**

---

## 6. Swagger로 즉시 테스트

- `http://127.0.0.1:8000/docs` 접속 → 주요 요청 스키마에 예시가 채워져 있어 **“Try it out” → “Execute”** 만으로 호출 가능.
- 권장 순서: `POST /local/schedules`로 일정 생성 → 응답 `data.id` 복사 → `POST /notifications/plan`의 `schedule_id`에 붙여넣기.
