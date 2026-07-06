"""Place recommendation service.

Orchestrates the place-recommend pipeline and scores candidates, mirroring the
rule-based scoring style used elsewhere in the project
(reservation_recommender: BASE_SCORE + bonuses/penalties, clamped to a range).

    recommend_places(request_dict) -> PlaceRecommendData

Pipeline:
    parse query/category  ->  Naver local search  ->  rule-based scoring
    -> [optional] travel time for top-N + travel-aware scoring
    ->  reason + tags  ->  sort (score desc, then original order)  ->  data

Weights & aliases come from rules/place_recommendation_rules.json (not
hard-coded). Naver-search/config failures surface as typed exceptions
(NaverConfigError / NaverApiError) for the router. Maps failures NEVER fail the
recommendation: the place's `travel` field is simply left null.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from backend.database.schema.place_schema import (
    PlaceRecommendData,
    PlaceRecommendFilters,
    RecommendedPlace,
)
from backend.database.schema.travel_schema import TravelInfo
from backend.services import naver_maps_client as maps
from backend.services import naver_place_client as naver
from backend.services import travel_time_service as travel_svc
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
    """Return (score 0..100, reason, tags) for one candidate (no travel yet)."""
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


# --------------------------------------------------------------------------- #
# Travel-time enrichment (optional, additive)
# --------------------------------------------------------------------------- #
def _travel_info_from_dict(d: dict) -> TravelInfo:
    return TravelInfo(
        distance_meters=d.get("distance_meters"),
        duration_minutes=d.get("duration_minutes"),
        transport_mode=d.get("transport_mode", "car"),
        route_summary=d.get("route_summary"),
        source=d.get("source", "naver_maps"),
        note=d.get("note"),
    )


def _travel_for_place(
    place_addr: Optional[str],
    origin_lat: float,
    origin_lng: float,
    mode: str,
) -> Optional[dict]:
    """Geocode the place then compute travel. Never raises (returns None)."""
    if not place_addr:
        return None
    try:
        geo = maps.geocode(place_addr)
    except Exception:
        return None
    if not geo:
        return None
    return travel_svc.safe_compute_travel(
        origin_lat, origin_lng, geo["latitude"], geo["longitude"], mode
    )


def _apply_travel_score(rec: RecommendedPlace, travel: dict, rules: dict) -> None:
    ts = rules.get("travel_scoring", {})
    minutes = travel.get("duration_minutes")
    if minutes is None:
        return
    if minutes <= ts.get("short_max_minutes", 15):
        rec.score += ts.get("short_bonus", 10)
        tail = f" 현재 위치에서 약 {minutes}분 거리라 이동 부담이 적습니다."
    elif minutes <= ts.get("medium_max_minutes", 30):
        rec.score += ts.get("medium_bonus", 5)
        tail = f" 현재 위치에서 약 {minutes}분 거리입니다."
    elif minutes > ts.get("long_min_minutes", 45):
        rec.score += ts.get("long_penalty", -10)
        tail = f" 현재 위치에서 약 {minutes}분 거리로 이동 부담이 있습니다."
    else:
        tail = f" 현재 위치에서 약 {minutes}분 거리입니다."

    sc = rules["scoring"]
    rec.score = _clamp(rec.score, sc["min_score"], sc["max_score"])
    rec.recommendation_tags.append(f"이동 {minutes}분")
    rec.reason = (rec.reason.rstrip() + tail).strip()


def _enrich_with_travel(
    recs: List[RecommendedPlace],
    origin: dict,
    mode: str,
    rules: dict,
) -> None:
    """Compute travel for the top-N places and fold it into score/reason/tags."""
    o_lat, o_lng = origin.get("latitude"), origin.get("longitude")
    if o_lat is None or o_lng is None:
        return  # no origin coords -> cannot compute; leave travel null
    top_n = rules.get("travel_scoring", {}).get("top_n_with_travel", 3)
    for rec in recs[:top_n]:
        addr = rec.road_address or rec.address
        travel = _travel_for_place(addr, o_lat, o_lng, mode)
        if not travel:
            continue  # Maps failure -> travel stays null, recommendation continues
        rec.travel = _travel_info_from_dict(travel)
        _apply_travel_score(rec, travel, rules)


def recommend_places(req: dict) -> PlaceRecommendData:
    """Main entry. `req` is a PlaceRecommendRequest.model_dump().

    Raises NaverConfigError / NaverApiError on local-search problems.
    Maps/travel problems never raise here.
    """
    rules = load_place_rules()
    preferences = req.get("preferences") or {}
    location = req.get("location") or {}
    schedule_context = req.get("schedule_context") or {}
    options = req.get("options") or {}

    query, category = build_search_query(req.get("input"), preferences, location)

    display = _clamp(
        rules.get("default_display_count", 5), 1, rules.get("max_display_count", 10)
    )
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

    scored.sort(key=lambda t: (-t[0], t[1]))
    recommended = [rec for _, _, rec in scored]

    # optional travel enrichment (top-N only); never fails the recommendation
    if options.get("include_travel_time") and (location.get("latitude") is not None):
        _enrich_with_travel(
            recommended, location, options.get("transport_mode", "car"), rules
        )
        # travel bonuses may have changed scores -> stable re-sort
        recommended.sort(key=lambda r: -r.score)

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
    if not slug:
        return None
    return _CATEGORY_LABEL.get(slug, slug)
