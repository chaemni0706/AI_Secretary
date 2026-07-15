# 포비(Pobi) — 나의 완벽한 AI 비서

> 자연어 일정 관리, 예약 추천·문의, 준비물·출발 알림, 하루 브리핑, 감정 코칭, AI 가계부, 이미지 인증을 하나로 묶은 개인 비서 앱입니다.
> **OpenAI API 키 없이도** 모든 기능이 규칙/템플릿 기반으로 동작하며, 키가 있으면 일부 문장 생성을 LLM으로 확장합니다.

---

## 한눈에

| 구분 | 내용 |
|------|------|
| 프론트엔드 | **Flutter** (Android) — 음성 웨이크워드 "포비", 온디바이스 STT/분류, 커스터마이즈 위젯 대시보드 |
| 백엔드 | **FastAPI** (Python 3.11) — 규칙 엔진 + 선택적 LLM |
| AI | 규칙/템플릿(기본) · OpenAI LLM(선택) · 이미지 인증(온디바이스 Smol blocker 선감지 → 서버 VLM fallback → Rule Engine 최종판정) · 온디바이스 경량 모델 |
| 데이터베이스 | **SQLite** 로컬 (`database/local_schema.sql` 단일 소스) |

세부 구조는 [README_아키텍처.md](./README_아키텍처.md)를 참고하세요.

---

## 주요 기능

- **자연어 일정 관리** — "내일 3시 강남 미팅"을 말/글로 입력 → 날짜·시간·장소·카테고리·우선순위 자동 추출, 부족한 정보는 되물음.
- **할일(To-do) 관리** — 마감·시작 일시, 우선순위 기반 할일 등록/수정, 완료 처리(완료 시각 기록), 완료 캘린더로 달성 현황 확인.
- **예약 추천·문의** — 빈 시간 탐색·점수화로 예약 후보 추천, 카테고리별 예약 문의 메시지 자동 생성.
- **출발·준비물 알림** — 이동 시간 계산 → 출발 시각 + 준비물 체크리스트 알림.
- **하루 브리핑** — 오늘 일정·핵심 포인트·우선순위 정렬, 전화형 알림/TTS로 전달.
- **감정 분석·생활 코칭** — 감정 분류 + 비진단 코칭(사용자 동의 시에만 기록).
- **AI 가계부** — 카드 결제 알림·영수증에서 거래 자동 기록, 카테고리 분류, 중복 제거, 예산 경고, 지출 리포트.
- **이미지 인증** — 물 마시기/운동/공부/기상 인증. 온디바이스 Smol이 명백한 오촬영(blocker)만 선감지하고 나머지는 서버 VLM으로 넘겨 Rule Engine이 최종 판정. 기상 인증은 카메라 직접 촬영만 허용하며, 얼굴/신원이 아닌 아침·기상 맥락(사람+침대/창문/햇빛 등)으로 판정.
- **음성 비서** — "포비" 호출어 상시 대기(온디바이스), STT/TTS 대화.

---

## 기술 스택

**Frontend** — Flutter, Dio, Provider, table_calendar, geolocator/google_maps, speech_to_text/flutter_tts, vosk(온디바이스 STT), firebase_messaging, flutter_local_notifications

**Backend** — FastAPI, SQLAlchemy 2.0, Pydantic v2, OpenAI(선택), LangChain·Chroma·FAISS·sentence-transformers, transformers/torch, spaCy·kiwipiepy·dateparser(한국어 NLP), PaddleOCR, scikit-learn

**DB** — SQLite (로컬), PostgreSQL(서버 로드맵)

---

## 프로젝트 구조

```
AI_Secretary/
├── frontend/              Flutter 앱
│   ├── lib/
│   │   ├── screens/       화면 (일정·할일·가계부·인증·대시보드 등)
│   │   ├── widgets/       위젯 (dashboard_widgets, todo 완료 캘린더 등)
│   │   ├── services/      API 클라이언트 + 온디바이스 서비스
│   │   ├── models/        DTO / 매퍼
│   │   └── theme/         디자인 토큰(Toss 스타일)
│   └── assets/            폰트·일러스트·온디바이스 모델
├── backend/               FastAPI
│   ├── api/               라우터 (엔드포인트)
│   ├── services/          도메인 로직 (규칙 + 선택적 LLM, 60+ 모듈)
│   ├── database/          ORM · 세션 · 리포지토리 · Pydantic 스키마
│   ├── rules/             JSON 규칙 파일
│   ├── data/              톤 프로파일·응답 템플릿
│   └── reschedule_model_demo/  일정 재조정 ML 데모(scikit-learn)
├── database/              local_schema.sql(단일 소스) + DBML 설계
├── on_device/             온디바이스 모델·매니저 (음성/이미지/메모리/알림)
├── prompts/               LLM 프롬프트 텍스트
├── runtime/               SQLite DB · 로그 (생성물)
├── tests/                 테스트
└── scripts/               초기화·유틸 스크립트
```

---

## 빠른 시작

### 백엔드

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

### 프론트엔드

```bash
cd frontend
flutter pub get
flutter run
```

`.env`에 백엔드 Base URL을 설정합니다.

| 환경 | Base URL |
|------|----------|
| PC 로컬 | `http://127.0.0.1:8000` |
| Android Emulator | `http://10.0.2.2:8000` |
| 실제 기기(같은 Wi-Fi) | `http://{PC_IP}:8000` |

### LLM (선택)

`backend/.env`에 `OPENAI_API_KEY`를 넣고 필요한 `ENABLE_LLM_*` 플래그를 켜면 해당 기능이 LLM으로 확장됩니다. 키가 없거나 플래그가 꺼져 있으면 규칙/템플릿으로 동작합니다.

---

## 공통 API 응답

```json
{ "success": true, "message": "...", "data": { } }
```

주요 필드 — 일정 `data.schedule_draft`, 예약 후보 `data.recommended_candidates`, 예약 메시지 `data.generated_message`, 출발 알림 `data.leave_time`·`data.checklist`, 브리핑 `data.summary`·`data.key_points`, 감정 `data.emotion`·`data.coaching`.

---

## 설계 원칙

1. **키 없이도 동작** — 모든 AI 기능은 규칙/템플릿이 기본, LLM은 선택적 확장이며 실패 시 자동 폴백.
2. **단일 스키마 소스** — `database/local_schema.sql`이 유일한 진실. ORM은 이를 1:1 미러링하고, 트리거·CHECK 제약을 보존하기 위해 `metadata.create_all`을 쓰지 않음.
3. **프라이버시 우선** — 감정/메모리는 마스킹 저장, 감정 로그는 사용자 동의(`consent_snapshot=1`) 없이는 기록 불가.
4. **인증은 false positive 차단 우선** — 온디바이스 Smol은 최종 판정자가 아닌 blocker 선감지 전용이며(물/positive의 로컬 통과 금지), 애매한 근거는 통과시키지 않고 서버 VLM + Rule Engine으로 최종 판정. 기상 인증은 얼굴/신원이 아닌 시각적 맥락으로만 판정.

---

## 로드맵

- 온디바이스 VLM 인증: SmolVLM 단독 최종 인증은 탈락(FP 이력)하여 현재는 **blocker 선감지 전용**으로만 실기기 연결(모델 미배포 기기에선 자동으로 서버 경로). 서버 VLM fallback을 거쳐 Rule Engine이 최종 판정하며, 장기적으로 **YOLO/OpenImages detector + 규칙** 구조로 전환 예정(온디바이스 완결성·비용·실시간성 개선).
- 대시보드 mock 위젯·화면을 실제 API로 연결, 온디바이스 TFLite 의도·감정 분류기 실추론 연결(현재 규칙 기반). 세부 내역은 [남은작업_백로그.md](./남은작업_백로그.md) 참고.
- 서버 DB(PostgreSQL) 전환 및 다중 사용자 인증(현재 로컬 SQLite · `local-user` 단일 사용자).
