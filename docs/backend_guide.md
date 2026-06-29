# AI Secretary Backend — 실행 가이드

## 요구 사항
- Python 3.11+ (권장)
- 프로젝트 루트(`ai-secretary/`)에서 실행합니다. 서버 모듈 경로는 `backend.main:app` 입니다.

## 1) 가상환경 생성 & 활성화
```bash
cd ai-secretary

python -m venv venv

# Windows
.\venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

## 2) 패키지 설치
```bash
pip install -r backend/requirements.txt
```
> MVP 단계는 Rule-based / Template로 동작하므로 OpenAI 등 외부 키 없이 실행됩니다.
> LLM 확장 기능을 쓰려면 `.env`에 `OPENAI_API_KEY`를 설정하세요(없어도 템플릿으로 동작).

## 3) 서버 실행
```bash
uvicorn backend.main:app --reload
```
- 로컬: `http://127.0.0.1:8000`
- 같은 네트워크의 다른 기기에서 접속하려면:
```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## 4) Swagger (API 문서/테스트)
```
http://127.0.0.1:8000/docs
```
각 엔드포인트에 예시 Request가 채워져 있어 "Try it out"으로 바로 호출할 수 있습니다.

## 5) 헬스 체크
```bash
curl http://127.0.0.1:8000/health
```

## 6) 환경변수 (.env)
`backend/.env` 파일 예시 (`backend/.env.example` 참고):
```env
APP_NAME=AI Secretary Backend
APP_VERSION=0.1.0
API_V1_PREFIX=/api/v1
DEBUG=true

# CORS: "*"는 모든 출처 허용(개발용), 또는 콤마로 구분된 목록
CORS_ORIGINS=*

# LLM (선택) — 없으면 템플릿으로 동작
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.7
LLM_TIMEOUT_SECONDS=8.0
```

## 7) 테스트 실행
```bash
pytest -q
```


## LLM 동작 방식 (선택)

- `OPENAI_API_KEY`가 비어 있으면 모든 기능이 **Rule-based / Template**로 동작합니다(키 없이 실행·시연 가능).
- 키를 설정하면 다음 3개 기능이 LLM 생성으로 업그레이드됩니다.
  - 예약 메시지(`/messages/reservation`) — `generated_message`
  - 하루 브리핑(`/briefings/daily`) — `summary`
  - 감정 코칭(`/emotion/analyze`) — `coaching`
- LLM 호출이 실패하면(네트워크/쿼터/타임아웃 등) 자동으로 템플릿으로 **fallback**합니다.
- 감정 분석의 라벨·점수·위기(risk=high) 판단은 **항상 규칙 기반**으로, LLM은 코칭 문장 표현만 담당합니다.
- 모델/온도는 `OPENAI_MODEL`, `LLM_TEMPERATURE`로 조정하며, 모든 LLM 연동 코드는 `backend/services/llm_service.py` 한 곳에 있습니다.

## 폴더 구조 (백엔드)
```
backend/
├── main.py                # FastAPI 앱 (CORS, 라우터, 예외 핸들러)
├── core/                  # config, 공통 응답
├── api/                   # 엔드포인트 (health/schedule/reservation/message/alert/briefing/emotion)
├── services/              # 비즈니스 로직 (rule/template), llm_service(구조)
├── rules/                 # 카테고리/우선순위/체크리스트/알림/감정 룰 JSON
└── database/schema/       # Pydantic 요청·응답 스키마
```
