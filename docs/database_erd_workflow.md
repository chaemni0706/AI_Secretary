# AI 비서 주요 기능 5개 ERD 설계 순서

## 설계 원칙

1. 화면이나 Agent 이름을 그대로 테이블로 만들지 않는다.
2. 기능 수행 후 계속 기억해야 하는 데이터만 테이블 후보로 삼는다.
3. 각 테이블은 한 종류의 사실만 담당한다.
4. PK는 한 행을 식별하고, FK는 다른 테이블의 행을 가리킨다.
5. 검색·정렬·충돌검사에 필요한 값은 일반 컬럼으로 둔다.
6. LLM 추출 결과처럼 형태가 자주 바뀌는 값만 JSONB로 둔다.
7. 기능 하나를 확정할 때마다 예시 시나리오로 데이터 흐름을 검증한다.

## 작업 순서

### 0단계 — VSCode 환경 및 Git 브랜치
- `feature/erd-priority-5` 브랜치를 만든다.
- Codex와 dbdiagram 확장을 설치한다.
- `database/schema_mvp_working.dbml`을 연다.
- DBML Preview를 오른쪽에 연다.

### 1단계 — 공통 사용자 기반
확정할 테이블:
- users
- user_settings
- user_devices
- external_accounts
- calendars

질문:
- 로그인은 Google만 사용하는가?
- 로컬 캘린더도 지원하는가?
- 하나의 사용자가 여러 기기를 사용하는가?

### 2단계 — 기능 1: AI 일정 생성 + 일정 추천
확정할 테이블:
- ai_interactions
- schedule_recommendations
- schedule_candidates
- planner_items
- event_details

검증 시나리오:
- 사용자가 “금요일 저녁 빈 시간에 미용실 일정 잡아줘”라고 말한다.
- AI가 3개 후보 시간을 만든다.
- 사용자가 하나를 선택한다.
- 선택된 후보가 확정 일정으로 저장된다.

### 3단계 — 기능 2: 캘린더 + To-do 통합 대시보드
확정할 테이블:
- planner_items
- event_details
- todo_details
- calendars

검증 시나리오:
- 오늘 일정과 오늘 마감 To-do를 시간순으로 한 화면에 보여준다.

### 4단계 — 기능 3: AI 음성 브리핑(STT/TTS)
확정할 테이블:
- ai_interactions
- briefings

검증 시나리오:
- 음성 입력을 STT로 변환한다.
- 하루 브리핑 텍스트를 생성한다.
- TTS 음성 파일 참조값을 저장한다.

### 5단계 — 기능 4: 개인 맞춤 메모리 + 성향별 알림
확정할 테이블:
- user_settings
- user_memories
- reminders
- user_devices

검증 시나리오:
- “병원 갈 때는 진료카드를 챙긴다”는 메모리를 저장한다.
- 병원 일정 전에 사용자가 선호하는 말투로 준비물 알림을 만든다.

### 6단계 — 기능 5: 감정 기반 브리핑 및 생활 코칭
확정할 테이블:
- emotion_logs
- coaching_outputs
- briefings

검증 시나리오:
- 사용자의 감정 입력을 분석해 감정 기록을 저장한다.
- 일정 강도를 고려한 생활 코칭을 생성한다.

### 7단계 — 전체 검수
각 관계마다 다음을 확인한다.
- 부모 데이터가 삭제되면 자식 데이터는 어떻게 되는가?
- 필수 FK인가, 선택 FK인가?
- 중복을 막아야 하는 컬럼은 무엇인가?
- 개인정보와 감정 데이터의 보관 기간은 얼마인가?
- JSONB로 둔 데이터를 실제로 검색해야 하지는 않는가?

### 8단계 — 팀 공유 산출물
- 최종 DBML 문법 검증
- 전체 ERD PNG
- 핵심 관계만 보이는 요약 PNG
- 기능별 테이블 매핑표
