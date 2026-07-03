"""Place recommendation service.

Orchestrates the place-recommend pipeline and scores candidates, mirroring the
rule-based scoring style used elsewhere in the project
(reservation_recommender: BASE_SCORE + bonuses/penalties, clamped to a range).

    recommend_places(request_dict) -> PlaceRecommendData

Pipeline:
    parse query/category  ->  Naver local search  ->  rule-based scoring
    ->  reason + tags  ->  sort (score desc, then original order)  ->  data

Weights & aliases come from rules/place_recommendation_rules.json (not
hard-coded). Naver/config failures surface as typed exceptions
(NaverConfigError / NaverApiError) for the router to map to the common
error envelope.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from backend.database.schema.place_schema import (
    PlaceRecommendData,
    PlaceRecommendFilters,
    RecommendedPlace,
)
from backend.services import naver_place_client as naver
from backend.services.place_query_parser import build_search_query, load_place_rules

# Display label for our category slugs (response-friendly).
_CATEGORY_LABEL = {
    "restaurant": "식당",
    "cafe": "카페",
    "activity": "놀거리",
    "beauty": "뷰티",
    "hospital": "병원",
}


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _category_matched(place: dict, category: Optional[str], rules: dict) -> bool:
    """True if the Naver category text contains an alias of the target category."""
    if not category:
        return False
    naver_cat = (place.get("category") or "")
    aliases = rules.get("category_aliases", {}).get(category, [])
    return any(a in naver_cat for a in aliases)


def _keyword_matched(place: dict, keywords: List[str]) -> bool:
    if not keywords:
        return False
    haystack = " ".join(
        str(place.get(f) or "") for f in ("name", "category", "address", "road_address")
    )
    return any(kw and kw in haystack for kw in keywords)


def _mood_matched(place: dict, mood: Optional[str], rules: dict) -> bool:
    if not mood:
        return False
    words = rules.get("mood_aliases", {}).get(mood, [])
    if not words:
        return False
    haystack = " ".join(str(place.get(f) or "") for f in ("name", "category"))
    return any(w in haystack for w in words)


def _score_place(
    place: dict,
    category: Optional[str],
    keywords: List[str],
    mood: Optional[str],
    rules: dict,
) -> Tuple[int, str, List[str]]:
    """Return (score 0..100, reason, tags) for one candidate."""
    sc = rules["scoring"]
    score = sc["base_score"]
    tags: List[str] = []
    reason_bits: List[str] = []

    cat_match = _category_matched(place, category, rules)
    if cat_match:
        score += sc["category_match_bonus"]
        tags.append("카테고리 일치")
        reason_bits.append("요청한 카테고리와 잘 맞고")
    elif not category:
        score += sc["unknown_penalty"]

    if _keyword_matched(place, keywords):
        score += sc["keyword_match_bonus"]
        tags.append("키워드 일치")
        reason_bits.append("선호 키워드와 관련이 있으며")

    if place.get("road_address"):
        score += sc["has_road_address_bonus"]
        tags.append("도로명 주소 있음")
    if place.get("phone"):
        score += sc["has_phone_bonus"]
        tags.append("연락처 있음")
    if place.get("map_url"):
        score += sc["has_map_url_bonus"]
        tags.append("지도 연결 가능")

    if _mood_matched(place, mood, rules):
        score += sc["mood_match_bonus"]
        tags.append("분위기 일치")

    score = _clamp(score, sc["min_score"], sc["max_score"])

    # ---- reason assembly ----
    info_bits = []
    if place.get("road_address") or place.get("address"):
        info_bits.append("주소")
    if place.get("phone"):
        info_bits.append("연락처")
    if info_bits:
        reason_bits.append(f"{'와 '.join(info_bits)} 정보가 있어 방문/문의하기 좋습니다")
    if not reason_bits:
        reason_bits.append("현재 조건에 맞는 장소입니다")

    reason = " ".join(reason_bits).strip()
    if not reason.endswith("."):
        reason += "."
    return score, reason, tags


def _available_time(schedule_context: Optional[dict]) -> Optional[str]:
    if not schedule_context:
        return None
    start = schedule_context.get("available_start_time")
    end = schedule_context.get("available_end_time")
    if start and end:
        return f"{start}-{end}"
    return start or end


def recommend_places(req: dict) -> PlaceRecommendData:
    """Main entry. `req` is a PlaceRecommendRequest.model_dump().

    Raises NaverConfigError / NaverApiError on upstream problems.
    """
    rules = load_place_rules()
    preferences = req.get("preferences") or {}
    location = req.get("location") or {}
    schedule_context = req.get("schedule_context") or {}

    query, category = build_search_query(req.get("input"), preferences, location)

    display = _clamp(
        rules.get("default_display_count", 5), 1, rules.get("max_display_count", 10)
    )
    # Naver call may raise NaverConfigError / NaverApiError -> handled by router.
    raw_places = naver.search_places(query, display=display)

    keywords = preferences.get("keywords") or []
    mood = preferences.get("mood")

    scored: List[Tuple[int, int, RecommendedPlace]] = []
    for idx, place in enumerate(raw_places):
        score, reason, tags = _score_place(place, category, keywords, mood, rules)
        out_category = category or place.get("category")
        rec = RecommendedPlace(
            place_id=f"naver_{idx + 1:03d}",
            name=place.get("name") or "이름 미상",
            category=out_category,
            address=place.get("address"),
            road_address=place.get("road_address"),
            phone=place.get("phone"),
            map_url=place.get("map_url"),
            score=score,
            reason=reason,
            recommendation_tags=tags,
            source=place.get("source", "naver"),
        )
        scored.append((score, idx, rec))

    # sort: score desc, then original Naver order (stable tiebreak)
    scored.sort(key=lambda t: (-t[0], t[1]))
    recommended = [rec for _, _, rec in scored]

    filters = PlaceRecommendFilters(
        category=category,
        max_distance_meters=preferences.get("max_distance_meters"),
        available_time=_available_time(schedule_context),
    )
    return PlaceRecommendData(
        query=query,
        recommended_places=recommended,
        filters=filters,
    )


def category_label(slug: Optional[str]) -> Optional[str]:
    """Human-readable label for a category slug (used in messages)."""
    if not slug:
        return None
    return _CATEGORY_LABEL.get(slug, slug)
