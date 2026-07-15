# 이동 시간 · 출발 알림 확장 (Naver Cloud Maps 연동)

네이버 클라우드 Maps API(Geocoding / Reverse Geocoding / Directions 5)를 추가로
연결해 추천 장소까지의 거리·예상 이동 시간을 계산하고, 기존 장소 추천 API와
출발 알림 API에 **추가(additive)** 방식으로 연결합니다. 기존 API는 대체하지
않으며, 옵션이 없으면 기존 동작/응답 그대로입니다.

Maps API는 **백엔드에서만** 호출합니다(프론트 직접 호출 금지).

## 환경 변수 (`backend/.env`) — 인증 정보 분리

```env
# 지역 검색용
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...

# 지도/거리/경로 계산용 (Naver Cloud Maps; 인증 정보 분리)
NAVER_MAPS_CLIENT_ID=...
NAVER_MAPS_CLIENT_SECRET=...
```

키가 없어도 서버는 부팅합니다. Maps 기반 기능만 명확한 에러(`503`)를 반환하거나,
장소 추천의 경우 이동 시간 필드를 `null`로 두고 추천은 계속 반환합니다.

---

## 1) 이동 시간 계산 API (신규)

```
POST /api/v1/travel/estimate
```

Request:

```json
{
  "user_id": "user-1",
  "current_datetime": "2026-07-03T17:30:00+09:00",
  "timezone": "Asia/Seoul",
  "origin": {"latitude": 37.5572, "longitude": 126.9245, "address": "홍대입구역"},
  "destination": {
    "name": "홍대 한식당 예시",
    "address": "서울 마포구 양화로 ...",
    "road_address": "서울 마포구 양화로 ...",
    "latitude": null,
    "longitude": null
  },
  "transport_mode": "car"
}
```

동작: 목적지 좌표가 없으면 `road_address`/`address`를 Geocoding으로 좌표 변환한 뒤
출발지→목적지 Directions 5(자동차)로 거리·시간을 계산합니다.

에러: 키 누락 `503`, Maps 호출 실패 `502`, 입력 부족(좌표·주소 모두 없음) `422`.

---

## 2) 이동 시간 포함 장소 추천 (기존 API 확장)

```
POST /api/v1/places/recommend
```

`options.include_travel_time=true`이고 `location`에 좌표가 있으면, **상위 3개**
장소에 대해서만 Geocoding→Directions로 이동 시간을 계산해 `travel` 필드로 포함하고
추천 점수/이유/태그에 반영합니다.

```json
{
  "input": "홍대 근처에서 저녁 먹을 만한 식당 추천해줘",
  "location": {"latitude": 37.5572, "longitude": 126.9245, "address": "홍대입구역"},
  "preferences": {"category": "restaurant", "keywords": ["저녁", "한식", "가성비"], "mood": "casual"},
  "options": {"include_travel_time": true}
}
```

이동 시간 점수 반영(0~100 clamp): 15분 이하 +10, 30분 이하 +5, 45분 초과 -10.
`travel` 정보가 없으면 이동 시간 항목은 건너뜁니다. Maps 실패가 추천 전체를
실패시키지 않습니다(해당 장소 `travel=null`).

---

## 3) 출발 알림 확장 (기존 API 확장)

```
POST /api/v1/alerts/departure-plan
```

`options.include_travel_time`이 있으면 이동 시간을 반영한 `alert_plan` 형태로
응답합니다. 옵션이 없으면 **기존 leave_time/checklist/notifications 그대로**입니다.

```json
{
  "user_id": "user-1",
  "current_datetime": "2026-07-03T17:30:00+09:00",
  "timezone": "Asia/Seoul",
  "schedule": {
    "id": "sch_001", "title": "홍대 한식당 방문", "category": "restaurant",
    "date": "2026-07-03", "start_time": "19:00", "end_time": "20:30",
    "location": "서울 마포구 ...", "latitude": 37.5541, "longitude": 126.9223,
    "priority": "medium", "is_fixed": true
  },
  "user_profile": {
    "default_alert_minutes_before": 30, "departure_buffer_minutes": 10,
    "transport_mode": "car", "late_prone": true,
    "current_location": {"latitude": 37.5572, "longitude": 126.9245, "address": "홍대입구역"}
  },
  "options": {
    "include_checklist": true, "include_departure_alert": true,
    "include_mock_call_alert": true, "include_travel_time": true, "voice_enabled": true
  }
}
```

출발 시간 계산:

```
departure_time = start_time - travel_duration_minutes - departure_buffer_minutes
trigger_datetime = departure_time - 10분
# 예) 19:00 - 18 - 10 = 18:32,  trigger 18:22
```

`travel` 정보를 못 얻으면 `start_time - default_alert_minutes_before`로 폴백합니다.
실제 로컬 알림 예약은 프론트(Flutter)가 수행하며, 백엔드는 계획(trigger_datetime /
departure_time / message / voice_alert_text)만 반환합니다.

---

## transport_mode 처리 (MVP)

- `car` / `unknown`: Directions 5(자동차) 사용.
- `public_transit`: 자동차 결과를 참고값으로 반환하되 "대중교통 기준 실제 시간은
  별도 연동 필요" note 추가.
- `walking`: 직선거리 기반 추정 + note(실제 도보 경로 미연동).

## 미구현 / 주의

- 대중교통·도보 실제 경로 API는 미연동(참고값/추정치 + note).
- 실제 예약 가능 시간 확인은 MVP 범위 밖.
- Reverse Geocoding은 선택 구현(클라이언트에 함수만 제공, 파이프라인 필수 아님).
