"""회귀 테스트: 업체 추천 검색어의 '위치 우선' 규칙.

문제: GPS 위치가 있어도 발화의 자유 지역토큰(STT 오인식 "포항"→"포비야",
잔여 어미 "싶은데")이 있으면 GPS 지역이 검색어에서 빠져 0건→mock 이 됐다.
수정: location_address(GPS/구조화 위치)가 있으면 그걸 지역으로 신뢰하고
발화 지역토큰은 사용하지 않는다. 위치가 없을 때만 발화 지역토큰으로 폴백.
"""

from backend.services import place_query_parser as q


def setup_function(_):
    # 규칙 파일 캐시 초기화(테스트 격리).
    q.load_place_rules.cache_clear()


def test_gps_location_wins_over_garbled_stt():
    query, cat = q.build_search_query("포비야 싶은데 치과", {}, {"address": "포항시"})
    assert cat == "hospital"
    assert query == "포항시 치과", query  # STT 쓰레기 제거 + GPS 지역 사용


def test_gps_location_with_normal_utterance():
    query, cat = q.build_search_query(
        "치과 예약하고 싶은데 추천해 줘", {}, {"address": "포항시"}
    )
    assert cat == "hospital"
    assert query == "포항시 치과", query


def test_cafe_with_gps():
    query, cat = q.build_search_query("카페 추천해줘", {}, {"address": "포항시"})
    assert cat == "cafe"
    assert "포항시" in query and "카페" in query, query


def test_no_location_falls_back_to_utterance_region():
    query, cat = q.build_search_query("강남 카페 추천해줘", {}, {})
    assert cat == "cafe"
    assert "강남" in query and "카페" in query, query


def test_no_location_no_region_uses_category_only():
    query, cat = q.build_search_query("카페 추천해줘", {}, {})
    assert cat == "cafe"
    assert query == "카페", query


def test_stopword_expansion_strips_filler():
    # '먹을만한'류/'싶은데' 등이 지역토큰으로 새지 않는다(위치 없을 때).
    query, _ = q.build_search_query("맛집 가고싶은데 추천해줘", {}, {})
    assert "가고싶은데" not in query and "추천" not in query, query
