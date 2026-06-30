# AI Secretary 데이터·라벨 가이드

기준 브랜치: `origin/Feature_CM`  
기준 확인 커밋: `2466e61`  
기준 기능: `POST /api/v1/ai/schedule/parse`

이 문서는 현재 팀장 브랜치의 Pydantic Schema, Rule JSON, `schedule_parser.py`의
실제 동작을 데이터셋 표준으로 고정하기 위한 가이드다.

---

## 1. 데이터셋 목적

일정 데이터는 두 가지 목적으로 분리한다.

1. **Rule 회귀 테스트**
   - 현재 `schedule_parser.py`가 반환해야 하는 값을 고정한다.
   - 코드 변경으로 기존 정상 기능이 깨지는 것을 탐지한다.
2. **향후 개선용 Annotation**
   - 현재 룰로 처리하지 못하는 장소, 기간, 복합 표현 등을 별도로 기록한다.
   - 이후 Slot/NER 모델 또는 LLM fallback 설계에 사용한다.

현재 동작과 개선 목표를 하나의 정답으로 섞지 않는다.

---

## 2. 공통 Enum

### Priority

허용값:

- `low`
- `medium`
- `high`

현재 코드에서는 소문자를 사용한다.

### Source

허용값:

- `ai`
- `user`

AI 일정 파서가 생성한 일정 초안은 `ai`를 사용한다.

### InputType

허용값:

- `text`
- `voice`

기본값은 `text`다.

---

## 3. Intent

### 현재 실제 구현값

- `create_schedule`
- `unknown`

`schedule_schema.py` 설명에는 `create_todo`, `query`도 예시로 있지만,
현재 `schedule_parser.py`가 실제 생성하는 값은 위 두 개다.

### 현재 Intent 판정 규칙

날짜, 시간, 제목, 카테고리 중 하나라도 인식되면 `create_schedule`이다.
모두 인식되지 않을 때만 `unknown`이다.

이 때문에 `"안녕"` 같은 일반 문장도 제목으로 인식되어
`create_schedule`이 되는 현재 한계가 있다.

---

## 4. Category

허용값:

- `hospital`
- `meeting`
- `school`
- `study`
- `beauty`
- `restaurant`
- `exercise`
- `personal`
- `etc`

`etc`는 기본값이다.

| Category | 키워드 |
|---|---|
| `hospital` | 병원, 진료, 치과, 검진, 내과, 치료 |
| `meeting` | 회의, 미팅, 팀플, 팀 회의, 회식 미팅 |
| `school` | 수업, 학교, 강의, 등교, 수강 |
| `study` | 과제, 공부, 시험, 마감, 스터디, 레포트, 보고서 |
| `beauty` | 미용실, 커트, 네일, 파마, 염색, 헤어 |
| `restaurant` | 식당, 밥, 저녁, 점심, 외식, 맛집, 회식, 디너, 런치 |
| `exercise` | 운동, 헬스, 필라테스, 요가, 러닝, 수영, PT |
| `personal` | 친구, 약속, 데이트, 모임, 만남 |
| `etc` | 위 규칙과 일치하지 않음 |

카테고리는 위에서 아래 순서로 검색하며 첫 번째 일치값을 반환한다.
따라서 여러 카테고리 키워드가 한 문장에 있으면 충돌할 수 있다.

---

## 5. Priority 규칙

우선순위 판정 순서:

1. `high_keywords`
2. `low_keywords`
3. `category_priority`
4. 기본값 `medium`

### High 키워드

- 마감
- 시험
- 발표
- 제출
- 긴급
- 중요
- 데드라인
- 면접

### Low 키워드

- 휴식
- 산책
- 여유
- 취미
- 낮잠

### Category 기본 Priority

| Category | Priority |
|---|---|
| `hospital` | `high` |
| `meeting` | `high` |
| `study` | `medium` |
| `school` | `medium` |
| `exercise` | `medium` |
| `personal` | `medium` |
| `beauty` | `medium` |
| `restaurant` | `medium` |
| `etc` | `medium` |

`priority_rules.json`의 `high_categories`는 현재
`_detect_priority()`에서 사용되지 않는다.

---

## 6. Schedule Parse Request

```json
{
  "input": "내일 오후 2시에 병원 예약 잡아줘",
  "input_type": "text",
  "current_datetime": "2026-06-29T10:00:00+09:00",
  "timezone": "Asia/Seoul"
}
```

| 필드 | 필수 | 설명 |
|---|---:|---|
| `input` | O | 분석할 사용자 원문 |
| `input_type` | X | `text` 또는 `voice`, 기본 `text` |
| `current_datetime` | X | 상대 날짜 해석 기준 ISO 8601 |
| `timezone` | X | 기본 `Asia/Seoul` |

재현 가능한 평가를 위해 데이터셋에서는 `current_datetime`을 고정한다.

---

## 7. Schedule Parse Response

공통 API Envelope:

```json
{
  "success": true,
  "message": "일정 정보를 추출했습니다.",
  "data": {}
}
```

`data` 구조:

```json
{
  "intent": "create_schedule",
  "confidence": 0.94,
  "slots": {
    "title": "병원",
    "date_expression": "내일",
    "time_expression": "오후 2시",
    "date": "2026-06-30",
    "start_time": "14:00",
    "end_time": "15:00",
    "category": "hospital",
    "location": null
  },
  "schedule_draft": {
    "title": "병원",
    "category": "hospital",
    "date": "2026-06-30",
    "start_time": "14:00",
    "end_time": "15:00",
    "location": null,
    "memo": null,
    "priority": "high",
    "source": "ai"
  },
  "missing_fields": []
}
```

현재 API 필드명은 `date`, `start_time`, `end_time`이다.
`normalized_date`, `normalized_start_time` 같은 별도 이름을 사용하지 않는다.

---

## 8. 날짜 파싱 범위

현재 지원:

- 오늘
- 내일
- 모레
- 글피
- 월요일~일요일
- 이번 주 금요일
- 금주 금요일
- 다음 주 금요일
- 담주 금요일
- 7월 3일

주요 규칙:

- 단독 요일은 기준일 이후 가장 가까운 해당 요일이다.
- 기준일과 같은 요일이면 기준일 당일이다.
- `N월 N일`이 이미 지났으면 다음 해로 넘긴다.
- 잘못된 날짜는 `date=null`, `missing_fields=["date"]` 처리한다.

현재 미지원 예:

- 다음 달 초
- 이번 달 말
- 7월 셋째 주 수요일
- 주말
- 3일 후
- 퇴근 후

---

## 9. 시간 파싱 범위

현재 지원 예:

- 오전 10시
- 오후 2시
- 아침 9시
- 저녁 7시
- 밤 11시
- 점심 1시
- 새벽 6시
- 14시
- 3시 30분

오전·오후 표현 없이 입력하면 현재 파서는 시간대를 임시 해석한 뒤
`time_ambiguity`를 추가한다.

예:

```json
{
  "input": "7월 3일 3시에 미용실 예약",
  "start_time": "15:00",
  "missing_fields": ["time_ambiguity"]
}
```

현재 코드에서는 `14시` 같은 24시간 표기도
`time_ambiguity`로 표시한다.

잘못된 시각 예:

- `25시`
- `14시 70분`

잘못된 시각은 `start_time=null`, `end_time=null`,
`missing_fields`에 `time`을 넣는다.

---

## 10. End Time

현재 종료 시각은 시작 시각에 항상 1시간을 더한다.

```text
14:00 -> 15:00
23:00 -> 00:00
```

`3시간`, `30분`, `1시간 30분` 같은 기간 표현은 제목에서는 제거되지만
종료 시각 계산에는 아직 반영되지 않는다.

---

## 11. Title 추출

날짜·시간 표현과 명령어 꼬리를 제거한다.

제거 예:

- 잡아줘
- 추가해줘
- 넣어줘
- 등록해줘
- 예약해줘
- 일정
- 스케줄
- 예약

따라서:

```text
내일 오후 2시에 병원 예약 잡아줘
```

의 현재 제목은 `병원 예약`이 아니라 `병원`이다.

---

## 12. Location

Schema에는 `location`이 있지만 현재 파서에는 장소 추출 함수가 없다.
현재 회귀 정답은 `location=null`로 둔다.

향후 NER용 Annotation에서는 다음처럼 별도로 기록할 수 있다.

```json
{
  "current_location": null,
  "desired_location": "서울역 근처"
}
```

---

## 13. Confidence

현재 `confidence`는 모델 확률이 아니라 Rule 완성도 점수다.

```text
기본값        0.40
날짜 인식    +0.18
시간 인식    +0.18
제목 인식    +0.10
카테고리 인식 +0.08
최대값        0.95
```

모든 항목이 인식되면 현재 계산 결과는 `0.94`다.

---

## 14. Missing Fields

현재 허용값:

- `date`
- `time`
- `title`
- `time_ambiguity`

순서는 현재 파서의 생성 순서를 유지한다.

---

## 15. JSONL 레코드 형식

```json
{
  "sample_id": "schedule_0001",
  "case_type": "regression",
  "request": {},
  "expected_data": {},
  "metadata": {
    "source": "team_written",
    "difficulty": "easy",
    "template_group": "hospital_relative_day_time"
  }
}
```

### case_type

- `regression`: 현재 정상 동작을 자동 테스트
- `known_limitation`: 현재 한계와 향후 기대 동작을 함께 기록

`known_limitation`은 다음 필드를 추가한다.

```json
{
  "current_behavior": "현재 코드의 동작 설명",
  "desired_behavior": {
    "description": "향후 개선 목표"
  }
}
```

---

## 16. 데이터 분리 기준

같은 템플릿에서 숫자나 날짜만 바꾼 문장은 같은 `template_group`으로 묶는다.
모델 학습 시 같은 `template_group`을 Train과 Test에 동시에 넣지 않는다.

권장 비율:

- Train 70%
- Validation 15%
- Test 15%

Rule 회귀 테스트 데이터는 학습용 split과 분리한다.

---

## 17. 개인정보 원칙

실제 이름, 전화번호, 이메일, 정확한 주소, 실제 병원명은 원본 그대로
Git에 올리지 않는다.

예:

- `010-1234-5678` -> `[PHONE_1]`
- 실제 병원명 -> `[MEDICAL_ORG_1]`
- 실제 주소 -> `[ADDRESS_1]`

---

## 18. 현재 확인된 개선 과제

1. `create_schedule`, `unknown` 외 Intent 미구현
2. 일반 대화도 일정으로 오분류 가능
3. 장소 추출 미구현
4. 기간이 종료 시각에 반영되지 않음
5. Category 키워드 충돌 가능
6. `14시` 같은 24시간 표기도 `time_ambiguity` 처리
7. Schedule Category와 Alert Category 문서 범위 불일치
8. `confidence`는 모델 확률이 아님
