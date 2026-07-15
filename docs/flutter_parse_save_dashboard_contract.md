# Flutter 연동 계약: parse → confirm → dashboard/today

이 문서는 Flutter 앱이 의존하는 **API 계약(필드명·응답 wrapper·상태코드)** 을 고정합니다.
계약은 `tests/test_flutter_contract_parse_save_dashboard.py` 로 회귀 검증됩니다.

전체 흐름:

```
자연어 입력
  → POST /api/v1/ai/schedule/parse/enhanced   (파싱, 평면 data)
  → (needs_clarification 확인 → 필요 시 되묻기)
  → POST /api/v1/ai/schedule/confirm           (item_type: EVENT→일정 / TODO→할 일)
  → GET  /api/v1/dashboard/today?date=...       (반영 확인)
```

모든 응답은 공통 envelope `{ "success": bool, "message": str, "data": ... }` 를 따릅니다.
날짜는 `YYYY-MM-DD`, 시간은 `HH:MM` 문자열입니다.

---

## 1. Enhanced Parse — `POST /api/v1/ai/schedule/parse/enhanced`

요청:

```json
{ "text": "오늘 오후 3시에 병원 예약 있어", "today": "2026-07-01", "timezone": "Asia/Seoul", "use_llm": false }
```

응답 `data` (항상 **평면 구조**, 필드는 값이 없어도 `null`/`[]`로 유지):

```json
{
  "original_text": "오늘 오후 3시에 병원 예약 있어",
  "title": "병원 예약",
  "date": "2026-07-01",
  "start_time": "15:00",
  "end_time": null,
  "category": "health",
  "item_type": "EVENT",
  "location": null,
  "memo": null,
  "is_all_day": false,
  "confidence": 0.86,
  "parse_source": "rule_fallback",
  "timezone": "Asia/Seoul",
  "base_date": "2026-07-01",
  "warnings": [],
  "needs_clarification": false,
  "missing_fields": [],
  "clarification_questions": []
}
```

- `item_type` 은 `"EVENT"` 또는 `"TODO"`. (기존 `/ai/schedule/parse` 의 중첩 `slots`/`schedule_draft` 구조와 다릅니다. enhanced 는 별도 매핑하세요.)
- `today` 를 생략하면 서버가 `timezone` 기준 오늘을 `base_date` 로 계산합니다.

---

## 2. Confirm 저장 — `POST /api/v1/ai/schedule/confirm`

`item_type` 으로 분기하며(요청 최상위 `item_type` 우선, 없으면 `parsed.item_type`, 그래도 없으면 `EVENT`),
성공 응답 wrapper 는 EVENT=`data.schedule`, TODO=`data.todo` 로 **고정**됩니다.

### EVENT

요청:

```json
{ "user_id": "local-user",
  "parsed": { "title": "병원 예약", "date": "2026-07-01", "start_time": "15:00",
              "category": "health", "item_type": "EVENT", "is_all_day": false } }
```

응답:

```json
{ "success": true, "message": "일정을 저장했습니다.",
  "data": { "schedule": { "id": "…", "title": "병원 예약", "date": "2026-07-01",
                          "start_time": "15:00", "end_time": null, "category": "health",
                          "location": null, "memo": null } } }
```

### TODO

요청:

```json
{ "user_id": "local-user",
  "parsed": { "title": "과제 제출", "date": "2026-07-01", "category": "study", "item_type": "TODO" } }
```

응답:

```json
{ "success": true, "message": "할 일을 저장했습니다.",
  "data": { "todo": { "id": "…", "title": "과제 제출", "due_date": "2026-07-01",
                      "category": "study", "completed": false } } }
```

> TODO 는 `parsed.date` 가 `due_date` 로 매핑되고, 저장 시 `completed=false` 입니다.

### 검증 실패 = `422` (500 아님)

- 공통: `item_type` 이 EVENT/TODO 가 아니면 422.
- EVENT: `title` 없음 / `date` 없음 / (`is_all_day=false` 인데 `start_time` 없음) / `date`·`start_time` 형식 오류 → 422. `is_all_day=true` 는 `start_time` 없이 저장 가능.
- TODO: `title` 없음 / `date`(→`due_date`) 없음 / `date` 형식 오류 → 422.
- 에러 응답도 공통 envelope(`success=false`, `message` 에 사유)입니다.
- **`needs_clarification=true` 인 parsed 를 그대로 confirm 하면 422** 로 거절됩니다(필수 필드 누락이므로).

---

## 3. Dashboard — `GET /api/v1/dashboard/today`

> 경로는 기존 계약인 `/dashboard/today` 를 유지합니다. `GET /dashboard`(bare) 는 만들지 않습니다.

```
GET /api/v1/dashboard/today?date=2026-07-01&user_id=local-user
```

응답 `data` (일정/할 일 분리):

```json
{
  "date": "2026-07-01",
  "schedules": [ { "id": "…", "title": "병원 예약", "date": "2026-07-01",
                   "start_time": "15:00", "end_time": null, "category": "health" } ],
  "todos": [ { "id": "…", "title": "과제 제출", "due_date": "2026-07-01",
               "category": "study", "completed": false } ],
  "next_schedule": null,
  "total_schedule_count": 1,
  "total_todo_count": 1,
  "completed_todo_count": 0,
  "todo_completion_rate": 0.0,
  "stats": { "schedule_count": 1, "todo_count": 1, "completed_todo_count": 0, "todo_completion_rate": 0.0 },
  "high_priority_items": [],
  "summary_message": "…"
}
```

- 일정 필터: `date == schedule.date`. 할 일 필터: `date == todo.due_date`.
- 일정 사용 필드: `id, title, date, start_time, end_time, category`.
- 할 일 사용 필드: `id, title, due_date, category, completed`.
- 데이터 없음/잘못된 `date`/`user_id` 누락 → 빈 배열 반환(500 없음). 저장 직후 조회 시 반영됩니다.

---

## 4. Clarification UX 처리

Flutter 처리 순서:

```
1. needs_clarification 확인
2. missing_fields 확인
3. clarification_questions 표시
4. 사용자 입력으로 parsed 보완
5. confirm 호출
```

규칙(계약):

- `date` 없음 → `missing_fields` 에 `"date"`, 질문 "언제 일정으로 등록할까요?"
- EVENT + `is_all_day=false` + `start_time` 없음 → `"start_time"`, "몇 시에 시작하는 일정인가요?"
- `title` 없음 → `"title"`, "일정 제목을 무엇으로 할까요?"
- `location` 없음은 `missing_fields` 에 넣지 않음. `category=other` 는 저장 차단 사유 아님.
- `missing_fields` 가 비어있지 않으면 `needs_clarification=true`, 비어있으면 `false`.
- `clarification_questions` 개수는 `missing_fields` 개수와 1:1 대응.

`422` 는 앱 에러가 아니라 **"입력 보완 필요"** 상태로 처리하세요.

---

## 5. item_type 감지 정책 (MVP 한계)

키워드 기반이며 **EVENT 신호가 TODO 신호보다 우선**, 신호가 없으면 **EVENT 기본** 입니다.

- TODO 키워드 예: `해야 해`, `해야돼`, `해야 함`, `제출`, `완료`, `마감`, `까지`, `할 일`, `할일`, `작성`, `정리`, `준비`
- EVENT 키워드 예: `예약`, `회의`, `약속`, `미팅`, `방문`, `진료`, `병원`, `치과`, `수업`, `알림`
- 모호한 문장(신호 없음)은 `EVENT` 로 분류됩니다.

정의 위치: `backend/services/schedule_parse_service.py` 의 `_EVENT_SIGNALS`/`_TODO_SIGNALS`.
(레거시 `/ai/schedule/parse` 의 intent 분류기와 독립적으로 유지합니다.)

---

## 6. MVP 한계

1. `confirm` 의 `user_id` 는 값이 와도 **단일 로컬 소유자 `local-user`** 로 저장됩니다(멀티유저/인증 미도입).
2. 저장 datetime 은 **naive** 이며, `timezone` 은 `base_date` 계산에만 반영되고 저장 값 변환에는 쓰이지 않습니다.
3. `item_type` 감지는 규칙 키워드 기반이고 모호하면 EVENT 로 처리합니다.
4. 대시보드 경로는 `/dashboard/today` 로 고정(스펙 예시의 `/dashboard` 아님).

Flutter 는 서버가 반환한 `date`/`start_time`/`due_date` **문자열을 그대로 표시** 하세요(자체 tz 변환 금지).

---

## 7. 추후 개선 (멀티유저 / 인증 / 실제 timezone)

- 멀티유저: `confirm`/`dashboard` 가 실제 `user_id` 로 소유자를 분리하도록 `ensure_default_owner` 대신 인증 주체 기반 소유자 확정으로 교체(스키마의 users/calendars FK 활용).
- 인증: 토큰 미들웨어 도입 후 `user_id` 를 요청 바디가 아니라 인증 컨텍스트에서 획득.
- 실제 timezone: 저장을 timezone-aware datetime 으로 전환(스키마 마이그레이션 포함), 조회 시 클라이언트 tz 로 변환. 이번 단계 범위 아님.
