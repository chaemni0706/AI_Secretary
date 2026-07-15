"""중기예보(D+3~) 파싱/병합 회귀 테스트.

라이브 KMA 호출 없이 픽스처로 순수 로직만 검증한다:
- _parse_wf_text: 육상예보 하늘텍스트 → (sky, precip)
- _parse_mid_land / _parse_mid_ta: 단일 item → {N: ...}
- _build_week: 단기(D0~2) + 중기(D3~6) 실측 병합, 중기 없으면 근사 폴백
- _mid_reg_ids / _mid_base: 좌표→regId, 발표시각(tmFc)
"""

from datetime import datetime, timedelta

from backend.database.schema.weather_schema import WeatherDay
from backend.services import weather_service as w


# --- _parse_wf_text ---------------------------------------------------------
def test_parse_wf_text_variants():
    assert w._parse_wf_text("맑음") == ("맑음", "없음")
    assert w._parse_wf_text("구름많음") == ("구름많음", "없음")
    assert w._parse_wf_text("흐림") == ("흐림", "없음")
    assert w._parse_wf_text("구름많고 비") == ("구름많음", "비")
    assert w._parse_wf_text("흐리고 눈") == ("흐림", "눈")
    assert w._parse_wf_text("흐리고 비/눈") == ("흐림", "비/눈")
    assert w._parse_wf_text("소나기") == (None, "소나기")
    assert w._parse_wf_text(None) == (None, "없음")


# --- _parse_mid_land / _parse_mid_ta ----------------------------------------
def _land_item():
    it = {}
    for n in range(3, 8):
        it[f"wf{n}Am"] = "맑음"
        it[f"wf{n}Pm"] = "구름많고 비"
        it[f"rnSt{n}Am"] = 20
        it[f"rnSt{n}Pm"] = 60
    return [it]


def _ta_item():
    it = {}
    for n in range(3, 8):
        it[f"taMin{n}"] = 10 + n
        it[f"taMax{n}"] = 20 + n
    return [it]


def test_parse_mid_land_uses_pm_representative():
    out = w._parse_mid_land(_land_item())
    assert set(out.keys()) == {3, 4, 5, 6, 7}
    assert out[3]["sky"] == "구름많음"       # Pm 대표
    assert out[3]["precip"] == "비"
    assert out[3]["pop"] == 60               # rnSt Pm


def test_parse_mid_ta():
    out = w._parse_mid_ta(_ta_item())
    assert out[3] == (13.0, 23.0)
    assert out[7] == (17.0, 27.0)


def test_parse_mid_empty():
    assert w._parse_mid_land([]) == {}
    assert w._parse_mid_ta([]) == {}


# --- _build_week ------------------------------------------------------------
def _short_days(now):
    """오늘/내일/모레(D0~2) 단기 예보 3일."""
    base = datetime(now.year, now.month, now.day)
    out = []
    for i in range(3):
        d = base + timedelta(days=i)
        out.append(WeatherDay(
            date=d.strftime("%Y-%m-%d"), dow=w._dow_label(d),
            temp_min=15.0, temp_max=25.0, sky="맑음", precipitation="없음",
        ))
    return out


def test_build_week_merges_midterm_for_days_3_to_6():
    now = datetime(2026, 7, 10, 9, 0)
    land = w._parse_mid_land(_land_item())
    ta = w._parse_mid_ta(_ta_item())
    week = w._build_week(_short_days(now), now, land, ta, count=7)

    assert len(week) == 7
    # D0~2 단기 유지
    assert week[0].sky == "맑음" and week[0].temp_max == 25.0
    # D+3~D+6 은 중기 실측(구름많음/비, 기온 taMin/Max N)
    for i in (3, 4, 5, 6):
        assert week[i].sky == "구름많음", week[i]
        assert week[i].precipitation == "비"
        assert week[i].temp_min == 10 + i
        assert week[i].temp_max == 20 + i


def test_build_week_falls_back_to_synth_without_midterm():
    now = datetime(2026, 7, 10, 9, 0)
    week = w._build_week(_short_days(now), now, None, None, count=7)
    assert len(week) == 7
    # 중기 없음 → D+3~ 는 근사(_synth_day: precipitation '없음').
    assert all(d.precipitation is not None for d in week)
    # 날짜가 연속인지(오늘부터 7일).
    dates = [d.date for d in week]
    assert dates == sorted(dates)
    assert len(set(dates)) == 7


# --- _mid_reg_ids / _mid_base ----------------------------------------------
def test_mid_reg_ids_seoul_and_busan():
    assert w._mid_reg_ids(37.5665, 126.9780) == ("11B00000", "11B10101")
    assert w._mid_reg_ids(35.1800, 129.0750) == ("11H20000", "11H20201")


def test_mid_reg_ids_default_when_unknown():
    # 좌표 없음 → 서울 기본.
    assert w._mid_reg_ids(None, None) == ("11B00000", "11B10101")


def test_mid_base_slot_selection():
    assert w._mid_base(datetime(2026, 7, 10, 3, 0)).endswith("1800")   # 06시 이전 → 전일 1800
    assert w._mid_base(datetime(2026, 7, 10, 3, 0)).startswith("20260709")
    assert w._mid_base(datetime(2026, 7, 10, 9, 0)) == "202607100600"  # 06~18시
    assert w._mid_base(datetime(2026, 7, 10, 20, 0)) == "202607101800" # 18시 이후
