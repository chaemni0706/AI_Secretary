# 예약 후보 → 예약 메시지 생성 연동 (draft-only)

## 1. 목적

예약 메시지 생성 기능을 새로 만든 것이 아니라, 기존 **템플릿+LLM fallback** 메시지 생성기를
**예약 후보 추천 결과**와 연결합니다. 사용자가 후보를 선택하면 그 candidate 정보로 예약 문의
메시지 카드를 만들어 Flutter에서 복사/전송 UI로 쓸 수 있게 합니다.

```
예약 후보 추천 → 후보 선택 → message/from-candidate → message_card 표시(복사/전송)
```

MVP: 실제 문자/카카오/네이버 전송 X, 실제 예약 확정 X. `delivery.status="draft_only"`.

## 2. 기존 template + LLM fallback 구조

`POST /api/v1/messages/reservation`(`message_generator.generate_message`)는 그대로 유지됩니다.
category(hospital/beauty/restaurant/meeting/etc)별 템플릿을 우선 사용하고, OpenAI 키가 있으면
LLM 초안을 시도한 뒤 실패 시 템플릿으로 폴백합니다. beauty는 항상 "커트 또는 시술" 기본 문구를
사용합니다. 이 엔진과 계약은 변경하지 않았습니다.

## 3. 예약 후보 추천과 연결

`POST /api/v1/reservations/business-candidates` 응답 `data`에 optional `next_actions`를
추가했습니다(기존 candidate/필드는 그대로):

```json
"next_actions": [
  { "type": "generate_message", "label": "예약 문의 메시지 만들기",
    "endpoint": "POST /api/v1/reservations/message/from-candidate" }
]
```

## 4. candidate → message request 변환 규칙

`reservation_candidate_to_message_request(candidate, service_name=...)`:

- `business_name` → 카드 업체명
- `category` → reservation_type(라벨) → 엔진 category
- `date` → target_date, `start_time` → preferred_time, `end_time`/`duration_minutes` → 참고
- `service_name` → purpose (beauty는 엔진 기본 "커트 또는 시술" 유지)
- `party_size` → 식당일 때 메시지에 "{N}명" 반영
- `request_note` → 카드의 요청사항 필드

## 5. category → reservation_type 매핑

hair/beauty/nail→beauty, health/hospital/dental→hospital, meal/restaurant→restaurant,
study/meeting→meeting, pt/fitness→fitness, 그 외→general. 메시지 생성 엔진은
beauty/hospital/restaurant/meeting만 지원하므로 fitness/general은 엔진상 `etc`(일반 문구)로
처리하고, 카드의 `reservation_type` 라벨에는 매핑값을 그대로 노출합니다.

## 6. message_card 응답 구조

```json
"data": {
  "message_card": {
    "title": "챔니 헤어살롱 예약 문의",
    "message_text": "안녕하세요. 7월 3일 오후 6시쯤 커트 또는 시술 예약 가능한 시간이 있을까요?",
    "copy_text": "…같은 문장…",
    "action_type": "inquiry",
    "reservation_type": "beauty",
    "business_name": "챔니 헤어살롱",
    "date": "2026-07-03", "time": "18:00",
    "service_name": "커트 또는 시술", "request_note": "예약 가능한지 확인 부탁드립니다.",
    "alternatives": ["…", "…"],
    "generation_source": "template",
    "delivery": { "external_send_enabled": false, "status": "draft_only",
                  "note": "MVP에서는 실제 메시지 전송 없이 문구만 생성합니다." }
  },
  "source_candidate": { "business_id": "hair_001", "business_name": "챔니 헤어살롱",
                        "date": "2026-07-03", "start_time": "18:00", "end_time": "19:00" }
}
```

- `message_text`(표시용)와 `copy_text`(복사용) 항상 포함, 비어 있지 않음.
- `action_type` ∈ inquiry/confirm/change/cancel/check. inquiry는 기존 엔진(템플릿+LLM),
  나머지는 간단 템플릿으로 생성. `generation_source`는 template | llm_fallback.
- 필수 필드(business_name, date, start_time, category) 부족 시 500이 아니라 422 +
  `data.missing_fields`.

## 7. draft_only 의미 / 실제 예약 확정과의 차이

메시지 생성 ≠ 예약 확정. 이 API는 "문구만" 만들며 어떤 외부 전송/예약도 하지 않습니다
(`external_send_enabled=false`, `status="draft_only"`). 사용자가 문구를 복사/전송해 실제 예약이
성사되면, 별도로 `POST /api/v1/reservations/book` 또는 일정 저장 흐름을 호출합니다.

## 8. Flutter에서 사용할 필드

`message_card.message_text`(표시), `message_card.copy_text`(복사 버튼),
`message_card.delivery.status`(draft_only → "복사하기/직접 전송하기"로 표현, 전송 완료로 표시 금지),
`source_candidate`(어떤 후보로 만든 메시지인지). 후보 목록의 `next_actions`로 "메시지 만들기"
버튼을 노출.

## 9. 현재 MVP 한계

실제 전송/예약 API 없음, inquiry는 기존 엔진 형식(예: "오후 6시쯤")·비-inquiry는 별도 템플릿
형식("18:00")이라 표기가 일부 다름, beauty는 service_name과 무관하게 기본 "커트 또는 시술"
문구 유지, reservation_type fitness/general은 일반 문구로 생성, user_id는 참고용(local-user).

## 10. 추후 실제 전송/예약 API 연동 방향

`delivery`를 실제 채널(SMS/카카오/네이버 예약)로 확장하고 status를 sent/failed로 관리, 전송 후
예약 확정 시 `reservations/book`·캘린더 등록과 연계, 메시지 히스토리 저장, LLM 초안 품질 개선
(비진단·정중체 가드 유지).
