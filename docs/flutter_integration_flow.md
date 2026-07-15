# Flutter 연동 흐름: 자연어 → 저장 → 대시보드

Flutter 앱에서 쓰는 핵심 흐름입니다.

```
자연어 입력
  → POST /api/v1/ai/schedule/parse/enhanced   (파싱)
  → POST /api/v1/ai/schedule/confirm           (저장: EVENT→일정 / TODO→할 일)
  → GET  /api/v1/dashboard/today?date=...       (반영 확인)
```

모든 응답은 공통 envelope `{ "success": bool, "message": str, "data": ... }` 를 따릅니다.
`data` 안의 필드명만 화면에 바인딩하면 됩니다.

날짜는 항상 `YYYY-MM-DD`, 시간은 `HH:MM` 문자열입니다. 테스트/디버깅 시 `today`
를 주입하면 상대 날짜(`오늘`, `내일`, `이번 주 금요일` 등)가 그 기준으로 계산됩니다.
실제 앱에서는 `today`를 생략하고 `timezone`(기본 `Asia/Seoul`)만 보내면 서버가
해당 시간대의 오늘을 기준으로 계산합니다.

---

## 1) 파싱 — POST /api/v1/ai/schedule/parse/enhanced

요청:

```json
{
  "text": "오늘 오후 3시에 병원 예약 있어",
  "today": "2026-07-01",
  "timezone": "Asia/Seoul",
  "use_llm": false
}
```

응답(`data` 일부):

```json
{
  "original_text": "오늘 오후 3시에 병원 예약 있어",
  "title": "병원 예약",
  "date": "2026-07-01",
  "start_time": "15:00",
  "end_time": "16:00",
  "category": "health",
  "is_all_day": false,
  "item_type": "EVENT",
  "parse_source": "rule_fallback",
  "timezone": "Asia/Seoul",
  "base_date": "2026-07-01",
  "warnings": [],
  "needs_clarification": false,
  "clarification_questions": [],
  "missing_fields": []
}
```

- `item_type`: `EVENT`(일정) 또는 `TODO`(할 일). 다음 단계 분기에 사용합니다.
- `needs_clarification` / `clarification_questions` / `missing_fields`: 정보가
  부족할 때 사용자에게 되물을 문구를 담습니다. 비어 있으면 바로 저장 가능합니다.
- `use_llm`은 키가 없거나 실패해도 규칙 기반으로 안전하게 폴백합니다(500 없음).

할 일 예시 입력 `"오늘까지 과제 제출해야 해"` → `item_type: "TODO"`,
`title: "과제 제출"`, `date: "2026-07-01"`.

---

## 2) 저장(confirm) — POST /api/v1/ai/schedule/confirm

파싱 결과를 사용자가 확인한 뒤 그대로 `parsed`에 담아 보냅니다. `item_type`으로
일정/할 일을 분기합니다(요청 최상위 `item_type` 또는 `parsed.item_type`).

### 일정(EVENT)

요청:

```json
{
  "user_id": "local-user",
  "item_type": "EVENT",
  "parsed": {
    "title": "병원 예약",
    "date": "2026-07-01",
    "start_time": "15:00",
    "category": "health",
    "is_all_day": false,
    "item_type": "EVENT"
  }
}
```

응답:

```json
{
  "success": true,
  "message": "일정을 저장했습니다.",
  "data": { "schedule": { "id": "…", "title": "병원 예약", "date": "2026-07-01",
                          "start_time": "15:00", "category": "health", "status": "scheduled" } }
}
```

### 할 일(TODO)

요청:

```json
{
  "user_id": "local-user",
  "item_type": "TODO",
  "parsed": { "title": "과제 제출", "date": "2026-07-01", "category": "study", "item_type": "TODO" }
}
```

응답:

```json
{
  "success": true,
  "message": "할 일을 저장했습니다.",
  "data": { "todo": { "id": "…", "title": "과제 제출", "due_date": "2026-07-01",
                      "category": "study", "completed": false } }
}
```

### 검증 규칙 (실패 시 500이 아니라 422)

- `title` 필수.
- 일정: `date` 필수. 종일(`is_all_day: true`)이 아니면 `start_time` 필수.
  종일 일정은 `start_time` 없이 저장됩니다.
- 할 일: `title`과 `date`(→ `due_date`) 필수. 저장 시 `completed`는 `false`.
- 시간 형식이 잘못되면 422.

> 참고: 현재 MVP에서 `user_id`는 단일 로컬 사용자(`local-user`)로 저장됩니다.

---

## 3) 대시보드 — GET /api/v1/dashboard/today

```
GET /api/v1/dashboard/today?date=2026-07-01&user_id=local-user
```

응답(`data` 일부):

```json
{
  "date": "2026-07-01",
  "schedules": [ { "id": "…", "title": "병원 예약", "date": "2026-07-01",
                   "start_time": "15:00", "end_time": "16:00", "category": "health",
                   "priority": "medium", "status": "scheduled" } ],
  "todos": [ { "id": "…", "title": "과제 제출", "due_date": "2026-07-01",
               "category": "study", "completed": false, "priority": "medium",
               "status": "scheduled" } ],
  "next_schedule": { … },
  "total_schedule_count": 1,
  "total_todo_count": 1,
  "completed_todo_count": 0,
  "todo_completion_rate": 0.0,
  "stats": { "schedule_count": 1, "todo_count": 1,
             "completed_todo_count": 0, "todo_completion_rate": 0.0 },
  "high_priority_items": [ … ],
  "summary_message": "…"
}
```

- 일정은 `schedules`, 할 일은 `todos`로 분리되어 내려옵니다.
- 일정 필터 기준: `date == schedule.date`. 할 일 필터 기준: `date == todo.due_date`.
- 데이터가 없으면 빈 배열(`[]`)을 반환합니다(500 없음). 잘못된 `date`나 `user_id`
  누락도 안전하게 처리되어 빈 결과를 돌려줍니다.

---

## Flutter에서 주의할 필드명

- 파싱 결과는 **평면(flat)** 구조입니다: `title`, `date`, `start_time`, `category`,
  `item_type`. (기존 `/ai/schedule/parse`의 중첩 `slots`/`schedule_draft`와 다릅니다.)
- 저장 응답은 `data.schedule`(일정) 또는 `data.todo`(할 일)로 감싸여 옵니다.
- 대시보드에서 일정은 `schedules[].date` + `start_time`, 할 일은 `todos[].due_date`
  + `completed`를 사용합니다. 완료 여부는 `completed`(불리언)입니다.
- 날짜 기준이 파싱(`today`/`base_date`) → 저장(`date`/`due_date`) → 대시보드(`date`)
  전 구간에서 동일하게 유지됩니다.
```
