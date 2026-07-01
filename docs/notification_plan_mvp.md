# 알림 계획 MVP (맞춤 알림 · 준비물 · 출발 알림)

## 1. MVP 범위

이 기능은 **실제 OS 푸시가 아니라 "알림 계획(plan-only)"** 을 생성/저장/조회합니다.

| 구현함 | 구현 안 함 (MVP 제외) |
|---|---|
| 알림 계획 생성/저장/조회 | 실제 OS 푸시 / FCM / APNs / AlarmManager |
| 준비물 체크리스트 | 실제 백그라운드 알림 발송 |
| 출발 알림 시간 계산 | 실제 교통 API |
| Flutter 표시용 응답 | 실제 날씨 API |

모든 알림 계획 응답에는 다음이 포함되어 명시적으로 plan-only임을 표시합니다:

```json
"delivery": { "os_push_enabled": false, "status": "planned_only",
              "note": "MVP에서는 실제 OS 푸시가 아니라 알림 계획만 생성합니다." }
```

## 2. 실제 OS 푸시 vs 알림 계획

- 알림 계획 = 서버가 rule-based로 계산한 "언제·무엇을·왜" 추천. 실제 예약/발송이 아님.
- Flutter는 `delivery.status="planned_only"`이면 **"알림 계획/추천 알림"** 으로 표시해야 하며,
  실제 OS 알림이 예약된 것처럼 표시하면 안 됩니다. 실제 로컬 알림 스케줄링은 Flutter 후속 작업.

## 3. 일정(EVENT) 알림 계획 생성 흐름

```
parse/enhanced → confirm(EVENT 저장) → preference 조회
  → default 알림 + (위치 있으면) departure 알림 생성
  → category 기반 checklist 생성 → reminders 테이블에 저장(idempotent) → 응답 reminder_plan
```

- **default 알림**: `minutes_before = default_reminder_minutes`(late_prone이면 +15), `trigger_time = 시작시각 − minutes_before`, 톤은 `notification_style`/`preferred_tone` 반영, category 힌트 문구 추가.
- **departure 알림**(위치가 있을 때만): `minutes_before = 기본이동 30분 + departure_buffer_minutes(+late_prone 10분)`. 실제 교통 API 미사용(기본 이동 시간 기준)임을 reason에 명시.
- 위치 없음 → departure 미생성 + warning. 시작시각 없음/종일 → trigger_time null + warning.

## 4. TODO 마감 알림 흐름

- EVENT와 분리 처리하며 **출발 알림은 생성하지 않습니다.**
- `due_date`가 있으면 당일 오전 09:00 `deadline` 알림 생성(`minutes_before=null`).
- `priority=high`면 하루 전 18:00 알림 추가.
- `due_date` 없으면 알림 미생성 + warning.

## 5. 준비물 체크리스트 기준

- 기존 `rules/checklist_rules.json`을 재사용합니다(카테고리 매핑: health→hospital, work→meeting, meal→restaurant 등).
- 예약성 일정(health/beauty/meal 또는 제목에 "예약")이면 "예약 확인" 추가.
- 위치가 있으면 "장소 확인" 추가. 제출성 TODO(study/work)면 "제출 파일 확인" 추가.
- 항목명 기준 중복 제거. 각 항목은 `{item, reason}` 구조(Flutter 체크박스 UI용).
- 알 수 없는 category는 `etc` 기본 준비물로 안전 처리.

## 6. 출발 알림 계산 기준

```
출발 minutes_before = estimated_travel_minutes(기본 30) + departure_buffer_minutes(+ late_prone 보정 10)
trigger_time        = 시작시각 − minutes_before
```

## 7. 개인 preference 반영

`preference_service.get_effective_user_preference` 재사용: `default_reminder_minutes`,
`departure_buffer_minutes`, `late_prone`, `notification_style`, `preferred_tone`. 저장된 선호가
없으면 기본값(30분/10분/false/normal)으로 동작하며 `personalization.personalization_applied=false`.
사용된 선호는 `personalization.used_preferences`에 나열됩니다.

## 8. API 요청/응답 예시

**저장(confirm)** `POST /api/v1/ai/schedule/confirm`

```json
{ "user_id": "local-user",
  "parsed": { "title": "병원 예약", "date": "2026-07-01", "start_time": "15:00",
              "category": "health", "location": "강남역", "item_type": "EVENT" } }
```

응답 `data`에 기존 `schedule`(또는 `todo`) + `reminder_plan`이 함께 옵니다:

```json
{ "schedule": { "id": "...", "title": "병원 예약", "date": "2026-07-01", "start_time": "15:00" },
  "reminder_plan": {
    "reminders": [
      { "type": "default", "minutes_before": 30, "trigger_time": "2026-07-01T14:30:00",
        "message": "30분 뒤 병원 예약이(가) 있어요. 천천히 준비해볼까요? 신분증과 예약 확인을 챙겨주세요.",
        "reason": "사용자 기본 알림 시간과 부드러운 알림 톤을 반영했습니다." },
      { "type": "departure", "minutes_before": 40, "trigger_time": "2026-07-01T14:20:00",
        "message": "기본 이동 시간과 준비 여유 시간을 고려하면 14:20쯤 준비를 시작하면 좋아요.",
        "reason": "기본 이동 시간 30분, 출발 버퍼 10분을 반영했습니다. (실제 교통 API는 사용하지 않는 기본 이동 시간 기준)" }
    ],
    "checklist": [ { "item": "신분증", "reason": "병원 일정에 필요한 기본 준비물입니다." } ],
    "personalization": { "personalization_applied": true, "memory_source": "stored_preference",
                         "used_preferences": ["default_reminder_minutes","notification_style","departure_buffer_minutes"] },
    "delivery": { "os_push_enabled": false, "status": "planned_only" },
    "warnings": [] } }
```

**조회** `GET /api/v1/notifications/plans/{item_id}` → 저장된 EVENT/TODO의 `reminder_plan`을 재구성해 반환(동일 입력 → 동일 결과, idempotent). 없는 id는 404.

## 9. Flutter에서 표시할 필드

- 알림 카드: `reminder_plan.reminders[]`(type/minutes_before/trigger_time/message/reason)
- 준비물 UI: `reminder_plan.checklist[]`(item/reason)
- 출발 알림 UI: `type == "departure"`인 reminder
- `reminder_plan.delivery.status == "planned_only"`이면 "추천 알림"으로 표시(실제 예약 아님)

## 10. 현재 MVP 한계

- 실제 OS 푸시/스케줄링/교통·날씨 API 없음(계획 계산만).
- `estimated_travel_minutes`는 고정 30분(외부 API 미연동).
- `user_id`는 단일 `local-user` 기준 저장/조회(멀티유저·인증 미도입).
- 저장 datetime은 naive. dashboard item에는 reminder_summary를 추가하지 않았습니다(기존 계약 보존). confirm 응답과 조회 API로 충분.
- confirm 메시지는 기존 계약 유지("일정을 저장했습니다."/"할 일을 저장했습니다.")하고 알림 계획은 `data.reminder_plan`으로 additive 제공.

## 11. 추후 실제 OS 푸시 연동 시 필요한 작업

- Flutter 로컬 알림 스케줄링(flutter_local_notifications) 또는 FCM/APNs 연동, `trigger_time`을 실제 예약 시각으로 사용.
- 서버측 발송이 필요하면 백그라운드 스케줄러(APScheduler 등) + 디바이스 토큰 관리.
- 실제 교통 API(예상 이동시간)·날씨 API로 `estimated_travel_minutes`/weather 체크리스트 대체.
- `delivery.status`를 `scheduled`/`sent` 등 실제 상태로 확장, 재알림/취소 처리.
