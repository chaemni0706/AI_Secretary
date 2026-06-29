# AI Secretary — Backend

> **AI 개인비서 앱 백엔드**
> Flutter 앱과 REST API로 연동되는 FastAPI 서버. 자연어 일정 분석, 예약 후보 추천, 예약 메시지 생성, 준비물·출발 알림, 하루 브리핑, 감정 코칭을 JSON으로 제공합니다.

---

## 1. 프로젝트 개요

AI Secretary 백엔드는 Flutter 앱에서 받은 사용자 입력을 받아 AI 기능을 처리하고, 결과를 공통 JSON 구조로 돌려주는 API 서버입니다.

제공 기능:
- 자연어 일정 분석 (예: "내일 오후 2시에 병원 예약 잡아줘" → 일정 데이터)
- 예약 후보 시간 추천 (빈 시간 탐색 + 점수화)
- 예약 문의 메시지 생성 (템플릿 + LLM 확장)
- 준비물·출발 알림 계획 (날씨·이동시간·성향 반영)
- 하루 브리핑 (우선순위 정렬 + 요약)
- 감정 분석·생활 코칭 (비진단, 생활 보조)

---

## 2. 백엔드 역할

- Flutter에서 받은 사용자 입력을 처리하고 분석 결과를 반환합니다.
- 규칙이 명확한 기능은 **Rule-based**로 처리합니다.
- 자연어 생성이 필요한 기능(예약 메시지, 브리핑)은 **LLM 확장 구조**로 설계했습니다. (`OPENAI_API_KEY`가 있으면 LLM, 없으면 템플릿으로 자동 동작)
- **일정과 To-do는 기기(On-device)에 저장**하고, 서버는 상태를 저장하지 않는(stateless) AI 분석을 담당합니다.

---

## 3. 시스템 구조

```text
Flutter App
   │  (REST / JSON)
   ▼
FastAPI Backend  (/api/v1)
   │
   ├── Rule-based Service   (일정 파싱 · 예약 추천 · 출발 알림 · 브리핑 · 감정)
   ├── Template Service     (예약 메시지 · 브리핑 문장)
   └── LLM Service (확장)   (OPENAI_API_KEY 있을 때, 실패 시 템플릿 fallback)
   │
   ▼
JSON Response  { success, message, data }
   │
   ▼
Flutter 화면 표시
```

---

## 4. 주요 API

모든 응답은 공통 구조 `{ success, message, data }` 를 사용합니다.

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET  | `/health` | 서버 상태 확인 |
| POST | `/api/v1/ai/schedule/parse` | 자연어 → 일정 정보 추출 |
| POST | `/api/v1/reservations/candidates` | 예약 후보 시간 추천 |
| POST | `/api/v1/messages/reservation` | 예약 문의 메시지 생성 |
| POST | `/api/v1/alerts/departure-plan` | 준비물·출발 알림 계획 |
| POST | `/api/v1/briefings/daily` | 하루 브리핑 생성 |
| POST | `/api/v1/emotion/analyze` | 감정 분석·생활 코칭 (비진단) |

상세 스펙: [`docs/api_spec.md`](docs/api_spec.md) · 연동 가이드: [`docs/integration_guide.md`](docs/integration_guide.md) · 응답 샘플: [`mock/`](mock/)

---

## 5. 실행 방법

```bash
cd ai-secretary

# 1) 가상환경
python -m venv venv
.\venv\Scripts\activate        # Windows
# source venv/bin/activate     # macOS / Linux

# 2) 패키지 설치
pip install -r backend/requirements.txt

# 3) 서버 실행 (프로젝트 루트에서)
uvicorn backend.main:app --reload

# 4) Swagger 접속
# http://127.0.0.1:8000/docs
```

테스트:
```bash
pytest -q
```

자세한 실행/환경변수 안내: [`docs/backend_guide.md`](docs/backend_guide.md)

---

## 6. 시연 시나리오

| 입력 / 상황 | 호출 API | 결과 |
|-------------|----------|------|
| "내일 오후 2시에 병원 예약 잡아줘" | `/ai/schedule/parse` | 날짜·시간·카테고리(hospital) 추출, 일정 초안 생성 |
| "이번 주 금요일 저녁에 미용실 갈 수 있는 시간 찾아줘" | `/reservations/candidates` | 기존 일정 사이 빈 시간(19:00) 추천 |
| "내일 병원 예약 문의 문자 만들어줘" | `/messages/reservation` | 정중한 예약 문의 문구 + 대안 2개 |
| 병원 예약 + 비 예보 + 이동 35분 | `/alerts/departure-plan` | 출발 13:15, 준비물(신분증·진료카드·우산), 알림 시간 |
| 오늘 일정 목록 | `/briefings/daily` | 우선순위 정렬 + 하루 요약 + 핵심 포인트 |
| "오늘 너무 피곤하고 아무것도 하기 싫어" | `/emotion/analyze` | 감정(fatigue) + 생활 코칭 + 실천 행동 |

---

## 7. 발표용 설명

- 백엔드는 **Flutter 앱과 AI 기능을 연결하는 API 서버** 역할을 담당합니다.
- 모든 기능을 모델 학습으로 구현하지 않고, **규칙이 명확한 기능은 Rule-based**로 처리하고 **자연어 생성이 필요한 기능은 LLM 확장 구조**로 설계했습니다. (LLM 키가 없어도 템플릿으로 동작)
- 프론트엔드는 **Mock JSON으로 먼저 화면을 만들고**, 백엔드는 **동일한 JSON 구조로 API를 구현**해 병렬 개발이 가능합니다.

---

## 폴더 구조

```text
ai-secretary/
├── backend/
│   ├── main.py              # FastAPI 앱 (CORS, 라우터, 공통 예외)
│   ├── core/                # 설정, 공통 응답(success/message/data)
│   ├── api/                 # 엔드포인트 7종
│   ├── services/            # rule/template 로직 + llm_service(확장)
│   ├── rules/               # 카테고리·우선순위·체크리스트·알림·감정 룰(JSON)
│   └── database/schema/     # Pydantic 요청/응답 스키마
├── prompts/                 # LLM 프롬프트 템플릿
├── mock/                    # 실제 응답과 동일한 샘플 JSON
├── docs/                    # api_spec / backend_guide / integration_guide
├── tests/                   # pytest API 테스트
└── frontend/                # Flutter 앱 (별도)
```

## Tech Stack
FastAPI · Pydantic v2 · Uvicorn · pytest · (확장) OpenAI
