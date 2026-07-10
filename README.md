# AI Secretary — Backend

자연어 일정 관리, 예약 추천/문의, 준비물·출발 알림, 하루 브리핑, 감정 코칭을 제공하는 FastAPI 백엔드입니다.
**OpenAI API 키 없이도** 모든 API가 룰/템플릿 기반으로 동작하며, 키가 있으면 일부 문장 생성을 LLM으로 확장합니다.

## 기능

### AI 추론형 API (룰/템플릿 + 선택적 LLM)

| API | 설명 |
|-----|------|
| `POST /api/v1/ai/schedule/parse` | 자연어 → 일정(날짜/시간/카테고리/우선순위) 추출 |
| `POST /api/v1/reservations/candidates` | 빈 시간 탐색·점수화로 예약 후보 추천 |
| `POST /api/v1/reservations/candidates/from-store` | 저장된 일정 기반 예약 후보 추천 |
| `POST /api/v1/messages/reservation` | 카테고리별 예약 문의 메시지 + 대안 생성 |
| `POST /api/v1/alerts/departure-plan` | 출발 시각 계산 + 준비물 체크리스트 + 알림 |
| `POST /api/v1/briefings/daily` | 하루 요약·핵심 포인트·우선순위 정렬 |
| `POST /api/v1/emotion/analyze` | 감정 분류 + 생활 코칭(비진단) |

### 로컬 데이터 API (SQLite CRUD)

| API | 설명 |
|-----|------|
| `POST·GET·PATCH·DELETE /api/v1/local/schedules` | 로컬 일정 CRUD (목록/단건 조회 포함) |
| `POST /api/v1/local/schedules/from-draft` | parse 결과(schedule_draft)로 일정 저장 |
| `POST·GET·PATCH·DELETE /api/v1/local/todos` | 로컬 To-do CRUD (목록/단건 조회 포함) |
| `POST /api/v1/local/todos/from-draft` | parse 결과(draft)로 To-do 저장 |
| `GET /api/v1/dashboard/today` | 특정 날짜의 일정·할일 + 집계 |
| `GET /api/v1/dashboard/summary` | 요약 집계 |
| `GET·PUT /api/v1/memory/{user_id}` | 사용자 메모리/선호 조회·upsert |
| `GET /api/v1/memory/{user_id}/context` | alert/reservation용 사용자 context |
| `PATCH /api/v1/memory/{user_id}/preferences` | 알림 성향·이동/여유시간 등 수정 |
| `POST /api/v1/memory/{user_id}/places` | 자주 가는 장소 추가 |
| `POST /api/v1/notifications/plan` | 저장된 일정 기반 알림 계획 생성 |
| `GET /api/v1/notifications/plan/{schedule_id}` | 저장된 일정 기반 알림 계획 조회(path parameter) |
| `GET /health` | 헬스 체크 |

## 빠른 시작

```bash
pip install -r backend/requirements.txt

# 최초 1회: 로컬 SQLite 스키마 초기화 (runtime/ai_secretary_local.db 생성)
python scripts/init_local_db.py

# 로컬 실행
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# 외부 기기/에뮬레이터 연동용
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## 접속 주소 (프론트 연동)

| 환경 | Base URL |
|------|----------|
| PC 로컬 | `http://127.0.0.1:8000` |
| Android Emulator | `http://10.0.2.2:8000` |
| 실제 기기(같은 Wi-Fi) | `http://{PC_IP}:8000` |

## 공통 응답 구조

```json
{ "success": true, "message": "...", "data": { } }
```

프론트 핵심 필드: 일정 `data.schedule_draft`, 예약 후보 `data.recommended_candidates`,
예약 메시지 `data.generated_message`, 출발 알림 `data.leave_time`·`data.checklist`,
브리핑 `data.summary`·`data.key_points`, 감정 `data.emotion`·`data.coaching`.

## 인증(Verification) 도메인

인증 타입은 책임에 따라 두 범주로 나뉘며, 판정 로직은 타입별로 분리되어 있다.
라우팅은 `backend/services/verification_orchestrator.py`가 담당한다.

1. **VLM 기반 시각 인증** — water / exercise / study
   - 이미지 → VisionAnalyzer → VisionAnalysis → `evaluate_image_verification(type, ...)`(Rule Engine) → 판정
   - exercise는 `activity_type`(gym/home_workout 등)이 필수이며, 없으면 422를 반환한다.
   - study는 기기(노트북/모니터) 존재만으로 verified되지 않고 학습 콘텐츠 근거가 필요하다.
   - water는 빈 컵/색 음료/근거 부족이 PASS되지 않는다(false positive 우선 차단).

2. **세션/시간 기반 인증** — wakeup
   - 서버 수신 시각, 일회성 인증 세션, 이미지 SHA256 중복 검사, 재촬영 횟수 제한으로 판정한다.
   - **Qwen VLM과 Rule Engine을 사용하지 않는다.** 휴대전화 시간·EXIF 시간·사진에 표시된 시각은 최종 판정 기준으로 쓰지 않는다.
   - 그래서 wakeup은 Qwen VLM batch 평가(local_eval) 대상에서 의도적으로 제외된다.

> Wakeup verification is intentionally excluded from Qwen VLM batch evaluation because the final
> decision is based on server-side time/session validation and duplicate image hash checks, not
> visual semantic evidence.

### 엔드포인트

기존 엔드포인트는 유지되며(하위호환), 아래 통합 경로가 추가되었다.

VLM 이미지 인증:

```http
POST /api/v1/verification/image/{verification_type}    # water | exercise | study (multipart)
```

기상(wakeup) 인증:

```http
POST /api/v1/verification/wakeup/session               # 세션 발급 (JSON)
POST /api/v1/verification/wakeup/submit                # 이미지 제출 (multipart: session_id + file)
```

기존 경로(그대로 유지): `POST /api/v1/image-verifications`,
`POST /api/v1/image-verifications/wakeup/sessions`,
`POST /api/v1/image-verifications/wakeup/sessions/{session_id}/verify`.

응답은 공통 envelope `{success, message, data}`를 따른다. 이미지 인증의 `data`는
`verification_type / result / score / rule_evidence / vlm_analysis`를 포함하고, wakeup 제출의
`data`는 `{verification_type: "wakeup", result, wakeup_data}` 형태로 감싼다.

## 알림 계획 API

알림 계획 생성:

`POST /api/v1/notifications/plan`

알림 계획 조회:

`GET /api/v1/notifications/plan/{schedule_id}`

주의: 알림 조회는 query parameter가 아니라 path parameter 방식입니다.
Flutter에서는 `schedule_id`를 URL 경로에 포함해야 합니다.

예:

```http
GET /api/v1/notifications/plan/123
```

## 테스트

```bash
python -m pytest -v                       # 전체 256개 통과
python -m pytest --import-mode=importlib   # import 모드 무관 통과
```

OpenAI 키 없이 결정론적으로 동작하므로 추가 설정 없이 재현됩니다.

## 시연(데모) 방법

1. 서버 실행 → http://127.0.0.1:8000/docs 접속.
2. 각 엔드포인트의 "Try it out"에서 예시 요청(스키마 example 자동 채움)으로 호출.
3. 응답이 `mock/*.json` 샘플과 동일 구조인지 확인.
   - 예: `/api/v1/briefings/daily`에 일정 3개 → `summary`에 "오전/오후/저녁" 흐름 + 준비 팁.

## 문서

- `docs/api_spec.md` — 엔드포인트별 Request/Response 상세
- `docs/backend_guide.md` — 실행/구조/테스트
- `docs/integration_guide.md` — 프론트(Flutter) 연동
- `mock/*.json` — 실제 응답과 동일한 샘플 (프론트 참고용)

## 데이터 계층

- SQLite + SQLAlchemy. 기본 DB: `sqlite:///runtime/ai_secretary_local.db`.
- 모델: `User`, `UserSetting`, `Calendar`, `PlannerItem`, `EventDetail`, `TodoDetail`, `Reminder`, `UserMemory`.
- 일정/To-do는 `PlannerItem`을 공통으로 쓰고 상세는 `EventDetail`/`TodoDetail`로 분리.

## 비고

- 결정론적·안전 필드(분류/점수/우선순위/위험도)는 항상 룰 기반.
- 문장 생성(summary/coaching/message)만 LLM 사용, 실패/키없음 시 템플릿 fallback.
- 감정 분석은 의학적 진단이 아닌 생활 코칭 보조이며, 위험 신호 시 전문가 상담을 권유합니다.

---

## 👥 Team

| 역할       | 담당 |
| -------- | -- |
| Frontend |    |
| Backend  |    |
| AI       |    |
| UI/UX    |    |
