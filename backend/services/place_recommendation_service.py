"""Place recommendation service.

Orchestrates the place-recommend pipeline and scores candidates, mirroring the
rule-based scoring style used elsewhere in the project
(reservation_recommender: BASE_SCORE + bonuses/penalties, clamped to a range).

    recommend_places(request_dict) -> PlaceRecommendData

Pipeline:
    parse query/category  ->  Naver local search  ->  rule-based scoring
    -> travel time (on by default, needs location coords) + travel-aware scoring
    -> [if schedule window + duration given] schedule-feasibility scoring
    ->  reason + tags  ->  sort (score desc, then original order)  ->  data

Weights & aliases come from rules/place_recommendation_rules.json (not
hard-coded). Naver-search/config failures surface as typed exceptions
(NaverConfigError / NaverApiError) for the router. Maps failures NEVER fail the
recommendation: the place's `travel` field is simply left null.
"""

from __future__ import annotations

import logging
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

_logger = logging.getLogger(__name__)

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
    elif not category:
        score += sc["unknown_penalty"]

    if _keyword_matched(place, keywords):
        score += sc["keyword_match_bonus"]
        tags.append("키워드 일치")

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


def _parse_hhmm(value: Optional[str]) -> Optional[int]:
    """'HH:mm' -> minutes since midnight. None on anything unparseable."""
    if not value:
        return None
    try:
        h, m = str(value).split(":")
        h, m = int(h), int(m)
    except (ValueError, AttributeError):
        return None
    if not (0 <= h < 24 and 0 <= m < 60):
        return None
    return h * 60 + m


def _available_window_minutes(schedule_context: dict) -> Optional[int]:
    """Length of the user's available window in minutes, or None if the window
    isn't a usable same-day start<end pair."""
    start = _parse_hhmm(schedule_context.get("available_start_time"))
    end = _parse_hhmm(schedule_context.get("available_end_time"))
    if start is None or end is None or end <= start:
        return None
    return end - start


def _schedule_usable(schedule_context: dict) -> bool:
    """Schedule scoring needs both a window and how long the visit takes."""
    return (
        _available_window_minutes(schedule_context) is not None
        and bool(schedule_context.get("duration_minutes"))
    )


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


def _geocode_place(place_addr: Optional[str]) -> Optional[dict]:
    """Geocode a place address to coords. Never raises (returns None).

    Failures are logged (not swallowed silently) so a missing travel line can be
    diagnosed: config error vs. no geocode match.
    """
    if not place_addr:
        _logger.info("[PLACE TRAVEL] 주소 없음 → 이동시간 건너뜀")
        return None
    try:
        geo = maps.geocode(place_addr)
    except Exception as exc:
        _logger.warning("[PLACE TRAVEL] geocode 실패 addr=%r: %s", place_addr, exc)
        return None
    if not geo:
        _logger.info("[PLACE TRAVEL] geocode 결과 없음 addr=%r", place_addr)
        return None
    return geo


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


def _apply_schedule_score(
    rec: RecommendedPlace, travel: dict, schedule_context: dict, rules: dict
) -> None:
    """Fold schedule feasibility into score/reason/tags.

    needed = one-way travel time + on-site stay (duration_minutes).
    Compared against the user's available window (end - start).
    """
    ss = rules.get("schedule_scoring", {})
    minutes = travel.get("duration_minutes")
    if minutes is None:
        return
    duration = schedule_context.get("duration_minutes") or 0
    window = _available_window_minutes(schedule_context)
    needed = minutes + duration

    if window is None:
        # No usable window: can't judge fit, just surface the total time needed.
        if duration:
            rec.recommendation_tags.append(f"소요 약 {needed}분")
        return

    sc = rules["scoring"]
    comfortable = window * ss.get("comfortable_ratio", 0.8)
    if needed <= comfortable:
        rec.score += ss.get("fits_bonus", 10)
        rec.recommendation_tags.append("일정 여유")
        tail = (
            f" 이동 {minutes}분 + 체류 {duration}분(총 {needed}분)으로 "
            f"가능 시간 {window}분 안에 여유있게 소화할 수 있습니다."
        )
    elif needed <= window:
        rec.score += ss.get("tight_bonus", 0)
        rec.recommendation_tags.append("일정 빠듯")
        tail = (
            f" 이동·체류 포함 총 {needed}분으로 가능 시간 {window}분에 "
            f"빠듯하게 맞습니다."
        )
    else:
        rec.score += ss.get("overflow_penalty", -15)
        rec.recommendation_tags.append("일정 초과 우려")
        tail = (
            f" 이동·체류 포함 총 {needed}분으로 가능 시간 {window}분을 "
            f"초과할 수 있습니다."
        )

    rec.score = _clamp(rec.score, sc["min_score"], sc["max_score"])
    rec.reason = (rec.reason.rstrip() + tail).strip()


def _enrich_with_travel(
    recs: List[RecommendedPlace],
    origin: dict,
    mode: str,
    rules: dict,
    schedule_context: Optional[dict] = None,
) -> None:
    """Compute travel and fold it into score/reason/tags. When the schedule is
    usable, also score schedule feasibility and widen the enrichment scope so
    ranking reflects which places actually fit the user's available time."""
    o_lat, o_lng = origin.get("latitude"), origin.get("longitude")
    if o_lat is None or o_lng is None:
        return  # no origin coords -> cannot compute; leave travel null

    schedule_context = schedule_context or {}
    if _schedule_usable(schedule_context):
        limit = rules.get("schedule_scoring", {}).get("top_n_with_schedule", 5)
    else:
        limit = rules.get("travel_scoring", {}).get("top_n_with_travel", 3)

    walk_max = rules.get("travel_scoring", {}).get("walk_show_max_minutes", 15)

    for rec in recs[:limit]:
        addr = rec.road_address or rec.address
        geo = _geocode_place(addr)
        if not geo:
            continue  # Maps failure -> travel stays null, recommendation continues
        g_lat, g_lng = geo["latitude"], geo["longitude"]

        # Primary travel = requested mode (car by default). Drives scoring.
        primary = travel_svc.safe_compute_travel(o_lat, o_lng, g_lat, g_lng, mode)
        if primary:
            rec.travel = _travel_info_from_dict(primary)
            _apply_travel_score(rec, primary, rules)
            if _schedule_usable(schedule_context):
                _apply_schedule_score(rec, primary, schedule_context, rules)
            _logger.info(
                "[PLACE TRAVEL] ok(%s) addr=%r → %s분", mode, addr,
                primary.get("duration_minutes"),
            )
        else:
            _logger.warning(
                "[PLACE TRAVEL] %s 경로 실패(키/경로 확인) addr=%r origin=(%s,%s)",
                mode, addr, o_lat, o_lng,
            )

        # Extra: walking, shown only when it's short enough to be worth walking.
        if mode != "walking":
            walk = travel_svc.safe_compute_travel(o_lat, o_lng, g_lat, g_lng, "walking")
            w_min = walk.get("duration_minutes") if walk else None
            if w_min is not None and w_min <= walk_max:
                rec.travel_walk = _travel_info_from_dict(walk)
                _logger.info("[PLACE TRAVEL] 도보 %s분 (≤%s) → 표시", w_min, walk_max)


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

    # Travel + schedule enrichment. On by default (options.include_travel_time
    # defaults True); needs user-location coords. Never fails the recommendation.
    if options.get("include_travel_time", True) and (location.get("latitude") is not None):
        _enrich_with_travel(
            recommended,
            location,
            options.get("transport_mode", "car"),
            rules,
            schedule_context=schedule_context,
        )
        # travel / schedule bonuses may have changed scores -> stable re-sort
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
