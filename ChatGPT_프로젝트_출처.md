# AI Secretary + AI 가계부 — 프로젝트 컨텍스트 (ChatGPT 프로젝트 출처용)

## 0. 한 줄 요약
Flutter(앱) ↔ FastAPI(백엔드)가 REST로 연결된 **AI 일정 비서 앱**으로, 자연어 일정 관리·예약 추천·출발 알림·하루 브리핑·감정 코칭을 제공하고, 여기에 **알림/영수증 기반 자동 거래 기록 + 소비 분석(AI 가계부)** 기능을 얹었다. 모든 AI 기능은 **rule/template이 기본, LLM은 선택적 상위 레이어**로 동작해 `OPENAI_API_KEY` 없이도 전 기능이 결정론적으로 작동한다.

---

## 1. 아키텍처 개요
- **프론트엔드**: Flutter (`frontend/lib`). 화면(screens) + 서비스(services) 구조. STT/TTS는 온디바이스(`speech_to_text`, `flutter_tts`).
- **백엔드**: FastAPI (`backend`). 라우터(`backend/api`) + 서비스 로직 + rules(JSON) 구조.
- **통신 규약**: 모든 응답은 `{ success, message, data }` envelope. 프론트 `api_client.dart`가 envelope를 풀어 `data`만 반환하고, `success=false`/네트워크 오류 시 `ApiException`을 던진다. API prefix는 `/api/v1`, connect/receive 타임아웃 각 10초.
- **데이터 계층**: SQLite + SQLAlchemy. 기본 DB `sqlite:///runtime/ai_secretary_local.db`.
- **AI 동작 원칙**: 분류/점수/우선순위/위험도 등 안전 필드는 **항상 rule 기반**. 문장 생성(summary/coaching/message)만 LLM을 시도하고, 키 없음/실패 시 template로 fallback.

---

## 2. AI Secretary (일정 비서) API

### 2-1. AI 추론형 API (rule/template + 선택적 LLM)
| API | 설명 |
|-----|------|
| `POST /api/v1/ai/schedule/parse` | 자연어 → 일정(날짜/시간/카테고리/우선순위) 추출 |
| `POST /api/v1/reservations/candidates` | 빈 시간 탐색·점수화로 예약 후보 추천 |
| `POST /api/v1/reservations/candidates/from-store` | 저장된 일정 기반 예약 후보 추천 |
| `POST /api/v1/messages/reservation` | 카테고리별 예약 문의 메시지 + 대안 생성 |
| `POST /api/v1/alerts/departure-plan` | 출발 시각 계산 + 준비물 체크리스트 + 알림 |
| `POST /api/v1/briefings/daily` | 하루 요약·핵심 포인트·우선순위 정렬 |
| `POST /api/v1/emotion/analyze` | 감정 분류 + 생활 코칭(비진단) |

### 2-2. 로컬 데이터 API (SQLite CRUD)
- 일정: `POST·GET·PATCH·DELETE /api/v1/local/schedules`, `POST .../from-draft`
- 할일: `POST·GET·PATCH·DELETE /api/v1/local/todos`, `POST .../from-draft`
- 대시보드: `GET /api/v1/dashboard/today`, `GET /api/v1/dashboard/summary`
- 메모리/선호: `GET·PUT /api/v1/memory/{user_id}`, `.../context`, `PATCH .../preferences`, `POST .../places`
- 알림 계획: `POST /api/v1/notifications/plan`, `GET /api/v1/notifications/plan/{schedule_id}` (조회는 **path parameter**)
- 헬스: `GET /health`

### 2-3. 데이터 모델
`User`, `UserSetting`, `Calendar`, `PlannerItem`, `EventDetail`, `TodoDetail`, `Reminder`, `UserMemory`. 일정/할일은 `PlannerItem`을 공통으로 쓰고 상세는 `EventDetail`/`TodoDetail`로 분리. enum은 DB에 UPPERCASE 저장, API는 소문자 응답(`SCHEDULED`↔`scheduled`).

### 2-4. 개인 맞춤 메모리 (Personalization)
새 기능이 아니라 기존 `user_memories`를 **예약 추천·알림·감정 코칭에 연결**해 개인화를 구현. MVP 전제: 멀티유저 인증 없음(기본 `user_id="local-user"`), DB 스키마 변경 없음, rule + 저장된 preference 기반.
- 조회/저장: `GET/PUT /api/v1/memory/{user_id}/preferences/effective`. richer 필드는 `user_memories`에 `pref_*` PREFERENCE 행으로 저장(스키마 불변).
- preference 예: `preferred_reservation_times`/`avoid_times`(time_bucket ∈ early_morning·morning·afternoon·evening·late_night), `default_reminder_minutes`, `departure_buffer_minutes`, `late_prone`, `preferred_tone`(neutral·gentle·warm), `coaching_style`(supportive·direct·coaching), `stress_triggers`, `rest_recommendation_enabled`, `notification_style`(normal·soft·strong).
- merge 정책: preference 없으면 기본값(`personalization_applied=false`, `memory_source=default_preference`), 일부만 있으면 기본값 위에 merge, invalid 값은 무시(500 없음). 하나라도 있으면 `personalization_applied=true`, `memory_source=stored_preference`.
- 모든 개인화 응답은 `personalization` 메타데이터(`personalization_applied`, `memory_source`, `used_preferences`) 포함 → 프론트가 개인화 적용 여부 확인 가능.

### 2-5. 감정 기반 생활 코칭 (Life Coaching MVP)
감정 입력을 rule-based로 분석한 뒤 **오늘 일정·할일·빈 시간·preference와 연결**해 단순 위로가 아닌 "지금 무엇을 하면 좋은지"를 카드로 제안. 새 학습 모델/외부 심리·의료 API 없음.
- 감정 상태: `stress, tired, overwhelmed, anxious, sad, unmotivated, angry, positive, neutral`. 여러 개면 `primary_emotion`+`secondary_emotions`, 매칭 없으면 `neutral`, `emotion_score`(0~1).
- 오늘 컨텍스트: `dashboard_service.get_today`로 `context_summary`(schedule_count·todo_count·next_schedule·due_todos) 채움. 마감 임박 할일이 있으면 `break_down_task` 카드 우선.
- 빈 시간: `reservation_recommender`로 09:00~21:00 창에서 빈 시간 추천(휴식/산책 제안 등).
- 안전: crisis 키워드는 고정 안전 메시지, 진단성 표현 금지.

---

## 3. AI 가계부 (Ledger) 기능

### 3-1. 개요
기존 백엔드에 **알림 기반 자동 거래 기록 + 영수증 스캔 기록 + 소비 분석 대시보드**를 최소 변경으로 추가. 신규 테이블 1개(`ledger_transactions`)만 추가하고 `main.py`는 라우터 등록 2줄만 수정. OCR/LLM은 모두 optional fallback.

### 3-2. API 명세 (모두 `{success, message, data}` envelope)
| Method | Path | 설명 |
|---|---|---|
| POST | `/api/v1/ledger/notifications/simulate` | mock 알림 파싱 → 거래 생성 |
| POST | `/api/v1/ledger/receipts/scan` | 영수증 텍스트 스캔/파싱 |
| POST | `/api/v1/ledger/receipts/scan-image` | 영수증 이미지 업로드 (OCR optional, 안전 fallback) |
| GET | `/api/v1/ledger/dashboard` | 가계부 홈 대시보드 (화면 1) |
| GET | `/api/v1/ledger/report` | 월간 소비 리포트 (화면 2) |
| POST | `/api/v1/ledger/transactions/{id}/confirm` | 거래 확정 |
| PATCH | `/api/v1/ledger/transactions/{id}` | 거래 수정 (category 수정 시 user_override) |
| DELETE | `/api/v1/ledger/transactions/{id}` | 거래 삭제 (soft delete: status=deleted) |
| POST | `/api/v1/ledger/mock/seed` | 시연용 mock 데이터 (idempotent) |

### 3-3. 핵심 로직
- **알림 파싱**: 유형 판정 우선순위 `cancel > ignore > income > expense`. 금액 정규식 추출, 상호명은 금액 이후 tail 제거 후 앞부분 유지.
- **영수증 파싱**: 상호명=첫 줄, 금액=합계/총액/결제금액 라인 우선(없으면 최대 금액), items는 `<상품명> <금액>` 라인만 추출.
- **카테고리 5단계**: ① rule_based(conf 0.98) → ② mock_place_search(모호 시 alternatives+needs_confirmation) → ③ category_mapping → ④ LLM(optional) → ⑤ fallback(`기타`, conf 0.3, needs_confirmation).
- **중복 방지**: `dedup_key`=sha1(user_id|normalized_merchant|amount|transaction_type|date)로 의미 중복 판정 + 퍼지(같은 상호·금액±100원·10분 이내). 중복이면 신규 생성 없이 기존 거래 반환. `source_hash`는 원본 재전송 감사용.
- **OCR**: pytesseract/PIL 없으면 `None` 반환 → API는 `status=needs_review`, `stored=false`로 HTTP 200 안전 응답(500 없음).

### 3-4. 프론트 연동 규약
- enum 전부 소문자: `transaction_type`=expense|income|cancel|ignore, `source_type`=notification|receipt_scan|manual|seed, `status`=pending|confirmed|duplicate|deleted|needs_review.
- `amount`=정수(원), `date`=YYYY-MM-DD, `time`=HH:MM, `occurred_at`=ISO datetime.
- 화면 1(홈)=dashboard 응답(summary/calendar/selected_date/pending_transactions/budget_alerts/recurring_preview), 화면 2(리포트)=report 응답(summary/category_analysis/budget_usage/recurring_payments/briefing).

---

## 4. 온디바이스 AI 방향
- **STT/TTS는 이미 온디바이스**(speech_to_text, flutter_tts). 서버 STT(Whisper 등) 미사용이 MVP 정책. 서버 `/voice/tts`는 오디오 합성 없이 "읽을 문장"만 반환하는 fallback.
- 온디바이스로 옮길 후보: TTS 재생 fallback 일관화(P0), 오프라인 타임아웃 감지 공통화(P0), 음성 챗봇 Mock→실API+로컬 fallback(P1), 경량 로컬 일정 키워드 파서(P1), 로컬 감정 키워드 분류(P2, 안전문구 필수), 로컬 말투 후처리(P2).
- 서버 유지: 복잡한 자연어 일정 분석(LLM-first hybrid), 감정 코칭 문장 생성, 하루 브리핑, 예약 추천/메시지, 지도·이동시간(외부 API).
- 원칙: 기존 파일은 삭제 없이 **fallback 분기만 추가**, API 계약(응답 스키마) 불변, 감정 분류는 라벨·정형문구까지만(진단성 표현 금지, 위기 신호는 고정 안전 메시지).

---

## 5. 저장소 구조 & rule-first 설계

### 5-1. rule 파일 기반 동작 (`backend/rules/`, JSON 약 28개)
안전·분류 로직은 코드가 아니라 JSON 규칙 파일에서 읽어 결정론적으로 동작(수정 시 재배포 없이 규칙만 교체 가능). 도메인별 예시:
- 일정/파싱: `schedule_patterns`, `schedule_categories`, `schedule_category_rules`, `schedule_stopwords`, `schedule_clarification_questions`, `schedule_location_policy`, `priority_rules`, `reschedule_rules`
- 감정/코칭: `emotion_rules`, `empathy_rules`, `solution_rules`, `tts_tone_rules`
- 알림/체크리스트: `notification_rules`, `checklist_rules`
- 예약/장소: `reservation_message_rules`, `place_recommendation_rules`, `virtual_businesses`
- 가계부: `ledger_notification_rules`, `merchant_category_rules`, `merchant_search_mock`, `category_mapping_rules`, `category_rules`, `ledger_budget_rules`
- 음성/의도: `voice_intent_rules`, `chat_intent_rules`

### 5-2. LLM 프롬프트 템플릿 (`prompts/`)
`briefing_prompt`, `emotion_coaching_prompt`, `memory_prompt`, `planner_prompt`, `reservation_prompt` (relationship_prompt는 비어 있음). LLM 사용 시에만 참조, 없으면 rule/template fallback.

### 5-3. 디렉터리 구조
- `backend/` : `api/`(라우터), 서비스 로직, `database/`(models·repository·schema), `rules/`
- `frontend/lib/` : `screens/`, `services/`, `models/`, `widgets/`, `theme/`, `data/`, `main.dart`
- `database/` : `local_schema.sql`(SQLite), `*.dbml`, `server_schema_postgres.sql`
- `docs/` : api_spec, backend_guide, integration/flutter contract, feature MVP 문서 등
- `tests/` : pytest (총 273건)
- **미구현/스캐폴드**: `rag/`(documents·embeddings·vector_db 빈 폴더), `data/`(locations·profiles·relationships 등 빈 폴더), `on_device/`(voice·memory·notification·image dart/tflite 스텁 — 실제 STT/TTS는 `frontend/lib/services`에 있음).

---

## 6. 실행 / 테스트
```bash
pip install -r backend/requirements.txt
python scripts/init_local_db.py          # 최초 1회 로컬 SQLite 초기화
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```
- Swagger: http://127.0.0.1:8000/docs · Health: http://127.0.0.1:8000/health
- 접속 주소: PC 로컬 `127.0.0.1:8000`, Android Emulator `10.0.2.2:8000`, 실기기 `{PC_IP}:8000`
- 테스트: `python -m pytest -q` → **273 passed** (기존 244 + 가계부 신규 29, 회귀 0). OpenAI 키/OCR 없이 결정론적으로 재현.

---

## 7. 안전·비고
- 감정 분석은 의학적 진단이 아닌 생활 코칭 보조. 위험 신호 시 전문가 상담 권유.
- 결정론·안전 필드는 항상 rule 기반, 문장 생성만 LLM(실패/키없음 시 template fallback).
- 프로토타입 범위: mock 알림 POST, receipt_text rule 파싱, mock place search, rule 카테고리/브리핑, in-DB dedup, idempotent seed. **실서비스 몫(미구현)**: 실제 SMS/NotificationListener 권한, 실 카드사/금융 API, 실 네이버/카카오 장소 검색, 필수 OCR 엔진, LLM 상시 사용.
