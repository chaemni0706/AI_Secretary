"""기상청(공공데이터포털) 단기예보 서비스.

- 위경도 → 기상청 격자(nx, ny) 변환(LCC DFS 공식, 기상청 제공 상수)
- 초단기예보(getUltraSrtFcst): 현재에 가까운 기온/하늘/강수
- 단기예보(getVilageFcst): 오늘 시간별 예보 + 최저/최고
- 키(KMA_SERVICE_KEY) 없거나 네트워크/파싱 실패 시 Mock 반환(앱은 항상 동작)

안전 원칙: 어떤 실패든 예외를 밖으로 던지지 않고 Mock 으로 degrade 한다.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from backend.core.config import settings
from backend.database.schema.weather_schema import (
    WeatherData,
    WeatherDay,
    WeatherHour,
    WeatherNow,
)

logger = logging.getLogger("weather_service")

_DOW = ["월", "화", "수", "목", "금", "토", "일"]


def _dow_label(d: datetime) -> str:
    return _DOW[d.weekday()]


_SKY = {"1": "맑음", "3": "구름많음", "4": "흐림"}
_PTY = {
    "0": "없음", "1": "비", "2": "비/눈", "3": "눈",
    "4": "소나기", "5": "빗방울", "6": "빗방울눈날림", "7": "눈날림",
}

# 서울 기본 격자(위치 조회 실패 시 fallback).
_SEOUL_NX, _SEOUL_NY = 60, 127


# --------------------------------------------------------------------------- #
# 위경도 → 기상청 격자 (LCC DFS)
# --------------------------------------------------------------------------- #
def latlon_to_grid(lat: float, lon: float) -> Tuple[int, int]:
    RE, GRID = 6371.00877, 5.0
    SLAT1, SLAT2, OLON, OLAT = 30.0, 60.0, 126.0, 38.0
    XO, YO = 43, 136
    DEGRAD = math.pi / 180.0
    re = RE / GRID
    slat1, slat2 = SLAT1 * DEGRAD, SLAT2 * DEGRAD
    olon, olat = OLON * DEGRAD, OLAT * DEGRAD
    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = (sf ** sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / (ro ** sn)
    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / (ra ** sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn
    nx = int(ra * math.sin(theta) + XO + 0.5)
    ny = int(ro - ra * math.cos(theta) + YO + 0.5)
    return nx, ny


# --------------------------------------------------------------------------- #
# 발표(base) 시각 계산
# --------------------------------------------------------------------------- #
def _ultra_base(now: datetime) -> Tuple[str, str]:
    """초단기예보: 매시 30분 발표, 45분 이후 제공."""
    t = now if now.minute >= 45 else now - timedelta(hours=1)
    return t.strftime("%Y%m%d"), t.strftime("%H30")


def _vilage_base(now: datetime) -> Tuple[str, str]:
    """단기예보: 02,05,08,11,14,17,20,23시 발표(각 +10분 이후 제공)."""
    slots = [2, 5, 8, 11, 14, 17, 20, 23]
    avail = now - timedelta(minutes=10)
    chosen = None
    for h in slots:
        if avail.hour >= h:
            chosen = h
    if chosen is None:  # 02:10 이전 → 전일 2300
        d = now - timedelta(days=1)
        return d.strftime("%Y%m%d"), "2300"
    return now.strftime("%Y%m%d"), f"{chosen:02d}00"


# --------------------------------------------------------------------------- #
# HTTP 호출
# --------------------------------------------------------------------------- #
def _fetch(url: str, nx: int, ny: int, base_date: str, base_time: str) -> List[dict]:
    """기상청 API 호출 → item 리스트. 실패 시 예외(호출부에서 처리)."""
    import httpx  # lazy import

    params = {
        "serviceKey": settings.KMA_SERVICE_KEY,
        "dataType": "JSON",
        "numOfRows": 1000,
        "pageNo": 1,
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    }
    r = httpx.get(url, params=params, timeout=settings.KMA_TIMEOUT_SECONDS)
    r.raise_for_status()
    body = r.json()["response"]["body"]
    return body["items"]["item"]


# --------------------------------------------------------------------------- #
# 파싱
# --------------------------------------------------------------------------- #
def _parse_now(items: List[dict]) -> WeatherNow:
    """초단기예보 items → 가장 이른 예보시각의 현재값."""
    if not items:
        return WeatherNow()
    first_time = min(i["fcstTime"] for i in items)
    cur = {i["category"]: i["fcstValue"] for i in items if i["fcstTime"] == first_time}
    temp = _to_float(cur.get("T1H"))
    sky = _SKY.get(cur.get("SKY"))
    pty = _PTY.get(cur.get("PTY"))
    reh = _to_int(cur.get("REH"))
    parts = [p for p in (sky, f"{temp:.0f}℃" if temp is not None else None) if p]
    return WeatherNow(
        temp_c=temp, sky=sky, precipitation=pty, humidity=reh,
        summary=", ".join(parts) if parts else None,
    )


def _parse_today(items: List[dict], today: str) -> Tuple[List[WeatherHour], Optional[float], Optional[float]]:
    """단기예보 items → 오늘 시간별 + 최저/최고."""
    by_time: Dict[str, Dict[str, str]] = {}
    tmn = tmx = None
    for i in items:
        if i["fcstDate"] != today:
            continue
        cat, val = i["category"], i["fcstValue"]
        if cat == "TMN":
            tmn = _to_float(val)
        elif cat == "TMX":
            tmx = _to_float(val)
        by_time.setdefault(i["fcstTime"], {})[cat] = val
    hours: List[WeatherHour] = []
    for t in sorted(by_time):
        c = by_time[t]
        if "TMP" not in c:  # 시간별 기온이 있는 예보 시각만(TMN/TMX 단독 행 제외)
            continue
        hours.append(WeatherHour(
            time=f"{t[:2]}:{t[2:]}",
            temp_c=_to_float(c.get("TMP")),
            sky=_SKY.get(c.get("SKY")),
            precipitation=_PTY.get(c.get("PTY")),
            pop=_to_int(c.get("POP")),
        ))
    return hours, tmn, tmx


def _parse_daily(items: List[dict]) -> List[WeatherDay]:
    """단기예보 items → 일자별 예보(최저/최고 + 대표 하늘/강수).

    기상청 getVilageFcst 는 통상 오늘 포함 ~3일치를 제공한다. 대표 하늘/강수는
    정오(1200) 값을 우선 사용하고 없으면 15시/임의 값으로 대체한다.
    """
    by_date: Dict[str, Dict[str, object]] = {}
    for i in items:
        d, cat, val, t = i["fcstDate"], i["category"], i["fcstValue"], i["fcstTime"]
        e = by_date.setdefault(d, {"tmn": None, "tmx": None, "sky": {}, "pty": {}})
        if cat == "TMN":
            e["tmn"] = _to_float(val)
        elif cat == "TMX":
            e["tmx"] = _to_float(val)
        elif cat == "SKY":
            e["sky"][t] = val  # type: ignore[index]
        elif cat == "PTY":
            e["pty"][t] = val  # type: ignore[index]
    out: List[WeatherDay] = []
    for d in sorted(by_date):
        e = by_date[d]
        sky_map, pty_map = e["sky"], e["pty"]  # type: ignore[assignment]
        sky_code = (sky_map.get("1200") or sky_map.get("1500")
                    or next(iter(sky_map.values()), None))
        pty_code = (pty_map.get("1200") or pty_map.get("1500")
                    or next(iter(pty_map.values()), None))
        dt = datetime.strptime(d, "%Y%m%d")
        out.append(WeatherDay(
            date=dt.strftime("%Y-%m-%d"), dow=_dow_label(dt),
            temp_min=e["tmn"], temp_max=e["tmx"],  # type: ignore[arg-type]
            sky=_SKY.get(sky_code), precipitation=_PTY.get(pty_code),
        ))
    return out


def _synth_day(d: datetime) -> WeatherDay:
    """KMA 단기예보 범위(~3일)를 넘는 날짜의 근사 예보(결정론적, 요일 기반)."""
    wd = d.weekday()
    skies = ["맑음", "구름많음", "흐림"]
    return WeatherDay(
        date=d.strftime("%Y-%m-%d"), dow=_dow_label(d),
        temp_min=float(16 + (wd % 3)), temp_max=float(23 + (wd % 4)),
        sky=skies[wd % 3], precipitation="없음",
    )


def _ensure_week(days: List[WeatherDay], now: datetime, count: int = 7) -> List[WeatherDay]:
    """일자별 예보를 count 일까지 채운다(실측 이후는 결정론적 근사로 보완)."""
    result = list(days[:count])
    if result:
        cursor = datetime.strptime(result[-1].date, "%Y-%m-%d")
    else:
        cursor = datetime(now.year, now.month, now.day) - timedelta(days=1)
    while len(result) < count:
        cursor = cursor + timedelta(days=1)
        result.append(_synth_day(cursor))
    return result


def _to_float(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v) -> Optional[int]:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# 오프라인 좌표→지역명 (외부 API 불필요, 전 플랫폼 동작)
# 전국 주요 도시 대표 좌표에 최근접(nearest) 매칭 → 도시 단위 지역명.
# --------------------------------------------------------------------------- #
_CITIES = [
    (37.5665, 126.9780, "서울특별시"),
    (37.4563, 126.7052, "인천광역시"),
    (37.2636, 127.0286, "경기도 수원시"),
    (37.4200, 127.1300, "경기도 성남시"),
    (37.6600, 126.8300, "경기도 고양시"),
    (37.2400, 127.1800, "경기도 용인시"),
    (37.5000, 126.7900, "경기도 부천시"),
    (37.8800, 127.7300, "강원특별자치도 춘천시"),
    (37.7500, 128.9000, "강원특별자치도 강릉시"),
    (37.3400, 127.9200, "강원특별자치도 원주시"),
    (36.3500, 127.3800, "대전광역시"),
    (36.4800, 127.2900, "세종특별자치시"),
    (36.6400, 127.4900, "충청북도 청주시"),
    (36.9900, 127.9300, "충청북도 충주시"),
    (36.8200, 127.1100, "충청남도 천안시"),
    (36.7900, 127.0000, "충청남도 아산시"),
    (35.8200, 127.1500, "전북특별자치도 전주시"),
    (35.9700, 126.7400, "전북특별자치도 군산시"),
    (35.9500, 126.9600, "전북특별자치도 익산시"),
    (35.1600, 126.8500, "광주광역시"),
    (34.8100, 126.3900, "전라남도 목포시"),
    (34.9500, 127.4900, "전라남도 순천시"),
    (34.7600, 127.6600, "전라남도 여수시"),
    (35.8700, 128.6000, "대구광역시"),
    (36.0190, 129.3435, "경상북도 포항시"),
    (35.8600, 129.2200, "경상북도 경주시"),
    (36.1200, 128.3400, "경상북도 구미시"),
    (36.5700, 128.7300, "경상북도 안동시"),
    (35.1800, 129.0750, "부산광역시"),
    (35.5400, 129.3100, "울산광역시"),
    (35.2300, 128.6800, "경상남도 창원시"),
    (35.2300, 128.8900, "경상남도 김해시"),
    (35.1800, 128.1100, "경상남도 진주시"),
    (33.5000, 126.5300, "제주특별자치도 제주시"),
    (33.2500, 126.5600, "제주특별자치도 서귀포시"),
]


def region_label(lat: Optional[float], lon: Optional[float]) -> Optional[str]:
    """좌표 → 지역명. 네이버 역지오코딩(정밀) 우선, 실패 시 오프라인 최근접 도시.
    날씨·업체추천 등 위치 기반 기능이 공통으로 쓴다."""
    return _region_name(lat, lon) or _region_from_latlon(lat, lon)


def _region_from_latlon(lat: Optional[float], lon: Optional[float]) -> Optional[str]:
    """좌표에 가장 가까운 주요 도시 이름(오프라인, 항상 동작)."""
    if lat is None or lon is None:
        return None
    best, best_d = None, None
    for clat, clon, name in _CITIES:
        d = (clat - lat) ** 2 + (clon - lon) ** 2
        if best_d is None or d < best_d:
            best, best_d = name, d
    return best


# --------------------------------------------------------------------------- #
# 지역명(역지오코딩) — GPS 좌표 → "시/도 시/군/구"
# --------------------------------------------------------------------------- #
def _region_name(lat: Optional[float], lon: Optional[float]) -> Optional[str]:
    """네이버 지도 역지오코딩으로 좌표→지역명. 키 없거나 실패 시 None."""
    if lat is None or lon is None or not settings.naver_maps_configured:
        return None
    try:
        from backend.services import naver_maps_client
        res = naver_maps_client.reverse_geocode(lat, lon)
        addr = (res or {}).get("address")
        if addr:
            # "서울특별시 강남구 역삼동 …" → 앞 2토큰(시/도 + 시·군·구)만.
            return " ".join(addr.split()[:2]) or None
    except Exception as exc:
        logger.debug("역지오코딩 실패: %s", exc)
    return None


# --------------------------------------------------------------------------- #
# 공개 진입점
# --------------------------------------------------------------------------- #
def get_weather(lat: Optional[float] = None, lon: Optional[float] = None) -> WeatherData:
    """현재+오늘 날씨. 키 없거나 실패 시 Mock. 위치 없으면 서울 격자."""
    if lat is not None and lon is not None:
        try:
            nx, ny = latlon_to_grid(lat, lon)
        except Exception:
            nx, ny = _SEOUL_NX, _SEOUL_NY
    else:
        nx, ny = _SEOUL_NX, _SEOUL_NY

    # GPS 기반 지역명: 네이버 역지오코딩(정밀) 우선, 실패 시 오프라인 최근접 도시.
    region = _region_name(lat, lon) or _region_from_latlon(lat, lon)

    if not settings.kma_configured:
        return _mock(nx, ny, region)

    try:
        now = datetime.now()
        ub_date, ub_time = _ultra_base(now)
        vb_date, vb_time = _vilage_base(now)
        now_items = _fetch(settings.KMA_ULTRA_NCST_URL, nx, ny, ub_date, ub_time)
        day_items = _fetch(settings.KMA_VILAGE_FCST_URL, nx, ny, vb_date, vb_time)
        today = now.strftime("%Y%m%d")
        hours, tmn, tmx = _parse_today(day_items, today)
        daily = _ensure_week(_parse_daily(day_items), now)
        return WeatherData(
            location=region or "현재 위치", nx=nx, ny=ny,
            now=_parse_now(now_items), today=hours, daily=daily,
            temp_min=tmn, temp_max=tmx, source="kma",
            observed_at=f"{ub_date} {ub_time}",
        )
    except Exception as exc:
        logger.warning("KMA 호출 실패 → Mock: %s", exc)
        return _mock(nx, ny, region)


def _mock(nx: int, ny: int, region: Optional[str] = None) -> WeatherData:
    hours = [
        WeatherHour(time=f"{h:02d}:00", temp_c=20.0 + (h % 6), sky="맑음",
                    precipitation="없음", pop=10)
        for h in range(9, 22, 3)
    ]
    return WeatherData(
        location=region or "서울(예시)", nx=nx, ny=ny,
        now=WeatherNow(temp_c=23.0, sky="맑음", precipitation="없음",
                       humidity=45, summary="맑음, 23℃"),
        today=hours, daily=_ensure_week([], datetime.now()),
        temp_min=18.0, temp_max=27.0, source="mock",
        observed_at=None,
    )
