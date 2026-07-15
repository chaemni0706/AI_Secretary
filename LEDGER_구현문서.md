# AI 가계부 (Ledger) 기능 구현 문서

기존 AI Secretary FastAPI 백엔드(Feature_CM 계열)에 **알림 기반 자동 거래 기록 +
영수증 스캔 거래 기록 + 소비 분석 대시보드**를 최소 변경으로 추가한 결과입니다.

- 기존 테스트 **244개 유지**, 신규 **29개 추가** → 전체 **273 passed**, 회귀 0건
- `OPENAI_API_KEY` 없이 전 테스트 통과 (LLM은 optional fallback)
- OCR 라이브러리 없이 전 테스트 통과 (이미지 업로드는 안전 fallback)
- 저장은 기존 SQLite 인프라 재사용 + 신규 테이블 1개(`ledger_transactions`)

---

## 1. 구현 파일 목록

### 기존 파일 수정 (2개 — 둘 다 최소 변경)

| 파일 | 변경 내용 |
|---|---|
| `backend/main.py` | import 튜플에 `ledger` 추가, 라우터 등록 튜플에 `ledger` 추가 (딱 2줄) |
| `database/local_schema.sql` | 파일 **끝에 append만**. 기존 174줄 바이트 동일, 기존 테이블/트리거/CHECK 불변 |

### 신규 파일

**API**
- `backend/api/ledger.py` — 전체 엔드포인트 (todo.py 패턴, `Depends(get_db)`)

**서비스 (9개)**
- `ledger_common.py` — 내부 카테고리 상수, 상호명 정규화, 금액 파싱, rule JSON 로딩(+in-code fallback)
- `ledger_notification_parser.py` — 알림 파싱 (expense/income/cancel/ignore)
- `receipt_parser.py` — 영수증 텍스트 rule-based 파싱
- `receipt_ocr_service.py` — OCR optional (없으면 None 반환, 서버 안 죽음)
- `merchant_category_engine.py` — 5단계 카테고리 분류
- `ledger_service.py` — 거래 저장/조회/확정/수정/삭제, 중복 방지, seed
- `spending_insight_engine.py` — 일간/월간 브리핑 (rule 기본, LLM optional)
- `recurring_payment_detector.py` — 반복 결제 감지
- `budget_alert_service.py` — 예산 사용률/경고

**DB / 스키마**
- `backend/database/ledger_models.py` — `LedgerTransaction` ORM (기존 `models.py` 미오염, 같은 `Base` 공유)
- `backend/database/ledger_repository.py` — 영속성 (기존 `repository.py` 미오염)
- `backend/database/schema/ledger_schema.py` — Pydantic 요청/응답 + UPPERCASE↔소문자 매핑

**rules (5개, `backend/rules/`)**
- `ledger_notification_rules.json`, `merchant_category_rules.json`,
  `merchant_search_mock.json`, `category_mapping_rules.json`, `ledger_budget_rules.json`

**테스트 (6개 + 헬퍼, `tests/`)**
- `ledger_test_utils.py` (공유 `client` fixture, conftest 미import)
- `test_ledger_parser.py`, `test_receipt_parser.py`, `test_merchant_category_engine.py`,
  `test_ledger_api.py`, `test_ledger_duplicate.py`, `test_ledger_dashboard.py`

---

## 2. 신규 테이블 (local_schema.sql append 분)

`ledger_transactions` 단일 테이블 + 인덱스 3개. enum은 UPPERCASE 저장, API는 소문자 응답
(기존 `planner_items`의 `SCHEDULED`↔`scheduled` 방식과 동일). `amount`는 INTEGER(원).
`duplicated_transaction_id`는 자기참조 FK 없이 TEXT, 무결성은 `LedgerService`가 관리.
배열형(`items`, `alternatives`)은 JSON TEXT. 전부 `IF NOT EXISTS`.

인덱스: `(user_id, date)` 대시보드/리포트, `(user_id, dedup_key)` 정확 dedup,
`(user_id, normalized_merchant, amount)` 퍼지 dedup 후보.

---

## 3. API 명세

모든 응답은 기존 envelope `{ "success", "message", "data" }`. 라이브 경로는 prefix
`/api/v1` 포함.

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

---

## 4. 주요 서비스 로직

### 4-1. 알림 파싱 (`ledger_notification_parser`)
- 거래 유형 판정 우선순위: **cancel > ignore > income > expense**.
  cancel을 최우선으로 두어 "결제취소"가 expense로 오분류되지 않게 함.
  ignore를 income/expense보다 앞에 두어 광고/쿠폰이 키워드에 걸려 저장되는 것을 방지.
- 금액: `5,800원 / 5800원 / 9,800 원 / 17,000 결제` 정규식으로 첫 금액 추출.
- 상호명: 금액 이후를 tail로 잘라내고 결제 키워드 제거 후 앞부분 유지
  (`스타벅스 강남역점 5,800원 결제` → `스타벅스 강남역점`).

### 4-2. 영수증 파싱 (`receipt_parser`)
- 상호명: 첫 줄. 금액: **합계/총액/결제금액/받을금액** 라인 우선, 없으면 최대 금액.
  합계 라인은 items에서 제외.
- 날짜/시간: 영수증 텍스트 우선, 없으면 `captured_at`.
- items: `<상품명> <금액>` 패턴 라인만 추출.

### 4-3. 카테고리 5단계 (`merchant_category_engine`)
1. `merchant_category_rules.json` → `rule_based` (conf 0.98)
2. `merchant_search_mock.json` → `mock_place_search` (모호 상호명은 alternatives + needs_confirmation)
3. `category_mapping_rules.json` → `category_mapping` (external → internal)
4. optional `llm_service.generate` → `llm` (키 없으면 건너뜀)
5. 실패 → `기타` / `fallback` / conf 0.3 / needs_confirmation=true

> 더현대서울·무신사처럼 mock_search에 `needs_user_confirmation`이 걸린 모호 상호명은
> 1단계(rule_based)를 **의도적으로 건너뛰고** 2단계로 넘겨, 명세대로 사용자 확인을 유도.
> income은 곧바로 `수입` 카테고리로 단락.

### 4-4. 브리핑 (`spending_insight_engine`)
- rule 기반 템플릿 문장이 기본. LLM은 키가 있을 때만 시도하고 실패 시 템플릿으로 fallback.

---

## 5. 중복 방지 로직 (`ledger_service`)

두 개의 지문:
- **`dedup_key`** = sha1(`user_id | normalized_merchant | amount | transaction_type | date`)
  — "의미"가 같으면 동일. 같은 알림 재전송(2-1)과 알림↔영수증 교차(2-2)를 모두 잡음.
  두 입력 모두 같은 canonical 튜플로 환원되기 때문.
- **`source_hash`** = sha1(원본 입력: source_type + raw_text + 수신/촬영 시각 등)
  — 동일 재전송 감사/디버그용.

판정 순서:
1. `dedup_key` 정확 일치 조회 (DELETED 제외) → 있으면 중복.
2. 퍼지: 같은 `normalized_merchant` + `amount ±100원` 후보 중, `transaction_type` 동일하고
   `occurred_at` 10분 이내(또는 같은 날짜 merchant+amount 동일) → 중복.

중복이면 신규 생성 없이:
```json
{
  "success": true,
  "message": "이미 등록된 거래로 판단되어 기존 거래를 반환합니다.",
  "data": { "duplicate": true, "duplicated_transaction_id": "tx_...", "transaction": { ... } }
}
```
`ignore` 알림은 저장하지 않고 `stored=false`로 응답.

status 값: `pending / confirmed / duplicate / deleted / needs_review` (+ ignore 알림은 `ignored`).

---

## 6. 영수증 스캔/OCR 로직

- **receipt_text (JSON)**: MVP 기본 경로. `receipt_parser`가 rule-based로 파싱 후 저장.
- **이미지 업로드 (multipart)**: `receipt_ocr_service.extract_text`가 OCR 백엔드를
  lazy 확인. pytesseract/PIL이 없으면 **None 반환** → API는 `status=needs_review`,
  `stored=false`의 안전 응답(HTTP 200). 어떤 경우에도 500으로 죽지 않음.
- pytesseract/easyocr는 **필수 의존성 아님**. 실제 OCR 붙일 땐 `_try_ocr`만 구현하면 됨.

---

## 7. Swagger 테스트용 request / response 예시

### 7-1. POST /api/v1/ledger/notifications/simulate
Request:
```json
{ "user_id": "user-1", "app_name": "KB국민카드", "title": "카드승인",
  "body": "스타벅스 강남역점 5,800원 결제", "received_at": "2026-12-31T14:20:00" }
```
Response `data` (실제 출력):
```json
{ "transaction_id": "tx_...", "source_type": "notification", "transaction_type": "expense",
  "amount": 5800, "merchant": "스타벅스 강남역점", "category": "카페",
  "category_source": "rule_based", "confidence": 0.98, "needs_user_confirmation": false,
  "date": "2026-12-31", "time": "14:20", "occurred_at": "2026-12-31T14:20:00",
  "status": "pending", "duplicate": false }
```

### 7-2. POST /api/v1/ledger/receipts/scan
Request:
```json
{ "user_id": "user-1",
  "receipt_text": "스타벅스 강남역점\n2026-12-31 14:20\n아이스 아메리카노 4,500\n카페라떼 5,300\n합계 9,800원\n카드결제",
  "captured_at": "2026-12-31T14:25:00" }
```
Response `data` (실제 출력):
```json
{ "transaction_id": "tx_...", "source_type": "receipt_scan", "transaction_type": "expense",
  "merchant": "스타벅스 강남역점", "amount": 9800, "category": "카페",
  "category_source": "rule_based", "confidence": 0.98, "needs_user_confirmation": false,
  "occurred_at": "2026-12-31T14:20:00", "date": "2026-12-31", "time": "14:20",
  "items": [ {"name": "아이스 아메리카노", "amount": 4500}, {"name": "카페라떼", "amount": 5300} ],
  "status": "pending", "duplicate": false }
```

### 7-2b. POST /api/v1/ledger/receipts/scan-image (OCR 미가용 시)
multipart form: `user_id`, `captured_at`, `file`. Response `data`:
```json
{ "transaction_id": null, "source_type": "receipt_scan", "status": "needs_review",
  "ocr_available": false, "duplicate": false, "stored": false, "filename": "receipt.jpg" }
```

### 7-3. GET /api/v1/ledger/dashboard?user_id=user-1&month=2026-12&selected_date=2026-12-31
Response `data`: `summary / calendar / selected_date(+briefing,+transactions) /
pending_transactions / budget_alerts / recurring_preview`.

### 7-4. GET /api/v1/ledger/report?user_id=user-1&month=2026-12
Response `data` (seed 후 실제 출력, 발췌):
```json
{ "month": "2026-12",
  "summary": { "month_expense": 131300, "month_income": 500000, "balance": 368700 },
  "category_analysis": [ {"category": "통신_공과금", "amount": 69000, "ratio": 53}, ... ],
  "budget_usage": [ {"category": "구독_콘텐츠", "budget": 30000, "spent": 17000, "usage_rate": 57, "status": "normal"}, ... ],
  "recurring_payments": [ {"merchant": "KT 통신비", ...}, {"merchant": "NETFLIX", ...} ],
  "briefing": { "title": "12월 AI 소비 브리핑", "message": "..." } }
```

### 7-8. POST /api/v1/ledger/mock/seed?user_id=user-1
Response `data`: `{ "user_id": "user-1", "count": 7, "transactions": [ ... ] }` (2회 호출해도 count 7 유지).

---

## 8. 프론트엔드 연동용 응답 구조

- **enum은 전부 소문자**: `transaction_type` = expense|income|cancel|ignore,
  `source_type` = notification|receipt_scan|manual|seed,
  `status` = pending|confirmed|duplicate|deleted|needs_review.
- **amount**: 정수(원). **date**: `YYYY-MM-DD`. **time**: `HH:MM`. **occurred_at**: ISO datetime.
- 모든 거래 응답에 `date, time, amount, category, status, confidence, source_type,
  duplicate, needs_user_confirmation`이 항상 포함되어 UI가 바로 사용 가능.
- **화면 1 (홈)**: `dashboard` 응답 그대로 — summary / calendar / selected_date /
  pending_transactions / budget_alerts / recurring_preview.
- **화면 2 (리포트)**: `report` 응답 그대로 — summary / category_analysis /
  budget_usage / recurring_payments / briefing.

---

## 9. pytest 실행 명령어

```bash
# 최소 의존성 (실제 프로젝트 requirements.txt로 대체 가능)
pip install fastapi "uvicorn[standard]" python-multipart pydantic pydantic-settings \
            sqlalchemy pytest httpx

# 전체 (기존 244 + 신규 29 = 273)
python -m pytest -q

# 가계부만
python -m pytest tests/test_ledger_parser.py tests/test_receipt_parser.py \
  tests/test_merchant_category_engine.py tests/test_ledger_api.py \
  tests/test_ledger_duplicate.py tests/test_ledger_dashboard.py -v
```
전체 실행 결과: **273 passed**.

---

## 10. 프로토타입 vs 실제 서비스 범위

**구현함(프로토타입)**: mock 알림 POST, receipt_text rule-based 파싱, mock place search
(JSON), rule 기반 카테고리/브리핑, in-DB dedup, idempotent seed.

**구현 안 함(실서비스 몫)**: 실제 SMS 권한, Android NotificationListener, 실제
카드사/금융 API, 실제 네이버/카카오 장소 검색 API, 필수 OCR 엔진, LLM 상시 사용
(모두 optional / mock / 구조만).

---

## 11. 한글 커밋 메시지 (추천)

```
feat(ledger): AI 가계부 기능 추가 (알림/영수증 거래 기록 + 소비 분석 대시보드)

- 신규 ledger_transactions 테이블 추가 (local_schema.sql append, 기존 DDL 불변)
- 알림/영수증 rule-based 파싱 및 5단계 카테고리 분류 엔진 구현
- dedup_key/source_hash 기반 중복 거래 방지 (알림 재전송·알림↔영수증 교차 포함)
- 대시보드/월간 리포트/예산 경고/반복 결제 감지 API 구현
- 영수증 이미지 OCR은 optional fallback (라이브러리 없어도 500 없이 needs_review)
- LLM fallback은 optional (OPENAI_API_KEY 없어도 동작)
- idempotent mock seed 및 pytest 29건 추가 (기존 244건 회귀 없음, 총 273 passed)

기존 planner/일정/할일 테이블·트리거·API 무영향. main.py는 라우터 등록 2줄만 수정.
```

세부 커밋으로 나눌 경우:
```
chore(db): ledger_transactions 테이블 및 인덱스 추가 (local_schema.sql append)
feat(ledger): 알림/영수증 파서 및 카테고리 분류 엔진 추가
feat(ledger): 거래 저장·중복 방지·CRUD·seed (LedgerService/Repository)
feat(ledger): 대시보드/리포트/예산/반복결제 API 추가
test(ledger): 파서·중복·대시보드 pytest 29건 추가
```
