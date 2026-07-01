# 개인 맞춤 메모리 연동: 예약 · 알림 · 감정 코칭

## 1. 목적

새 메모리 기능을 만드는 것이 아니라, 기존 `memory`(user_memories) 구조를 **예약 후보
추천 · 알림 추천 · 감정 코칭**에 연결해 실제 개인화가 동작하도록 강화합니다.
모든 개인화 응답은 `personalization` 메타데이터(`personalization_applied`,
`memory_source`, `used_preferences`)를 포함해 Flutter가 개인화 여부를 확인할 수 있습니다.

MVP 전제: 멀티유저 인증 없음, 기본 `user_id="local-user"`, DB 스키마 변경 없음,
외부 API/실LLM 호출 없음, rule-based + 저장된 preference 기반.

## 2. 저장 가능한 preference

`GET/PUT /api/v1/memory/{user_id}/preferences/effective` 로 조회/저장합니다.
richer 필드는 기존 `user_memories` 테이블에 `pref_*` PREFERENCE 행으로 저장되어
스키마 변경이 없고, 기존 `memory_service` 값(`notification_preference`,
`default_buffer_minutes` 등)과 브리지됩니다.

| 필드 | 타입 | 기본값 | 용도 |
|---|---|---|---|
| `preferred_reservation_times` | `[time_bucket]` | `["afternoon","evening"]` | 예약 후보 가점 |
| `avoid_times` | `[time_bucket]` | `[]` | 예약 후보 감점 |
| `default_reminder_minutes` | `int≥0` | `30` | 기본 알림 시각 |
| `departure_buffer_minutes` | `int≥0` | `10` | 출발 알림 버퍼 (기존 `default_buffer_minutes` 브리지) |
| `late_prone` | `bool` | `false` | 지각 경향(예약/알림 여유↑) |
| `preferred_tone` | `neutral\|gentle\|warm` | `neutral` | 코칭 말투 |
| `coaching_style` | `supportive\|direct\|coaching` | `supportive` | 코칭 방식 |
| `stress_triggers` | `[str]` | `[]` | 스트레스 키워드 |
| `rest_recommendation_enabled` | `bool` | `true` | 휴식 제안 포함 여부 |
| `notification_style` | `normal\|soft\|strong` | `normal` | 알림 말투 |

`time_bucket` ∈ `early_morning, morning, afternoon, evening, late_night`.

## 3. 기본 preference fallback / merge 정책

- preference가 전혀 없으면 **기본값**으로 동작(`personalization_applied=false`, `memory_source=default_preference`).
- 일부 필드만 저장되면 기본값 위에 **merge**.
- invalid 값(음수 시간, 알 수 없는 enum, 잘못된 타입, 유효하지 않은 time_bucket)은 **무시하고 기본값** 유지 — 500 없음.
- 저장된 값이 하나라도 있으면 `personalization_applied=true`, `memory_source=stored_preference`.

## 4. 예약 후보 추천 반영 — `POST /api/v1/reservations/business-candidates`

기존 conflict-free 후보 집합은 그대로 두고(추천 자체는 preference 없이도 동작),
같은 조건 후보끼리 `personalization_score`(0~1)로 **안정 재정렬**합니다.

- 후보 시작시각의 time_bucket이 `preferred_reservation_times`에 있으면 +0.3
- `avoid_times`에 있으면 −0.4
- `late_prone`이면 이른 시간대(`early_morning`/`morning`) −0.1
- 선호 시간대 후보 `reason` 에 개인화 사유 포함
- 응답 `data.personalization` 에 메타데이터, 후보별 `personalization_score`(optional)

```json
"personalization": { "personalization_applied": true, "memory_source": "stored_preference",
  "used_preferences": ["preferred_reservation_times","avoid_times","late_prone"],
  "reason": "선호 시간대와 지각 경향을 반영해 후보 순서를 조정했습니다." }
```

## 5. 알림 추천 반영 — `POST /api/v1/notifications/recommend`

요청 `{user_id, title, category?, date?, start_time?, travel_minutes?}` →

- `default` 알림: `default_reminder_minutes`(+ late_prone이면 15분 일찍)
- `departure` 알림(start_time+travel_minutes 있을 때): `travel + departure_buffer_minutes`(+ late_prone 15분)
- `notification_style`(soft/normal/strong)로 메시지 톤 조정

```json
"reminders": [
  {"type":"default","minutes_before":40,"message":"40분 뒤 병원 예약이(가) 있어요. 천천히 준비해볼까요?"},
  {"type":"departure","minutes_before":45,"message":"이동 시간을 고려하면 병원 예약 45분 전부터 준비하면 좋아요. 천천히 준비해볼까요?"}
]
```

기존 `POST /notifications/plan`(저장 일정 기반)은 그대로 유지됩니다.

## 6. 감정 코칭 반영 — `POST /api/v1/emotion/coach`

요청 `{user_id, text, sleep_hours?, schedule_count?, todo_done_rate?}`. 기존
`emotion_analyzer`(rule-based, 비진단)를 재사용하고 preference로 다듬습니다.

- `preferred_tone`: gentle→"괜찮아요.", warm→"많이 애쓰고 있어요." 접두
- `coaching_style`: supportive/coaching/direct 로 문장 마무리 조정
- `stress_triggers` 키워드가 입력에 있으면 "할 일을 작게 나누기","마감 전 알림 설정하기" 보강
- `rest_recommendation_enabled=true`면 "10분 휴식하기" 포함, false면 휴식 제안 제외

```json
{ "emotion": "stress",
  "coaching_message": "괜찮아요. 스트레스가 높은 상태로 보입니다. ... 천천히 함께 해봐요.",
  "suggested_actions": ["10분 휴식하기","우선순위 정리하기","할 일을 작게 나누기"],
  "personalization": { "personalization_applied": true, "memory_source": "stored_preference",
    "used_preferences": ["preferred_tone","coaching_style","stress_triggers","rest_recommendation_enabled"] } }
```

비진단 원칙: "우울증/장애/진단" 등 임상 표현 금지, 감정은 단정하지 않고 "~로 보입니다"로 표현.

## 7. API 요청/응답 예시 (선호 저장)

요청 `PUT /api/v1/memory/local-user/preferences/effective`:

```json
{ "preferred_reservation_times": ["evening"], "avoid_times": ["early_morning"],
  "default_reminder_minutes": 40, "departure_buffer_minutes": 15, "late_prone": true,
  "preferred_tone": "gentle", "coaching_style": "supportive",
  "stress_triggers": ["과제","마감"], "rest_recommendation_enabled": true, "notification_style": "soft" }
```

응답 `data`: `{ "preference": {...}, "personalization_applied": true, "memory_source": "stored_preference" }`.

## 8. Flutter에서 사용할 필드

응답마다 `personalization.personalization_applied`, `personalization.memory_source`,
`personalization.used_preferences` 를 일관되게 확인하세요. 예약은 후보별
`personalization_score` 로 정렬/배지 표시, 알림은 `reminders[].minutes_before/message`,
코칭은 `coaching_message`/`suggested_actions` 를 그대로 표시하면 됩니다.

## 9. 현재 MVP 한계

- `user_id`는 값이 와도 단일 로컬 소유자(`local-user`) 기준으로 저장/조회(멀티유저·인증 미도입).
- `late_prone`의 "촉박한 후보"는 절대 현재시각이 아니라 이른 시간대(early_morning/morning) 근사로 처리.
- item_type/시간대 판정은 rule-based, timezone 저장은 naive 유지(스키마 변경 없음).
- 알림 추천은 저장 로직이 아니라 추천만 반환(푸시/영속화는 기존 `/notifications/plan` 담당).

## 10. 추후 개선 방향

- 실제 멀티유저: 인증 컨텍스트 기반 `user_id`로 preference/저장 소유자 분리.
- preference 학습: 사용 로그 기반으로 preferred_time/late_prone 자동 갱신.
- 코칭 고도화: LLM 사용 시에도 비진단 가드 유지, few-shot 톤 튜닝.
- 알림 영속화: `/notifications/recommend` 결과를 reminders 테이블에 저장하는 옵션.
