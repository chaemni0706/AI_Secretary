# Backend Guide — 실행 / 구조 / 테스트

## 1. 환경

- Python 3.11 (개발/테스트는 3.10+ 호환)
- 의존성 설치: `pip install -r backend/requirements.txt`
- OpenAI 키는 **선택**입니다. 없어도 모든 API가 템플릿/룰 기반으로 동작합니다.
  - 사용 시: `backend/.env`에 `OPENAI_API_KEY=...` (예시는 `backend/.env.example`)

## 2. 서버 실행

로컬(본인 PC에서만 접속):
```bash
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

외부 연동용(같은 네트워크의 다른 기기/에뮬레이터에서 접속):
```bash
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger UI: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

## 3. 디렉터리 구조

```
backend/
  main.py                  # FastAPI 앱, CORS, 공통 예외 핸들러, 라우터 등록
  core/
    config.py              # 설정(pydantic-settings); OPENAI_API_KEY 등
    response.py            # 공통 응답 envelope {success, message, data}
  api/                     # 라우터 (얇은 계층, 서비스 호출만)
    health, schedule, reservation, message, alert, briefing, emotion
  services/                # 실제 비즈니스 로직 (rule / template 기반)
    schedule_parser, reservation_recommender, message_generator,
    departure_alert, briefing_generator, emotion_analyzer, llm_service
  rules/                   # 룰 JSON (category/priority/checklist/notification/emotion)
  database/schema/         # Pydantic Request/Response 스키마 (프론트 계약)
prompts/                   # LLM 프롬프트 템플릿 (키 있을 때만 사용)
mock/                      # 프론트 공유용 실제 응답 샘플 (Swagger 응답과 동일)
tests/                     # pytest (100개)
```

## 4. 설계 원칙

- 모든 응답은 `{success, message, data}` envelope로 통일(`core/response.py`).
- 결정론적·안전 필드(분류/점수/우선순위/위험도)는 항상 룰 기반.
- 자연어 문장(summary/coaching/message)만 LLM 사용, 실패·키없음 시 템플릿 fallback (`services/llm_service.py`가 단일 진입점, 실패는 `None` 반환).
- 서비스는 잘못된 입력에도 예외를 던지지 않음(missing_fields/빈 결과/None로 안전 처리).

## 5. 테스트

```bash
python -m pytest -v                         # 전체 (100 passed)
python -m pytest tests/test_api.py -v        # cross-API 계약
python -m pytest --import-mode=importlib     # import 모드 무관 통과
```

- `tests/conftest.py`: 세션 TestClient + `check_envelope` / `post` 헬퍼 fixture.
- 각 서비스 테스트(schedule/reservation/alert/briefing/emotion/message)와 LLM fallback 테스트(test_llm) 포함.
- OpenAI 키 없이 동작하므로 CI/로컬에서 추가 설정 없이 재현 가능.

## 6. Mock 동기화

`mock/*.json`은 실제 API 응답과 **동일 구조**입니다. 응답 구조를 바꾸면 mock도 함께 갱신하세요.
검증: 실제 호출 결과(JSON)와 `mock/*.json`을 비교해 일치하는지 확인합니다.
