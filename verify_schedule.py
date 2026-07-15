"""Standalone verification of travel-default + schedule-aware recommendation.

Runs the service directly (no FastAPI app / conftest) so stale bash-mirror
files elsewhere in the repo don't block us. External calls are stubbed.
"""
import sys
sys.path.insert(0, ".")

from backend.services import place_recommendation_service as svc
from backend.services import naver_place_client as naver


def _fake_places():
    return [
        {"name": "홍대 한식당 예시", "category": "한식>백반",
         "address": "서울 마포구 서교동 1-1", "road_address": "서울 마포구 양화로 100",
         "phone": "02-000-0000", "map_url": "https://map.naver.com/x", "source": "naver"},
        {"name": "무관한 옷가게", "category": "생활,편의>의류",
         "address": "서울 마포구 서교동 2-2", "road_address": "", "source": "naver"},
    ]


def _stub(monkey_minutes):
    svc.naver.search_places = lambda q, display=5: _fake_places()
    svc.maps.geocode = lambda a: {"latitude": 37.5541, "longitude": 126.9223,
                                  "road_address": a, "jibun_address": None}
    svc.travel_svc.safe_compute_travel = lambda *a, **k: {
        "distance_meters": 3200, "duration_minutes": monkey_minutes,
        "transport_mode": "car", "route_summary": f"약 {monkey_minutes}분",
        "source": "naver_maps"}


LOC = {"latitude": 37.5572, "longitude": 126.9245, "address": "홍대입구역"}

# 1. Travel ON by default (no options block at all)
_stub(12)
data = svc.recommend_places({
    "input": "홍대 저녁 한식 맛집 추천해줘",
    "location": LOC,
    "preferences": {"category": "restaurant"},
})
top = data.recommended_places[0]
assert top.travel is not None, "travel should be computed by default"
assert top.travel.duration_minutes == 12
print("PASS 1: travel on by default ->", top.travel.duration_minutes, "min")

# 2. Explicit include_travel_time=False disables travel (back-compat)
_stub(12)
svc.maps.geocode = lambda a: (_ for _ in ()).throw(AssertionError("geocode must not run"))
data = svc.recommend_places({
    "input": "홍대 저녁 한식 맛집 추천해줘",
    "location": LOC,
    "preferences": {"category": "restaurant"},
    "options": {"include_travel_time": False},
})
assert all(p.travel is None for p in data.recommended_places)
print("PASS 2: include_travel_time=False keeps travel null")

# 3. Comfortable schedule fit -> '일정 여유' tag + higher score
_stub(12)  # travel 12 + stay 60 = 72; window 180; 72 <= 180*0.8=144 -> comfortable
data = svc.recommend_places({
    "input": "홍대 저녁 한식 맛집 추천해줘",
    "location": LOC,
    "preferences": {"category": "restaurant"},
    "schedule_context": {"available_start_time": "18:00",
                         "available_end_time": "21:00", "duration_minutes": 60},
})
top = data.recommended_places[0]
assert "일정 여유" in top.recommendation_tags, top.recommendation_tags
print("PASS 3: comfortable fit ->", top.recommendation_tags, "score", top.score)

# 4. Overflow -> '일정 초과 우려' + penalty
_stub(40)  # travel 40 + stay 90 = 130; window 60 -> overflow
data = svc.recommend_places({
    "input": "홍대 저녁 한식 맛집 추천해줘",
    "location": LOC,
    "preferences": {"category": "restaurant"},
    "schedule_context": {"available_start_time": "18:00",
                         "available_end_time": "19:00", "duration_minutes": 90},
})
tagged = [p for p in data.recommended_places if p.travel is not None]
assert tagged and "일정 초과 우려" in tagged[0].recommendation_tags, tagged[0].recommendation_tags
print("PASS 4: overflow ->", tagged[0].recommendation_tags, "score", tagged[0].score)

# 5. Comfortable-fit place should outrank an overflow place (schedule affects ranking)
comfortable_score = None
_stub(12)
d_ok = svc.recommend_places({
    "input": "홍대 저녁 한식 맛집 추천해줘", "location": LOC,
    "preferences": {"category": "restaurant"},
    "schedule_context": {"available_start_time": "18:00",
                         "available_end_time": "21:00", "duration_minutes": 60}})
comfortable_score = d_ok.recommended_places[0].score
_stub(40)
d_bad = svc.recommend_places({
    "input": "홍대 저녁 한식 맛집 추천해줘", "location": LOC,
    "preferences": {"category": "restaurant"},
    "schedule_context": {"available_start_time": "18:00",
                         "available_end_time": "19:00", "duration_minutes": 90}})
overflow_score = d_bad.recommended_places[0].score
assert comfortable_score > overflow_score, (comfortable_score, overflow_score)
print(f"PASS 5: comfortable score {comfortable_score} > overflow score {overflow_score}")

# 6. Unit checks on helpers
assert svc._parse_hhmm("18:30") == 18 * 60 + 30
assert svc._parse_hhmm("bad") is None
assert svc._available_window_minutes(
    {"available_start_time": "18:00", "available_end_time": "21:00"}) == 180
assert svc._available_window_minutes(
    {"available_start_time": "21:00", "available_end_time": "18:00"}) is None
assert svc._schedule_usable(
    {"available_start_time": "18:00", "available_end_time": "21:00", "duration_minutes": 60})
assert not svc._schedule_usable(
    {"available_start_time": "18:00", "available_end_time": "21:00"})
print("PASS 6: helper unit checks")

print("\nALL CHECKS PASSED")
