# 포비(Pobi) — 아키텍처 상세 문서

> 나의 완벽한 AI 비서 **포비**. 프론트엔드 · 백엔드 · AI · 데이터베이스 4개 레이어의 구조를 상세히 정리한 문서입니다.
> 프로젝트 개요와 실행 방법은 [README.md](./README.md) / [README_전체.md](./README_전체.md)를 참고하세요.

---

## 목차

1. [전체 구성 한눈에 보기](#1-전체-구성-한눈에-보기)
2. [프론트엔드 (Flutter)](#2-프론트엔드-flutter)
3. [백엔드 (FastAPI)](#3-백엔드-fastapi)
4. [AI 레이어](#4-ai-레이어)
5. [데이터베이스](#5-데이터베이스)
6. [데이터 흐름 예시](#6-데이터-흐름-예시)

---

## 1. 전체 구성 한눈에 보기

```
┌─────────────────────────────────────────────────────────────┐
│                  Flutter 앱 (Android, 온디바이스)             │
│  화면 · 상태관리(Provider) · Dio HTTP 클라이언트              │
│  온디바이스: Vosk STT("포비" 웨이크워드) / TFLite 감정·의도   │
│              분류 / 포그라운드 서비스 / 로컬 알림             │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST (JSON)  {success, message, data}
┌───────────────────────────▼─────────────────────────────────┐
│                     FastAPI 백엔드                            │
│  api/ (라우터)  →  services/ (도메인 로직)  →  database/      │
│  규칙/템플릿 우선 + 선택적 LLM 확장(OpenAI, 기본 OFF)         │
└───────────────────────────┬─────────────────────────────────┘
                            │ SQLAlchemy 2.0 (동기)
┌───────────────────────────▼─────────────────────────────────┐
│              SQLite (runtime/ai_secretary_local.db)          │
│  단일 소스 스키마: database/local_schema.sql                 │
└─────────────────────────────────────────────────────────────┘
```

핵심 설계 원칙은 **"키 없이도 동작한다"** 입니다. 모든 AI 기능은 규칙/템플릿 기반으로 기본 동작하고, OpenAI 키가 있을 때만 일부 문장 생성을 LLM으로 확장합니다.

---

## 2. 프론트엔드 (Flutter)

`frontend/` — Dart/Flutter 기반 Android 앱. Toss 스타일 디자인 토큰과 Pretendard 폰트를 사용합니다.

### 기술 스택

| 영역 | 패키지 |
|------|--------|
| HTTP 통신 | `dio` |
| 상태관리 | `provider` |
| 환경변수 | `flutter_dotenv` |
| 캘린더 UI | `table_calendar` |
| 위치/지도 | `geolocator`, `google_maps_flutter` |
| 음성 STT/TTS | `speech_to_text`, `flutter_tts` |
| 온디바이스 웨이크워드 | `vosk_flutter_2` (한국어 모델, 로컬 vendoring) |
| 상시 대기 | `flutter_foreground_task` |
| 푸시/알림 | `firebase_messaging`, `flutter_local_notifications`, `timezone` |
| 로컬 저장 | `shared_preferences` |
| 이미지 | `image_picker` |

### 폴더 구조 (`frontend/lib/`)

- **`screens/`** — 화면 단위 UI. 캘린더/일정(추가·수정·상세), To-do, AI 채팅, 음성 채팅, 브리핑, 예약 추천·문의 메시지, 장소 추천, 이미지 인증, 가계부(리포트 포함), 마이페이지·설정, 위젯 대시보드 등.
- **`widgets/`** — 재사용 위젯. 특히 `dashboard_widgets/`는 사용자가 배치를 커스터마이즈하는 홈 위젯들(날씨, 예산, 브리핑, 준비물, 예약 후보, 지출 분석, 주/월 캘린더, OCR 인증 등).
- **`services/`** — 백엔드 API 클라이언트와 온디바이스 서비스. `api_client.dart`가 Dio 공통 클라이언트이고, 도메인별로 `schedule_api`, `todo_api`, `ledger_api`, `briefing_api`, `emotion_api`, `reservation_api`, `weather_api`, `verification_api`, `voice_*_api` 등으로 분리. 온디바이스 쪽은 `hotword_service`(웨이크워드), `voice_stt_service`/`voice_tts_service`, `intent_classifier_service`·`emotion_model_classifier_service`(TFLite), `local_schedule_parser`, `briefing_scheduler_service` 등.
- **`models/`** — API 응답/도메인 DTO. `*_mappers.dart`가 서버 enum(UPPERCASE) ↔ 앱 표현을 변환.
- **`data/`** — 위젯 카탈로그·레이아웃 저장, mock 데이터.
- **`theme/`** — `toss_tokens`, `app_theme`, 도메인별 스타일(ledger/schedule/todo).
- **`core/utils/`** — 날짜 파싱 유틸.

### 온디바이스 AI (`on_device/`)

앱에 직접 탑재되는 경량 모델·매니저입니다.

- `voice/wake_word_service.dart`, `voice/stt_service.dart` — "포비" 호출어 상시 감지 + STT.
- `image/image_classifier.tflite`, `image/image_service.dart` — 온디바이스 이미지 분류.
- `memory/`, `notification/` — 선호/프로필 관리, 리마인더·일정 체크.

---

## 3. 백엔드 (FastAPI)

`backend/` — Python 3.11 / FastAPI. 진입점은 `backend/main.py`, 설정은 `backend/core/config.py`(pydantic-settings).

### 레이어 구조

```
api/         라우터 (엔드포인트 정의, 얇게 유지)
services/    도메인 로직 (규칙 엔진 + 선택적 LLM)
database/    ORM 모델 · 세션 · 리포지토리 · Pydantic 스키마
rules/       JSON 규칙 파일 (카테고리/감정/알림/예약 등)
data/        톤 프로파일, 응답 템플릿, mock 장소
routers/     보조 라우터 (medicine, routines)
docs/        API 문서
```

### 주요 API 도메인 (`api/`)

일정 파싱(`schedule`), 로컬 일정/할일 CRUD(`local_schedule`, `todo`), 대시보드(`dashboard`), 예약 추천·문의(`reservation`, `message`), 출발/준비물 알림(`alert`), 브리핑(`briefing`), 감정 분석·코칭(`emotion`, `coaching`), 사용자 메모리/선호(`memory`, `user_preferences`), 알림 계획(`notification`), 가계부(`ledger`), 장소 추천(`place`), 이동시간(`travel`), 날씨(`weather`), 이미지/기상 인증(`image_verification`, `verification`), 음성 라우팅(`voice`), 채팅(`chat`), 헬스체크(`health`).

공통 응답 구조:

```json
{ "success": true, "message": "...", "data": { } }
```

### 서비스 계층 (`services/`)

60개 이상의 서비스 모듈이 도메인별로 분리되어 있습니다. 대표적으로:

- **일정 파싱** — `schedule_parse_service`, `schedule_rule_parser`, `schedule_slot_extractor`, `schedule_title_extractor`, `schedule_clarification`(부족 정보 질문), `schedule_llm_parser`(선택적 LLM).
- **예약** — `reservation_candidate_service`(빈 시간 탐색·점수화), `reservation_from_store_service`, `reservation_message_service`, `reschedule_recommender`.
- **알림/브리핑** — `departure_alert`, `notification_plan_builder`, `reminder_recommender`, `briefing_generator`.
- **감정/코칭** — `emotion_analyzer`, `emotion_coach_service`, `empathy_engine`, `life_coaching_service`.
- **가계부(AI 가계부)** — `ledger_notification_parser`(카드 알림 파싱), `receipt_ocr_service`/`receipt_parser`(영수증), `merchant_category_engine`(상호→카테고리), `recurring_payment_detector`, `spending_insight_engine`, `budget_alert_service`.
- **인증(Verification)** — `verification_orchestrator`(라우팅), `vision_analyzer`/`local_vlm_analyzer`, `image_verification_rule_engine`, `wakeup_verification_service`.
- **공통 인프라** — `llm_service`(OpenAI 래퍼), `memory_service`, `preference_service`, `weather_service`, `travel_time_service`, `naver_maps_client`/`naver_place_client`, `tts_response_builder`, `voice_intent_router`.

### 규칙 파일 (`rules/`, `data/`)

카테고리 매핑, 감정/공감, 알림, 예약 메시지, 우선순위, 체크리스트, 톤 프로파일 등이 JSON으로 외부화되어 있어 코드 수정 없이 규칙을 조정할 수 있습니다.

---

## 4. AI 레이어

포비의 AI는 **3단계 처리 경로**로 구성됩니다. (`ai_local_requests` 테이블의 `processing_route` 컬럼이 `RULE / LLM / HYBRID`로 이를 기록)

### 4.1 규칙/템플릿 (기본, 항상 동작)

일정 파싱, 예약 후보 시간 계산·점수화, 카테고리 분류, 감정 분류, 알림 계획 등 핵심 로직은 규칙 엔진과 템플릿으로 처리됩니다. **OpenAI 키 없이도 전 기능이 작동**합니다.

### 4.2 선택적 LLM 확장 (OpenAI, 기본 OFF)

`config.py`의 feature flag로 개별 제어하며 기본값은 모두 OFF입니다. 실패하거나 비활성일 때는 규칙/템플릿으로 자동 폴백합니다.

| 플래그 | 역할 |
|--------|------|
| `ENABLE_LLM_SCHEDULE_PARSE` | 규칙 파서가 놓친 일정 문장 보조 파싱 |
| `ENABLE_LLM_INTENT` | 규칙 분류가 매칭 실패할 때만 의도 보조 분류 |
| `ENABLE_LLM_CLARIFY` | 부족 정보 질문을 자연스럽게 생성 |
| `ENABLE_LLM_RESCHEDULE` | 후보 계산은 규칙, **최상위 후보 설명 문장만** LLM |
| `ENABLE_LLM_MEMORY` | 발화에서 지속적 선호 추출·저장 |
| `ENABLE_LLM_MULTITURN` | "아까 그거 오후로" 같은 모호한 참조 해석 |

기본 모델: `OPENAI_MODEL=gpt-4o-mini`, 비전 `gpt-4.1-mini`. 프롬프트는 `prompts/`에 텍스트로 분리(브리핑/감정코칭/메모리/플래너/관계/예약).

### 4.3 이미지 인증 (VLM)

인증은 책임에 따라 두 범주로 나뉩니다.

1. **VLM 기반 시각 인증** — water / exercise / study. 이미지 → VisionAnalyzer → Rule Engine 판정. false positive 차단을 우선(빈 컵/색 음료/게임 화면 등은 PASS 금지).
2. **세션/시간 기반 인증** — wakeup(기상). 서버 수신 시각 · 일회성 세션 · 이미지 SHA256 중복검사 · 재촬영 제한으로 판정. **VLM/Rule Engine 미사용**(휴대폰·EXIF·사진 표시 시각은 최종 판정 기준으로 쓰지 않음).

**온디바이스 VLM 검토 이력** (루트의 `SMOLVLM_ONDEVICE_EVAL_FINAL_DECISION.md`, `QWEN3B_*.md`):

- SmolVLM-500M 온디바이스 단독 인증 후보는 real-only 171장 평가에서 FP=9로 **탈락(NO-GO)**.
- 대체로 Qwen-3B(Qwen2.5-VL-3B) unified verification을 **임시 baseline**으로 채택.
- 향후 **YOLO/OpenImages 기반 detector + 규칙** 구조로 전환하여 온디바이스 완결성·비용·실시간성 개선 예정.

### 4.4 ML 데모 (`backend/reschedule_model_demo/`)

일정 재조정 후보 점수화용 로지스틱 회귀 모델(`reschedule_logistic_model.joblib`) + 학습 노트북/데이터 딕셔너리/스코어링 결과가 포함되어 있습니다. scikit-learn 기반.

### 4.5 그 외 AI 관련 스택

`requirements.txt` 기준: LangChain + Chroma/FAISS + sentence-transformers(RAG 기반 자산), transformers/torch, spaCy·kiwipiepy·dateparser(한국어 NLP), PaddleOCR(약봉투 OCR), OpenCV/Pillow(이미지), gTTS(음성).

---

## 5. 데이터베이스

### 5.1 개요

- **엔진**: 로컬 전용 **SQLite**. 외부 DB 서버 없음.
- **파일 위치**: `runtime/ai_secretary_local.db` (상대 경로는 프로젝트 루트 기준으로 고정 — 작업 디렉터리와 무관).
- **단일 소스 스키마**: `database/local_schema.sql`. 이 파일이 **유일한 진실의 원천(single source of truth)** 입니다.
- **초기화**: `python scripts/init_local_db.py` — raw SQL을 그대로 적용합니다. **`Base.metadata.create_all`을 의도적으로 사용하지 않아** 트리거와 CHECK 제약이 그대로 보존됩니다.
- **ORM**: SQLAlchemy 2.0 (동기). `backend/database/models.py`가 SQL 스키마를 1:1로 미러링합니다. 새 테이블을 ORM으로 만들지 않습니다.
- **세션**: `backend/database/session.py`. 커넥션마다 `PRAGMA foreign_keys=ON`을 걸어 FK/CASCADE가 raw SQL과 동일하게 동작합니다. FastAPI 의존성 `get_db()`가 세션을 열고 항상 닫습니다.

### 5.2 enum 규약

enum류 컬럼은 스키마에서 **UPPERCASE + CHECK 제약**으로 저장하고(`SCHEDULED`, `EVENT` 등), API/Pydantic 레이어는 **소문자**를 사용합니다. 그 사이를 `services/planner_mapping.py` 등 매핑 계층이 변환합니다.

### 5.3 테이블 (총 12개)

#### 일정/할일 도메인

핵심 설계는 **일정(EVENT)과 할일(TODO)을 별도 테이블로 두지 않고** 단일 `planner_items`(+ 1:1 상세 테이블)로 모델링한 것입니다. `schedules`/`todos` 테이블은 존재하지 않습니다.

| 테이블 | 역할 | 핵심 컬럼 / 제약 |
|--------|------|-----------------|
| `users` | 사용자 | `user_id`(PK) |
| `user_settings` | 사용자 설정 | 타임존/로케일, `default_reminder_minutes`, `memory_enabled`, `emotion_coaching_enabled`, `sensitive_data_consent` (모두 0/1 CHECK) |
| `calendars` | 캘린더 | `is_primary` — **사용자당 primary 1개** 부분 유니크 인덱스(`uq_calendars_one_primary`) |
| `planner_items` | 일정+할일 통합 | `item_type IN ('EVENT','TODO')`, `status IN (DRAFT/SCHEDULED/IN_PROGRESS/COMPLETED/CANCELLED)`, `priority`, `source_type IN (MANUAL/AI/EXTERNAL_SYNC)`, `deleted_at`(소프트 삭제) |
| `event_details` | EVENT 1:1 상세 | `start_at`/`end_at`(CHECK end>start), `is_all_day`, `location_text`, `travel_time_minutes`, 외부 이벤트 dedup 유니크 인덱스 |
| `todo_details` | TODO 1:1 상세 | `due_at`, `planned_date`, `estimated_minutes`(>0), `started_at`, `completed_at` |
| `reminders` | 리마인더 | `reminder_type IN (STANDARD/PREPARATION/DEPARTURE/WEATHER_CONTEXT)`, `trigger_at`, `status`, 중복방지 유니크 인덱스 |

#### AI/개인화 도메인

| 테이블 | 역할 | 핵심 컬럼 |
|--------|------|-----------|
| `user_memories` | 사용자 메모리 | `memory_type IN (PREFERENCE/PERSONA/PLACE/PREPARATION/PATTERN/FACT)`, `memory_value_masked`(마스킹 저장), `importance`/`confidence`(0~1), `is_active` |
| `emotion_logs` | 감정 로그 | `primary_emotion`, `source_text_masked`, **`consent_snapshot=1` 강제 CHECK**(동의 없으면 기록 불가) |
| `briefings` | 브리핑 기록 | `briefing_type IN (MORNING/DAILY/WEEKLY/ON_DEMAND)`, `delivery_channel IN (IN_APP/TTS/PHONE)`, `status` |
| `ai_local_requests` | AI 요청 이력 | `input_mode IN (TEXT/VOICE)`, `input_text_masked`, `intent`, `processing_route IN (RULE/LLM/HYBRID)`, `confidence`, `status` |

#### AI 가계부 도메인 (append-only, 독립)

`ledger_transactions` — planner 계열과 **완전히 독립**된 신규 테이블. 카드 알림/영수증/수동 입력에서 거래를 기록합니다.

- 출처: `source_type IN (NOTIFICATION/RECEIPT_SCAN/MANUAL/SEED)`, 원문 보존(`raw_text`, `app_name`, `title`).
- 거래: `merchant`/`normalized_merchant`, `amount`(KRW 정수, ≥0), `transaction_type IN (EXPENSE/INCOME/CANCEL/IGNORE)`.
- 분류: `category`, `category_source`(rule_based / receipt_rule / notification_rule / llm / user_override 등), `confidence`, `needs_user_confirmation`, `alternatives_json`.
- 시각: `occurred_at`(ISO), `date`(집계 키), `time` 분리 저장.
- 상태/중복: `status IN (PENDING/CONFIRMED/DUPLICATE/DELETED/NEEDS_REVIEW)`, `dedup_key`(정확 일치 지문), `source_hash`(재전송 감지), `duplicated_transaction_id`(자기참조 FK를 걸지 않고 서비스 계층에서 무결성 관리).
- 상세: `items_json`(영수증 품목), `is_recurring`, `memo`.
- ORM: `backend/database/ledger_models.py`, 리포지토리 `ledger_repository.py`.

### 5.4 트리거 & 인덱스

- **트리거** — `trg_event_item_type_insert`, `trg_todo_item_type_insert`: 상세 테이블에 INSERT할 때 부모 `planner_items.item_type`이 일치하지 않으면 `RAISE(ABORT)`로 차단(EVENT 상세는 EVENT에만, TODO 상세는 TODO에만).
- **조회 인덱스** — `idx_planner_items_dashboard`(대시보드용 user+삭제여부+상태+정렬), `idx_user_memories_lookup`, `idx_ledger_tx_user_date`(월별 리포트).
- **중복 방지 유니크/부분 인덱스** — primary 캘린더 1개, 외부 이벤트 ID, 리마인더 중복, 가계부 dedup/fuzzy.

### 5.5 데이터 접근 계층

- `repository.py` — planner_items/event/todo/memory/reminder CRUD 및 조회(예: `list_events_by_date`, `list_todos_by_due_date`, `upsert_memory`, `soft_delete_planner_item`).
- `ledger_repository.py` — 가계부 전용.
- `schema/` — 도메인별 Pydantic 스키마(요청/응답 검증). alert/briefing/chat/dashboard/emotion/ledger/memory/notification/place/reservation/schedule/todo/travel/verification/weather 등.
- `init_db.py` — 스키마 적용 + **멱등 컬럼 마이그레이션**(SQLite에 `ADD COLUMN IF NOT EXISTS`가 없어 `PRAGMA table_info`로 존재 확인 후 누락 컬럼만 추가. 예: `ledger_transactions.memo`).

### 5.6 설계 문서 & 서버 스키마

- `database/schema_mvp_working.dbml`, `schema_local_mvp.dbml`, `schema_server_minimal.dbml` — DBML 설계 문서.
- `database/server_schema_postgres.sql` — 향후 서버 DB(PostgreSQL) 최소 스키마. `requirements.txt`에 `alembic`, `pymysql`이 포함되어 있으나 **현재 로컬 런타임은 SQLite**이며, 서버 DB는 로드맵 단계입니다.

---

## 6. 데이터 흐름 예시

**"내일 3시 강남에서 미팅 잡아줘" (음성)**

1. 앱: Vosk가 "포비" 감지 → STT로 문장 변환 → `voice_api`로 전송.
2. 백엔드: `schedule_parse_service`가 규칙으로 날짜/시간/장소/카테고리 추출(부족하면 `schedule_clarification`이 되물음). 요청은 `ai_local_requests`에 `processing_route=RULE`로 기록.
3. 앱이 확인하면 `local_schedule` API → `planner_items`(EVENT) + `event_details` INSERT(트리거가 타입 일치 검증).
4. `notification_plan_builder`가 출발/준비물 리마인더 계산 → `reminders` INSERT.
5. 다음 날 아침 `briefing_generator`가 오늘 일정을 모아 브리핑 생성 → `briefings` 기록, 앱이 전화형 알림으로 표시.

**카드 결제 알림 → 가계부 자동 기록**

1. 앱의 알림 수신 서비스가 카드사 알림 캡처 → `ledger` API 전송.
2. `ledger_notification_parser`가 상호/금액/시각 파싱, `merchant_category_engine`이 카테고리 분류.
3. `dedup_key`/`source_hash`로 중복(재전송·영수증 교차) 검사 후 `ledger_transactions`에 저장(`status=PENDING`, 애매하면 `needs_user_confirmation=1`).
4. `spending_insight_engine`/`budget_alert_service`가 월 집계·예산 경고 생성 → 대시보드 위젯/리포트에 노출.
