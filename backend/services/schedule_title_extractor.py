"""Schedule title extractor (rule-base driven).

Turns a raw Korean utterance into a concise schedule *title* + category +
participants, using a JSON rule-base loaded via ``schedule_rule_loader``:

  * category keywords / title_rules -> backend/rules/schedule_categories.json
  * command / filler / date-time stopwords -> backend/rules/schedule_stopwords.json
  * sentence patterns (title/participant) -> backend/rules/schedule_patterns.json

Strategy (see ``extract_schedule_title``):
  1. detect category (keyword match, longest keyword wins within a category)
  2. build the keyword title via title_rules
  3. try sentence-pattern extraction for a MORE SPECIFIC title
  4. meal utterances keep the participant ("민수와 카페", "가족들과 저녁 약속")
  5. stopword-cleaning fallback when nothing else matches
  6. confidence + source; caller treats confidence < THRESHOLD as missing title

No hardcoded keyword/title tables remain here — they live in the JSON rules.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from backend.services import schedule_rule_loader as rules

# Titles below this confidence must NOT be committed; caller adds "title" to
# missing_fields and asks the user instead.
TITLE_CONFIDENCE_THRESHOLD = 0.6

_MEAL_SAFE_DAYPARTS = ("아침", "점심", "저녁")

# Categories where a sentence-pattern title may override the plain keyword title
# (it tends to be MORE specific there: "교수님 상담" > "상담"). Place-anchored
# categories (health/beauty/transport/...) keep their fixed title_rule so a
# captured place name goes to `location`, not the title ("병원 방문", not "포항성모병원").
_PATTERN_OVERRIDE_CATEGORIES = {"meeting", "study", "todo"}


# --------------------------------------------------------------------------- #
# text cleaning (stopword-driven)
# --------------------------------------------------------------------------- #
def _normalize_josa(text: str) -> str:
    """'민수랑' -> '민수와', '가족들이랑' -> '가족들과' for natural titles."""
    text = re.sub(r"(\S+?)이랑(?=\s|$)", r"\1과", text)
    text = re.sub(r"(\S+?)랑(?=\s|$)", r"\1와", text)
    return text


def _clean(text: str, *, keep_meal_dayparts: bool = True) -> str:
    """Strip date/time/command/intention/filler noise; keep meal dayparts."""
    sw = rules.load_stopwords()
    cp = rules.compiled_patterns()
    work = f" {text} "

    for _, rx, _ in cp.get("date_patterns", []):
        work = rx.sub(" ", work)
    for _, rx, _ in cp.get("time_patterns", []):
        work = rx.sub(" ", work)

    phrases = sorted(
        sw.get("schedule_command_phrases", [])
        + sw.get("todo_command_phrases", [])
        + sw.get("connective_phrases", [])
        + sw.get("intention_phrases", []),
        key=len,
        reverse=True,
    )
    for phrase in phrases:
        work = work.replace(phrase, " ")

    tokens = (
        list(sw.get("first_person", []))
        + list(sw.get("polite_fillers", []))
        + list(sw.get("date_words", []))
    )
    tokens += [
        t
        for t in sw.get("time_words", [])
        if not (keep_meal_dayparts and t in _MEAL_SAFE_DAYPARTS)
    ]
    tokens += list(sw.get("postpositions", []))
    for tok in tokens:
        work = re.sub(rf"(?:^|\s){re.escape(tok)}(?=\s|$)", " ", work)

    work = re.sub(r"\s+", " ", work).strip()
    return _normalize_josa(work)


# --------------------------------------------------------------------------- #
# pattern / participant extraction
# --------------------------------------------------------------------------- #
def _pattern_title(text: str) -> Optional[str]:
    """Most specific title from create_schedule_patterns, cleaned. None if no hit."""
    for _name, rx, _conf in rules.compiled_patterns().get("create_schedule_patterns", []):
        if "title" not in rx.groupindex:
            continue
        m = rx.search(text)
        if not m:
            continue
        raw = m.group("title")
        if not raw:
            continue
        cleaned = _clean(raw)
        if cleaned and len(cleaned.replace(" ", "")) >= 2:
            return cleaned
    return None


def _joiner(name: str) -> str:
    """Return the natural connective ('와'/'과') for a Korean noun by batchim."""
    if not name:
        return "와"
    last = name[-1]
    if "가" <= last <= "힣":
        return "와" if (ord(last) - 0xAC00) % 28 == 0 else "과"
    return "와"


def _extract_participants(text: str) -> Tuple[List[str], List[str]]:
    """Return (names, normalized_subjects) e.g. (['민수'], ['민수와'])."""
    for _name, rx, _conf in rules.compiled_patterns().get("participant_patterns", []):
        if "person" not in rx.groupindex:
            continue
        m = rx.search(text)
        if not m:
            continue
        person = (m.group("person") or "").strip()
        if person and 2 <= len(person) <= 6:
            return [person], [person + _joiner(person)]
    for noun in rules.load_patterns().get("participant_nouns", []):
        if noun in text:
            return [noun], [noun]
    return [], []


def _more_specific(candidate: Optional[str], baseline: Optional[str]) -> bool:
    if not candidate:
        return False
    if not baseline:
        return True
    return len(candidate.replace(" ", "")) > len(baseline.replace(" ", ""))


def _result(title, category, confidence, source, matched_keyword, participants) -> Dict:
    return {
        "title": title,
        "category": category,
        "confidence": round(confidence, 2),
        "source": source,
        "matched_keyword": matched_keyword,
        "participants": participants,
    }


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #
def extract_schedule_title(request_text: str) -> Dict:
    """Extract a concise schedule title + category + participants.

    Returns::

        {
          "title": str | None,
          "category": "health" | ... | "unknown",
          "confidence": 0.0-0.9,
          "source": "domain_keyword" | "pattern_match" | "cleaned_fallback" | "unclear",
          "matched_keyword": str | None,
          "participants": [str, ...],
        }
    """
    text = (request_text or "").strip()
    if not text:
        return _result(None, "unknown", 0.0, "unclear", None, [])

    category, keyword = rules.detect_category(text)
    keyword_title = rules.title_rule_for(category, keyword) or keyword
    pattern_title = _pattern_title(text)
    names, subjects = _extract_participants(text)

    if category == "meal":
        if _more_specific(pattern_title, keyword_title):
            return _result(pattern_title, category, 0.85, "pattern_match", keyword, names)
        if subjects:
            daypart = next((d for d in _MEAL_SAFE_DAYPARTS if d in text), None)
            core = f"{daypart} 약속" if daypart else "식사 약속"
            return _result(f"{subjects[0]} {core}", category, 0.82, "pattern_match", keyword, names)
        return _result(keyword_title, category, 0.9, "domain_keyword", keyword, names)

    if category != "unknown":
        if category in _PATTERN_OVERRIDE_CATEGORIES and _more_specific(pattern_title, keyword_title):
            return _result(pattern_title, category, 0.85, "pattern_match", keyword, names)
        return _result(keyword_title, category, 0.9, "domain_keyword", keyword, names)

    # unknown category — rely on pattern / cleaned fallback
    if pattern_title:
        return _result(pattern_title, "unknown", 0.7, "pattern_match", None, names)
    cleaned = _clean(text)
    if cleaned and len(cleaned.replace(" ", "")) >= 2:
        return _result(cleaned, "unknown", 0.58, "cleaned_fallback", None, names)
    return _result(None, "unknown", 0.3, "unclear", None, names)
