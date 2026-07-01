"""LLM-based schedule parser (JSON-first, few-shot).

Builds a strict JSON-only prompt with a small set of Korean few-shot examples,
requests OpenAI JSON mode when available, and delegates the actual model call to
the shared ``llm_service.generate`` (which returns None with no API key / on any
error). Whatever comes back is robustly reduced to a JSON object — tolerating
markdown code fences, surrounding prose, and trailing commas.

Contract: ``parse()`` returns the raw parsed dict, or None when the LLM is
unavailable / the reply can't be turned into a JSON object. It NEVER raises and
performs NO domain validation — that lives in ``schedule_parse_service``.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from backend.services import llm_service

_SYSTEM = "You are a schedule parsing engine for a Korean AI secretary app."

# Few-shot examples are written for a FIXED illustrative base date so the model
# learns the relative-date mapping without us hardcoding today's date. The real
# request's Base date is supplied separately and always governs actual parsing.
_FEWSHOT_BASE = "2026-07-01"
_FEWSHOT = """\
The following examples assume Base date = 2026-07-01 (Wednesday):

입력: 내일 오후 3시에 병원 예약 있어
출력: {"title":"병원 예약","date":"2026-07-02","start_time":"15:00","end_time":null,"category":"health","location":null,"memo":null,"is_all_day":false,"confidence":0.86}

입력: 이번 주 금요일 저녁 7시에 강남역에서 친구랑 밥
출력: {"title":"친구와 식사","date":"2026-07-03","start_time":"19:00","end_time":null,"category":"meal","location":"강남역","memo":null,"is_all_day":false,"confidence":0.82}

입력: 다음 주 월요일 오전 10시 팀 회의
출력: {"title":"팀 회의","date":"2026-07-06","start_time":"10:00","end_time":null,"category":"work","location":null,"memo":null,"is_all_day":false,"confidence":0.88}

입력: 모레 3시 반 네일 예약
출력: {"title":"네일 예약","date":"2026-07-03","start_time":"15:30","end_time":null,"category":"beauty","location":null,"memo":null,"is_all_day":false,"confidence":0.84}

입력: 7월 5일 하루 종일 워크숍
출력: {"title":"워크숍","date":"2026-07-05","start_time":null,"end_time":null,"category":"work","location":null,"memo":null,"is_all_day":true,"confidence":0.8}

입력: 미용실 예약해야 돼
출력: {"title":"미용실 예약","date":null,"start_time":null,"end_time":null,"category":"beauty","location":null,"memo":null,"is_all_day":false,"confidence":0.4}
"""

_PROMPT_TEMPLATE = """\
Extract schedule information from the user's Korean natural language input.
Return ONLY a valid JSON object. Do not include markdown, comments, or explanation.

Base date: {today}
Timezone: {timezone}

Allowed categories:
- health
- beauty
- study
- work
- meal
- personal
- other

Rules:
1. Convert Korean relative dates such as 오늘, 내일, 모레, 이번 주 금요일, 다음 주 월요일 into YYYY-MM-DD based on Base date.
2. Convert Korean time expressions such as 오후 3시, 저녁 7시, 3시 반 into HH:MM (24-hour).
3. If a field is unknown, use null. Do not guess.
4. Do not invent a location; only include a location that literally appears in the input.
5. Return confidence between 0 and 1.
6. Return a single JSON object only.

Output schema:
{{
  "title": string | null,
  "date": "YYYY-MM-DD" | null,
  "start_time": "HH:MM" | null,
  "end_time": "HH:MM" | null,
  "category": "health" | "beauty" | "study" | "work" | "meal" | "personal" | "other",
  "location": string | null,
  "memo": string | null,
  "is_all_day": boolean,
  "confidence": number
}}

{fewshot}
Now parse this input. Remember: the Base date is {today}, NOT the example date.

User input:
{text}
"""


def build_prompt(text: str, today: str, timezone: str = "Asia/Seoul") -> str:
    return _PROMPT_TEMPLATE.format(
        today=today, timezone=timezone, text=text, fewshot=_FEWSHOT
    )


def _extract_json(raw: Optional[str]) -> Optional[dict]:
    """Pull a JSON object out of a raw LLM reply. Tolerant of code fences,
    leading/trailing prose and trailing commas. Returns None on failure."""
    if not raw or not raw.strip():
        return None
    s = raw.strip()

    # strip ```json ... ``` / ``` ... ``` fences if present
    s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s).strip()

    # isolate the outermost {...}
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    fragment = s[start:end + 1]

    # remove trailing commas before } or ]
    fragment = re.sub(r",(\s*[}\]])", r"\1", fragment)

    try:
        obj = json.loads(fragment)
    except (ValueError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None


def parse(text: str, today: str, timezone: str = "Asia/Seoul") -> Optional[dict]:
    """Return the raw parsed dict from the LLM, or None if unavailable/unparseable.

    Requests OpenAI JSON mode; if the underlying client/model doesn't support it,
    ``llm_service.generate`` swallows the error and returns None -> rule fallback.
    """
    prompt = build_prompt(text, today=today, timezone=timezone)
    try:
        raw = llm_service.generate(
            prompt,
            system=_SYSTEM,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
    except TypeError:
        # a caller monkeypatched generate() without the response_format kwarg
        raw = llm_service.generate(prompt, system=_SYSTEM, temperature=0.0)
    except Exception:
        return None
    return _extract_json(raw)
