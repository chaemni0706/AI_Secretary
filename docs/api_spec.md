# AI Secretary Backend — API Spec

모든 응답은 공통 envelope를 사용합니다.

```json
{ "success": true, "message": "사람이 읽을 메시지", "data": { } }
```

- `success`: 처리 성공 여부 (boolean)
- `message`: 사용자/개발자용 메시지 (string)
- `data`: 실제 페이로드 (object 또는 null)

Base URL: `http://{host}:8000`  ·  API prefix: `/api/v1`  ·  Swagger: `/docs`

---

## API 목록

| # | Method | Endpoint | 설명 |
|---|--------|----------|------|
| 1 | GET  | `/health` | 서버 상태 확인 |
| 2 | POST | `/api/v1/ai/schedule/parse` | 자연어 → 일정 정보 추출 |
| 3 | POST | `/api/v1/reservations/candidates` | 예약 후보 시간 추천 |
| 4 | POST | `/api/v1/messages/reservation` | 예약 문의 메시지 생성 |
| 5 | POST | `/api/v1/alerts/departure-plan` | 준비물·출발 알림 계획 |
| 6 | POST | `/api/v1/briefings/daily` | 하루 브리핑 생성 |
| 7 | POST | `/api/v1/emotion/analyze` | 감정 분석·생활 코칭 (비진단) |


> **LLM 확장:** `/messages/reservation`(generated_message), `/briefings/daily`(summary), `/emotion/analyze`(coaching)는 `OPENAI_API_KEY`가 있으면 LLM 생성을 사용하고, 없거나 실패하면 템플릿으로 자동 fallback합니다. 응답 구조는 동일합니다.

> 일정/To-do 데이터는 기기(On-device)에 저장됩니다. 서버는 상태를 저장하지 않으며,
> 분석에 필요한 데이터를 요청 본문으로 받아 처리합니다.

---

## 1. GET /health

**Response**
```json
{ "success": true, "message": "Backend server is running",
  "data": { "status": "ok", "service": "AI Secretary Backend" } }
```
**프론트 처리:** 앱 시작 시 백엔드 연결 확인. `data.status == "ok"`면 정상.

---

## 2. POST /api/v1/ai/schedule/parse

**Request**
```json
{ "input": "내일 오후 2시에 병원 예약 잡아줘", "input_type": "text",
  "current_datetime": "2026-06-29T10:00:00+09:00", "timezone": "Asia/Seoul" }
```
**Response (data)** — `intent`, `confidence`, `slots`, `schedule_draft`, `missing_fields`.
전체 예시는 `mock/schedule_parse_response.json` 참고.

**프론트 처리:** `schedule_draft`를 일정 등록 폼 기본값으로 사용. `missing_fields`가 비어있지 않으면
(`date`, `start_time`, `title`, `time_ambiguity` 등) 사용자에게 보완 입력을 요청.

---

## 3. POST /api/v1/reservations/candidates

**Request**
```json
{ "constraints": { "target_date": "2026-07-03", "preferred_start_time": "18:00",
    "preferred_end_time": "21:00", "duration_minutes": 60, "category": "beauty" },
  "existing_schedules": [
    { "id": "sch_101", "title": "팀플 회의", "date": "2026-07-03", "start_time": "18:00", "end_time": "19:00" } ] }
```
**Response (data)** — `target_date`, `recommended_candidates[]`(candidate_id/start_time/end_time/score/reason/conflict), `rejected_slots[]`.
전체 예시는 `mock/reservation_candidates_response.json`.

**프론트 처리:** `recommended_candidates`를 점수순 카드로 표시. 빈 배열이면 `message`("예약 가능한 시간이 없습니다.")를 안내.

---

## 4. POST /api/v1/messages/reservation

**Request**
```json
{ "reservation_info": { "category": "hospital", "target_date": "2026-06-30",
    "preferred_time": "10:00", "purpose": "진료 예약" },
  "style": { "tone": "polite", "length": "short", "channel": "sms" } }
```
**Response (data)** — `generated_message`, `alternatives[]`, `style`.
전체 예시는 `mock/reservation_message_response.json`.

**프론트 처리:** `generated_message`를 기본 문구로 보여주고 `alternatives`를 "다른 문구" 옵션으로 제공.

---

## 5. POST /api/v1/alerts/departure-plan

**Request**
```json
{ "schedule": { "title": "병원 예약", "category": "hospital", "start_time": "14:00", "location": "서울OO병원" },
  "context": { "weather": "rain", "estimated_travel_minutes": 35, "buffer_minutes": 10 },
  "user_preference": { "notification_style": "strong", "forgetful": true } }
```
**Response (data)** — `leave_time`, `estimated_travel_minutes`, `buffer_minutes`, `checklist[]`(item/reason), `notifications[]`(time/message).
전체 예시는 `mock/departure_plan_response.json`.

**프론트 처리:** `checklist`를 체크박스 리스트로, `notifications`를 로컬 알림으로 등록. `leave_time`이 null이면 시간 입력 확인 요청.

---

## 6. POST /api/v1/briefings/daily

**Request**
```json
{ "date": "2026-06-30",
  "schedules": [ { "title": "병원 예약", "category": "hospital", "start_time": "14:00", "end_time": "15:00", "priority": "high" } ],
  "todos": [ { "title": "진료카드 챙기기", "priority": "high", "is_done": false } ] }
```
**Response (data)** — `summary`, `key_points[]`, `priority_order[]`(title/priority/reason).
전체 예시는 `mock/daily_briefing_response.json`.

**프론트 처리:** `summary`는 상단 카드, `key_points`는 불릿, `priority_order`는 정렬된 일정 리스트로 표시.

---

## 7. POST /api/v1/emotion/analyze

> 의학적 진단이 아닌 생활 코칭 보조 기능입니다.

**Request**
```json
{ "input": "오늘 너무 피곤하고 아무것도 하기 싫어", "date": "2026-06-30",
  "recent_context": { "sleep_hours": 4.5, "schedule_count": 5, "todo_done_rate": 30 } }
```
**Response (data)** — `sentiment`, `emotion`, `emotion_score`, `risk_level`, `coaching`, `recommended_actions[]`.
전체 예시는 `mock/emotion_analyze_response.json`.

**프론트 처리:** `coaching`을 코칭 카드로, `recommended_actions`를 실천 버튼으로 표시. `risk_level == "high"`면 지원 안내 UI를 노출.

---

## 에러 응답

에러도 동일한 envelope를 사용하며 `success: false`입니다.

| 상황 | HTTP | 예시 |
|------|------|------|
| 잘못된 경로 | 404 | `{ "success": false, "message": "Not Found", "data": null }` |
| 요청 형식 오류(검증 실패) | 422 | `{ "success": false, "message": "Validation error", "data": [ ...상세... ] }` |
| 서버 내부 오류 | 500 | `{ "success": false, "message": "Internal Server Error", "data": null }` |

**프론트 공통 처리:** 먼저 `success`를 확인 → false면 `message`를 사용자에게 노출(422의 경우 `data`로 어떤 필드가 문제인지 확인). 일부 분석 API는 파싱 실패해도 `success: true`로 응답하고 `missing_fields`(schedule) 또는 빈 배열로 부족분을 표현하므로, 화면에서 이 필드들을 확인해야 합니다.
