"""Rule-based intent router for the unified voice entry point.

Classifies a raw STT utterance into ONE of 7 voice-flow intents:

    reservation_recommendation | emotion_schedule_coaching | daily_briefing |
    schedule_query | reminder_setting | schedule_create | fallback_chat

This is intentionally a SEPARATE taxonomy from ``intent_classifier.py`` (used
only by ``/chat/respond``): that classifier's ``reservation_recommend`` means
"when should I book this appointment", while this router's
``reservation_recommendation`` means "find me a place/store" (place
discovery). Reusing one name for both would blur two different features, so
this module owns its own rule file (``rules/voice_intent_rules.json``) and
never touches ``chat_intent_rules.json``.

Priority is a CASCADE (first matching intent wins), not a max-score
comparison — this mirrors the spec's explicit ordering requirement:
"가게 추천해줘" contains a recommendation keyword so it must never fall
through to schedule_create; "오늘 진짜 피곤하다 오늘 일정 뭐야" contains a
schedule_query phrase but the emotion word upgrades it to
emotion_schedule_coaching.

Never raises: unexpected errors degrade to fallback_chat.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from backend.core.config import settings
from backend.services import llm_service

_RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "voice_intent_rules.json"

_logger = logging.getLogger("voice_intent_router")

INTENTS = (
    "reservation_recommendation",
    "emotion_schedule_coaching",
    "daily_briefing",
    "schedule_query",
    "reminder_setting",
    "schedule_create",
    "fallback_chat",
)

_HOURS_RE = re.compile(r"(\d+)\s*시간\s*전")
_MINUTES_RE = re.compile(r"(\d+)\s*분\s*전")


@lru_cache(maxsize=1)
def _rules() -> dict:
    with open(_RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _matched(text: str, keywords: Optional[List[str]]) -> List[str]:
    return [kw for kw in (keywords or []) if kw in text]


@lru_cache(maxsize=1)
def _place_category_aliases() -> Dict[str, List[str]]:
    """장소 카테고리 별칭(미용실→beauty, 치과/병원→hospital 등). 예약 추천 업종 감지용.
    place_recommendation_rules.json 을 재사용해 규칙 중복을 피한다."""
    path = Path(__file__).resolve().parents[1] / "rules" / "place_recommendation_rules.json"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("category_aliases", {}) or {}
    except Exception:
        return {}


def detect_place_category(text: str) -> Optional[str]:
    """발화에서 장소 업종(category)을 감지. 없으면 None."""
    text = text or ""
    for category, words in _place_category_aliases().items():
        if any(w in text for w in (words or [])):
            return category
    return None


def parse_reminder_minutes(text: str) -> Optional[int]:
    """Extract a spoken '1시간 전' / '30분 전' offset as minutes. None if absent."""
    text = text or ""
    m = _HOURS_RE.search(text)
    if m:
        return int(m.group(1)) * 60
    m = _MINUTES_RE.search(text)
    if m:
        return int(m.group(1))
    return None


def _is_reminder_decline(text: str, rules: dict) -> bool:
    return any(kw in text for kw in rules.get("reminder_setting", {}).get("decline", []))


def _schedule_create_signal(text: str) -> bool:
    """A concrete date/time in the utterance is a strong schedule_create signal
    even without an explicit '추가해줘' verb. Reuses the existing, tested
    schedule_parser instead of duplicating its date/time regexes."""
    try:
        from backend.database.schema.schedule_schema import ScheduleParseRequest
        from backend.services.schedule_parser import parse_schedule

        data = parse_schedule(ScheduleParseRequest(input=text))
        return bool(data.slots.date or data.slots.start_time)
    except Exception:
        return False


def _result(intent: str, matched_keywords: Dict[str, List[str]], **extra) -> dict:
    out = {"intent": intent, "matched_keywords": matched_keywords}
    out.update(extra)
    _logger.info(
        "[VOICE INTENT] intent=%s matched_keywords=%s extra=%s",
        intent, matched_keywords, {k: v for k, v in extra.items()},
    )
    return out


# --------------------------------------------------------------------------- #
# LLM 보조 분류 (규칙이 fallback_chat 으로 떨어질 때만 사용)
# --------------------------------------------------------------------------- #
# LLM 이 승격시킬 수 있는 '실행형' intent 집합. reminder_setting 은 직전 일정
# 컨텍스트가 있어야만 의미가 있어(문맥 게이팅) LLM 승격 대상에서 제외한다.
_LLM_ASSIST_INTENTS = (
    "schedule_create",
    "schedule_query",
    "emotion_schedule_coaching",
    "reservation_recommendation",
    "daily_briefing",
)
_LLM_MIN_CONFIDENCE = 0.6
_LLM_SYSTEM = (
    "너는 한국어 음성 비서의 의도 분류기야. 주어진 발화를 정해진 후보 중 하나로만 "
    "분류하고, 반드시 JSON 하나만 출력해. 설명·문장 금지."
)


def _llm_classify(text: str) -> Optional[dict]:
    """LLM(JSON mode, temperature=0)으로 의도를 분류. 실패/파싱실패/키없음 시 None.
    반환: {"intent": <후보>, "confidence": float} 또는 None."""
    from backend.services import llm_service

    prompt = (
        f'발화: "{text}"\n'
        "이 발화의 의도를 아래 후보 중 하나로 분류해줘.\n"
        "- schedule_create: 일정/약속 등록·추가\n"
        "- schedule_query: 기존 일정 조회·확인\n"
        "- emotion_schedule_coaching: 감정 토로/고민 상담(피곤·스트레스 등)\n"
        "- reservation_recommendation: 장소·가게·맛집 추천 요청\n"
        "- daily_briefing: 오늘 하루 요약/브리핑\n"
        "- fallback_chat: 위 어디에도 해당 안 되는 일반 대화\n"
        '반드시 JSON만 출력: {"intent": "<후보 중 하나>", "confidence": 0.0~1.0}'
    )
    data = llm_service.generate_json(prompt, system=_LLM_SYSTEM, temperature=0.0)
    if not data:
        return None
    intent = str(data.get("intent", "")).strip()
    try:
        conf = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    if intent not in _LLM_ASSIST_INTENTS and intent != "fallback_chat":
        return None  # 알 수 없는 라벨 → 규칙 유지
    return {"intent": intent, "confidence": conf}


def select_voice_intent_hybrid(text: str, context: Optional[dict] = None) -> dict:
    """규칙 우선 + (규칙이 애매할 때만) LLM 보조 분류.

    - 규칙이 fallback_chat 이 아닌 명확한 intent 를 주면 그대로 반환(LLM 미호출).
    - fallback_chat 이고 `ENABLE_LLM_INTENT` + API 키가 있을 때만 LLM 호출.
    - LLM 이 실행형 intent 를 confidence>=임계치로 주면 승격, 아니면 규칙 유지.
    - 어떤 실패든 규칙 결과로 fallback.
    """
    rule_res = select_voice_intent(text, context)
    if rule_res.get("intent") != "fallback_chat":
        return rule_res  # 명확 → LLM 호출 안 함(비용 절감)

    try:
        if not (settings.ENABLE_LLM_INTENT and llm_service.is_enabled()):
            return rule_res
        llm = _llm_classify(text)
    except Exception:
        _logger.exception("LLM intent assist failed for text=%r", text)
        return rule_res

    if llm and llm["intent"] in _LLM_ASSIST_INTENTS and llm["confidence"] >= _LLM_MIN_CONFIDENCE:
        return _result(
            llm["intent"], {},
            intent_source="llm", intent_confidence=round(llm["confidence"], 2),
        )
    return rule_res


def select_voice_intent(text: str, context: Optional[dict] = None) -> dict:
    """Classify one utterance. `context` is the client-echoed
    `last_action_context` from the previous turn (or None/{})."""
    text = text or ""
    context = context or {}
    matched_keywords: Dict[str, List[str]] = {}

    try:
        rules = _rules()

        # 1. reservation_recommendation — place/store discovery, checked FIRST.
        cfg = rules["reservation_recommendation"]
        hits = _matched(text, cfg["strong"]) + _matched(text, cfg["weak"])
        # 업종만 말하고 예약을 원하는 경우도 추천으로: 예약 동사 + 장소 카테고리.
        # (예: "미용실 예약해줘", "치과 가야 하는데 잡아줘") — 특정 업체명 없이.
        verb_hits = _matched(text, cfg.get("reservation_verbs", []))
        place_category = detect_place_category(text)
        if hits or (verb_hits and place_category):
            matched_keywords["reservation_recommendation"] = hits + verb_hits
            return _result(
                "reservation_recommendation", matched_keywords,
                category=place_category, location_required=True,
            )

        # 2. emotion_schedule_coaching — requires BOTH groups.
        cfg = rules["emotion_schedule_coaching"]
        emo_hits = _matched(text, cfg["emotion_keywords"])
        sched_hits = _matched(text, cfg["schedule_ref_keywords"])
        if emo_hits and sched_hits:
            matched_keywords["emotion_schedule_coaching"] = emo_hits + sched_hits
            return _result("emotion_schedule_coaching", matched_keywords)

        # 3. daily_briefing
        cfg = rules["daily_briefing"]
        hits = _matched(text, cfg["strong"])
        if hits:
            matched_keywords["daily_briefing"] = hits
            return _result("daily_briefing", matched_keywords)

        # 4. schedule_query (strong-only; see rules file comment)
        cfg = rules["schedule_query"]
        hits = _matched(text, cfg["strong"])
        if hits:
            matched_keywords["schedule_query"] = hits
            return _result("schedule_query", matched_keywords)

        # 5. reminder_setting — context-gated.
        cfg = rules["reminder_setting"]
        if context.get("type") == cfg.get("requires_context_type"):
            hits = _matched(text, cfg["strong"]) + _matched(text, cfg["weak"])
            decline = _is_reminder_decline(text, rules)
            minutes = parse_reminder_minutes(text)
            if hits or decline or minutes is not None:
                matched_keywords["reminder_setting"] = hits
                return _result(
                    "reminder_setting", matched_keywords,
                    reminder_minutes=minutes, reminder_decline=decline,
                )

        # 6. schedule_create — explicit verb OR a concrete date/time signal.
        cfg = rules["schedule_create"]
        hits = _matched(text, cfg["strong"]) + _matched(text, cfg["weak"])
        # 감정 표현만 있고 명시적 일정 키워드가 없으면, 날짜 신호(예: "오늘")만으로는
        # 일정 생성으로 보지 않는다("오늘 너무 힘들어" → 상담/일반대화로).
        emo = _matched(text, rules["emotion_schedule_coaching"]["emotion_keywords"])
        if hits or (_schedule_create_signal(text) and not emo):
            matched_keywords["schedule_create"] = hits
            return _result("schedule_create", matched_keywords)

        # 7. fallback_chat
        return _result("fallback_chat", matched_keywords)
    except Exception:
        _logger.exception("voice intent classification failed for text=%r", text)
        return _result("fallback_chat", {})
