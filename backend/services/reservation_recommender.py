"""Rule-based reservation candidate recommender.

Given a preferred time window on a target date and the device's existing
schedules, find free slots that fit the requested duration and score them.

Never raises: malformed times or an invalid window simply yield an empty
result (success with no candidates), so the API stays 200.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from backend.database.schema.reservation_schema import (
    ExistingSchedule,
    RecommendedCandidate,
    RejectedSlot,
    ReservationCandidateData,
    ReservationCandidateRequest,
)

STEP_MINUTES = 30           # candidate start granularity
TOO_LATE_MINUTES = 21 * 60  # starts at/after 21:00 are considered "too late"

BASE_SCORE = 80
SANDWICH_BONUS = 10         # fits exactly between two existing schedules
PROXIMITY_BONUS = 5         # closeness to preferred_start_time (graded 0..5)
LATE_PENALTY = 5            # starts at/after 21:00

# A free slot inside the preferred window, carrying the *merged* busy boundaries
# that bound it: (free_start, free_end, left_busy_end, right_busy_start).
# left_busy_end / right_busy_start are None when the slot touches the window edge
# with no adjacent busy interval.
FreeSlot = Tuple[int, int, Optional[int], Optional[int]]


def _wa_gwa(word: str) -> str:
    """Pick the Korean particle 와/과 based on the final consonant (받침)."""
    if not word:
        return "와"
    last = word[-1]
    if "가" <= last <= "힣":
        has_batchim = (ord(last) - 0xAC00) % 28 != 0
        return "과" if has_batchim else "와"
    return "와"


def _to_min(hhmm: str) -> Optional[int]:
    """Parse 'HH:mm' to minutes-since-midnight, or None if malformed."""
    try:
        h_s, m_s = hhmm.split(":")
        h, m = int(h_s), int(m_s)
    except (ValueError, AttributeError):
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h * 60 + m


def _to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _merge_busy(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged = [intervals[0]]
    for s, e in intervals[1:]:
        ls, le = merged[-1]
        if s <= le:
            merged[-1] = (ls, max(le, e))
        else:
            merged.append((s, e))
    return merged


def _free_slots(win_start: int, win_end: int, busy: List[Tuple[int, int]]) -> List[FreeSlot]:
    """Complement of (already merged) busy within [win_start, win_end].

    Each free slot also reports the merged busy boundaries that bound it so the
    caller can decide sandwich bonuses from merged edges, not raw schedule edges.
    """
    slots: List[FreeSlot] = []
    cursor = win_start
    left_be: Optional[int] = None  # merged busy end defining the current cursor
    for bs, be in busy:
        if be <= win_start or bs >= win_end:
            continue
        bs_c, be_c = max(bs, win_start), min(be, win_end)
        if bs_c > cursor:
            # free slot bounded on the right by this busy's (clipped) start.
            slots.append((cursor, bs_c, left_be, bs_c))
        cursor = max(cursor, be_c)
        left_be = be_c  # this busy's end bounds the next free slot on the left
    if cursor < win_end:
        slots.append((cursor, win_end, left_be, None))
    return slots


def _empty(target_date: str) -> ReservationCandidateData:
    return ReservationCandidateData(
        target_date=target_date,
        recommended_candidates=[],
        rejected_slots=[],
    )


def _score_candidate(
    start: int, end: int,
    left_busy_end: Optional[int], right_busy_start: Optional[int],
    win_end: int, span: int,
) -> Tuple[int, bool]:
    """Score a candidate slot. Returns (score 0..100, sandwiched).

    BASE_SCORE
      + SANDWICH_BONUS  if it fills a gap bounded by busy on BOTH merged edges
      + PROXIMITY_BONUS scaled by closeness to preferred_start (win_start)
      - LATE_PENALTY    if it starts at/after 21:00
    """
    sandwiched = (
        left_busy_end is not None and right_busy_start is not None
        and start == left_busy_end and end == right_busy_start
    )
    score = BASE_SCORE
    if sandwiched:
        score += SANDWICH_BONUS
    score += round(PROXIMITY_BONUS * (win_end - start) / span)
    if start >= TOO_LATE_MINUTES:
        score -= LATE_PENALTY
    return max(0, min(100, score)), sandwiched


def recommend_candidates(req: ReservationCandidateRequest) -> ReservationCandidateData:
    c = req.constraints
    win_start, win_end = _to_min(c.preferred_start_time), _to_min(c.preferred_end_time)
    duration = c.duration_minutes

    # --- input guard: malformed/invalid window or duration -> empty result ---
    if win_start is None or win_end is None or win_start >= win_end or duration <= 0:
        return _empty(c.target_date)

    span = win_end - win_start  # > 0, used for the proximity bonus

    # Only same-date schedules count as busy; skip malformed entries.
    same_day: List[ExistingSchedule] = [
        s for s in req.existing_schedules if s.date == c.target_date
    ]
    parsed: List[Tuple[int, int, ExistingSchedule]] = []
    for s in same_day:
        bs, be = _to_min(s.start_time), _to_min(s.end_time)
        if bs is None or be is None or bs >= be:
            continue
        parsed.append((bs, be, s))

    busy = _merge_busy([(bs, be) for bs, be, _ in parsed])

    # Rejected slots: existing schedules overlapping the preferred window.
    rejected: List[RejectedSlot] = []
    for bs, be, s in parsed:
        if bs < win_end and win_start < be:
            title = s.title or "기존 일정"
            rejected.append(RejectedSlot(
                start_time=s.start_time,
                end_time=s.end_time,
                reason=f"{title}{_wa_gwa(title)} 시간이 겹칩니다.",
            ))
    rejected.sort(key=lambda r: (_to_min(r.start_time) or 0))

    # Recommended candidates: windows fully inside a free slot (no overlap).
    candidates: List[RecommendedCandidate] = []
    for fs, fe, left_be, right_bs in _free_slots(win_start, win_end, busy):
        if fe - fs < duration:
            continue
        start = fs
        while start + duration <= fe:
            end = start + duration

            score, sandwiched = _score_candidate(
                start, end, left_be, right_bs, win_end, span
            )

            if sandwiched:
                reason = f"기존 일정 사이에 딱 맞는 빈 시간으로 예약 소요 시간 {duration}분을 만족합니다."
            else:
                reason = f"선호 시간대 내 빈 시간으로 예약 소요 시간 {duration}분을 만족합니다."

            candidates.append(RecommendedCandidate(
                candidate_id="",
                start_time=_to_hhmm(start),
                end_time=_to_hhmm(end),
                score=score,
                reason=reason,
                conflict=False,  # only non-overlapping slots reach this list
            ))
            start += STEP_MINUTES

    # Highest score first; ties broken by earlier start time.
    candidates.sort(key=lambda x: (-x.score, _to_min(x.start_time) or 0, _to_min(x.end_time) or 0))
    for i, cand in enumerate(candidates, 1):
        cand.candidate_id = f"cand_{i:03d}"

    return ReservationCandidateData(
        target_date=c.target_date,
        recommended_candidates=candidates,
        rejected_slots=rejected,
    )
