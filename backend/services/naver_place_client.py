"""Naver Local Search API client.

Single responsibility: call Naver's local search endpoint and return a list of
*internal-format* place dicts. No scoring here.

    search_places(query, display=5) -> list[dict]

Internal format (per item)::

    {
        "name":         "장소명",         # HTML tags stripped
        "category":     "카테고리",       # Naver's raw category string
        "address":      "지번 주소",
        "road_address": "도로명 주소",
        "phone":        "전화번호",
        "map_url":      "네이버 link 또는 지도 검색 URL",
        "source":       "naver",
    }

Errors are raised as typed exceptions so the router/service can map them to the
project's common error envelope instead of a raw 500:

    NaverConfigError  -> credentials missing/empty  (config problem)
    NaverApiError     -> upstream call failed        (network / HTTP / parse)
"""

from __future__ import annotations

import html
import re
from typing import List, Optional
from urllib.parse import quote

import httpx

from backend.core.config import settings

_TAG_RE = re.compile(r"<[^>]+>")


class NaverClientError(Exception):
    """Base class for Naver client errors."""


class NaverConfigError(NaverClientError):
    """Raised when Naver credentials are missing or empty."""


class NaverApiError(NaverClientError):
    """Raised when the Naver API call fails (network/HTTP/parse)."""


def _strip_html(text: Optional[str]) -> str:
    """Remove HTML tags (e.g. <b>...</b>) and unescape entities."""
    if not text:
        return ""
    return html.unescape(_TAG_RE.sub("", text)).strip()


def _map_url(item: dict) -> str:
    """Prefer Naver's own link; else build a map search URL from the name."""
    link = (item.get("link") or "").strip()
    if link:
        return link
    name = _strip_html(item.get("title"))
    if name:
        return f"https://map.naver.com/v5/search/{quote(name)}"
    return ""


def _normalize(item: dict) -> dict:
    """Convert one raw Naver item into our internal format."""
    return {
        "name": _strip_html(item.get("title")),
        "category": (item.get("category") or "").strip() or None,
        "address": (item.get("address") or "").strip() or None,
        "road_address": (item.get("roadAddress") or "").strip() or None,
        "phone": (item.get("telephone") or "").strip() or None,
        "map_url": _map_url(item) or None,
        "source": "naver",
    }


def search_places(query: str, display: int = 5, sort: str = "random") -> List[dict]:
    """Call Naver local search and return normalized place dicts.

    Args:
        query:   search string (already assembled by the query parser).
        display: number of results to request (Naver allows 1..5 for local).
        sort:    "random" (relevance) or "comment".

    Raises:
        NaverConfigError: credentials missing.
        NaverApiError:    upstream failure.
    """
    if not settings.naver_configured:
        raise NaverConfigError(
            "네이버 API 키가 설정되지 않았습니다. "
            "backend/.env에 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET를 설정하세요."
        )

    query = (query or "").strip()
    if not query:
        raise NaverApiError("검색어가 비어 있습니다.")

    # Naver local search caps `display` at 5.
    display = max(1, min(int(display or 5), 5))

    headers = {
        "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": display, "start": 1, "sort": sort}

    try:
        resp = httpx.get(
            settings.NAVER_LOCAL_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=settings.NAVER_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:  # network / DNS / timeout
        raise NaverApiError(f"네이버 API 호출에 실패했습니다: {exc}") from exc

    if resp.status_code == 401:
        raise NaverConfigError("네이버 API 인증에 실패했습니다. 키를 확인하세요.")
    if resp.status_code != 200:
        raise NaverApiError(
            f"네이버 API가 오류를 반환했습니다 (status={resp.status_code})."
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        raise NaverApiError("네이버 API 응답을 해석할 수 없습니다.") from exc

    items = payload.get("items") or []
    return [_normalize(it) for it in items]
