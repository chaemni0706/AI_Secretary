"""업체 추천 Mock 데이터.

네이버 장소 API 키가 없거나 호출이 실패했을 때, 카테고리별 예시 업체 목록을
돌려주기 위한 Mock 이다. 실제 API 응답(RecommendedPlace)과 동일한 형태를 만들어
호출부(_handle_reservation_recommendation)에서 그대로 쓸 수 있게 한다.

주의: 이 파일은 순수 Mock 이며 실제 위치/영업정보와 무관하다. source="mock".
"""

from __future__ import annotations

from typing import List

from backend.database.schema.place_schema import (
    PlaceRecommendData,
    PlaceRecommendFilters,
    RecommendedPlace,
)

# 카테고리별 예시 업체(이름, 이유, 태그). 필요 시 여기만 늘리면 됨.
_MOCK: dict[str, List[dict]] = {
    "beauty": [
        {"name": "제이헤어 살롱", "reason": "리뷰 평점이 높고 예약이 수월해요.",
         "tags": ["헤어", "가까움", "리뷰많음"]},
        {"name": "라라네일", "reason": "네일·왁싱 전문, 도보 5분 거리예요.",
         "tags": ["네일", "도보5분"]},
        {"name": "뷰티풀 미용실", "reason": "합리적인 가격대의 동네 미용실이에요.",
         "tags": ["가성비", "동네"]},
    ],
    "hospital": [
        {"name": "미소가득 치과", "reason": "야간 진료가 가능하고 예약이 빨라요.",
         "tags": ["치과", "야간진료"]},
        {"name": "튼튼 정형외과", "reason": "물리치료실을 갖춘 가까운 병원이에요.",
         "tags": ["정형외과", "물리치료"]},
        {"name": "맑은 피부과", "reason": "피부 진료 리뷰가 좋은 곳이에요.",
         "tags": ["피부과", "리뷰좋음"]},
    ],
    "restaurant": [
        {"name": "행복한 밥상", "reason": "가까운 한식당, 점심 예약 추천.",
         "tags": ["한식", "가까움"]},
        {"name": "파스타공방", "reason": "분위기 좋은 양식당이에요.",
         "tags": ["양식", "분위기"]},
    ],
    "cafe": [
        {"name": "한적한 커피", "reason": "조용해서 작업하기 좋아요.", "tags": ["조용함"]},
        {"name": "디저트타임", "reason": "디저트가 맛있는 카페예요.", "tags": ["디저트"]},
    ],
}

# 카테고리 미상일 때 기본 목록.
_DEFAULT = [
    {"name": "추천 업체 A", "reason": "가까운 인기 업체예요.", "tags": ["가까움"]},
    {"name": "추천 업체 B", "reason": "예약이 수월한 업체예요.", "tags": ["예약수월"]},
]


def mock_places(category: str | None, query: str) -> PlaceRecommendData:
    """카테고리에 맞는 Mock 업체 목록을 RecommendedPlace 로 반환."""
    items = _MOCK.get(category or "", _DEFAULT)
    places: List[RecommendedPlace] = []
    for i, it in enumerate(items):
        places.append(
            RecommendedPlace(
                place_id=f"mock_{(category or 'etc')}_{i + 1:02d}",
                name=it["name"],
                category=category,
                address="예시 주소 (Mock)",
                road_address=None,
                phone="02-000-0000",
                map_url=None,
                score=90 - i * 5,
                reason=it["reason"],
                recommendation_tags=list(it.get("tags", [])),
                source="mock",
            )
        )
    return PlaceRecommendData(
        query=query or (category or "추천"),
        recommended_places=places,
        filters=PlaceRecommendFilters(category=category),
    )
