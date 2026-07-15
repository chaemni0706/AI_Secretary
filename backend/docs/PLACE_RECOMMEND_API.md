# 장소 추천 API (Naver 지역 검색 기반)

사용자의 자연어 입력·위치·선호 조건을 받아 네이버 지역 검색 API로 장소 후보를
가져오고, 서비스 기준의 rule-based 점수를 계산해 추천 리스트를 반환합니다.
네이버 API는 **백엔드에서만** 호출합니다 (프론트에서 직접 호출 금지).

## Endpoint

```
POST /api/v1/places/recommend
```

## 환경 변수 (`backend/.env`)

```env
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
```

- 키가 없거나 비어 있으면 서버는 정상 부팅하며, 이 엔드포인트만 `503`으로
  명확한 에러 메시지를 반환합니다.
- 네이버 호출 자체가 실패(네트워크/타임아웃/HTTP 오류)하면 `502`로 실패 응답을
  반환하고 서버는 죽지 않습니다.
- 모든 응답은 공통 엔벨로프 `{success, message, data}` 형식을 따릅니다.

## Swagger 테스트 방법

1. 서버 실행: 프로젝트 루트에서 `uvicorn backend.main:app --reload`
2. 브라우저에서 `http://127.0.0.1:8000/docs` 접속
3. `POST /api/v1/places/recommend` → **Try it out**
4. 아래 Request 예시를 붙여넣고 **Execute**

### Request 예시

```json
{
  "user_id": "user-1",
  "input": "홍대 근처에서 저녁 먹을 만한 식당 추천해줘",
  "current_datetime": "2026-07-03T18:00:00+09:00",
  "timezone": "Asia/Seoul",
  "location": {
    "latitude": 37.5572,
    "longitude": 126.9245,
    "address": "홍대입구역"
  },
  "preferences": {
    "category": "restaurant",
    "keywords": ["저녁", "한식", "가성비"],
    "max_distance_meters": 1500,
    "price_level": "medium",
    "mood": "casual"
  },
  "schedule_context": {
    "available_start_time": "18:30",
    "available_end_time": "21:00",
    "duration_minutes": 90
  }
}
```

필드는 대부분 선택입니다. 최소한 `input` 또는 `preferences.category` 중 하나만
있으면 동작하며, `location`이 없어도 검색어 기반 추천이 가능합니다.

### Response 예시

```json
{
  "success": true,
  "message": "추천 장소를 찾았습니다.",
  "data": {
    "query": "홍대 저녁 맛집",
    "recommended_places": [
      {
        "place_id": "naver_001",
        "name": "홍대 한식당 예시",
        "category": "restaurant",
        "address": "서울 마포구 서교동 1-1",
        "road_address": "서울 마포구 양화로 100",
        "phone": "02-000-0000",
        "map_url": "https://map.naver.com/...",
        "score": 95,
        "reason": "요청한 카테고리와 잘 맞고 선호 키워드와 관련이 있으며 주소와 연락처 정보가 있어 방문/문의하기 좋습니다.",
        "recommendation_tags": ["카테고리 일치", "키워드 일치", "도로명 주소 있음", "연락처 있음", "지도 연결 가능"],
        "source": "naver"
      }
    ],
    "filters": {
      "category": "restaurant",
      "max_distance_meters": 1500,
      "available_time": "18:30-21:00"
    }
  }
}
```

## 추천 점수 계산 방식 (0~100)

가중치와 카테고리 alias는 `backend/rules/place_recommendation_rules.json`에서
로딩합니다 (하드코딩 아님). 기존 `reservation_recommender`의
`BASE_SCORE + 보너스/감점 → clamp` 스타일을 따릅니다.

```
score = BASE_SCORE(50)
      + CATEGORY_MATCH_BONUS(20)     # 네이버 카테고리에 요청 카테고리 alias 포함
      + KEYWORD_MATCH_BONUS(10)      # 선호 키워드가 이름/카테고리/주소에 포함
      + HAS_ROAD_ADDRESS_BONUS(5)
      + HAS_PHONE_BONUS(5)
      + HAS_MAP_URL_BONUS(5)
      + MOOD_MATCH_BONUS(5)          # mood alias 매칭
      + UNKNOWN_PENALTY(-5)          # 카테고리 판별 실패 시
score = clamp(score, 0, 100)
```

정렬: score 내림차순 → 동점 시 네이버 원래 순서 유지(안정 정렬).

## 파이프라인

```
자연어 입력
  → place_query_parser: 검색어 생성 + 카테고리 판별 (rule-based, LLM fallback 확장 가능)
  → naver_place_client: 네이버 지역 검색 호출 + HTML 태그 제거 + 내부 포맷 정제
  → place_recommendation_service: 점수 계산 + 추천 이유/태그 + 정렬
  → 공통 엔벨로프로 반환
```
