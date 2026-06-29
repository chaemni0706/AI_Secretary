"""Rule-based reservation candidate recommender.

Given a preferred time window on a target date and the device's existing
schedules, find free slots that fit the requested duration and score them.
Never raises: an empty result simply yields no candidates.
"""

from __future__ import annotations

from typing import List, Tuple

from backend.database.schema.reservation_schema import (
    ExistingSchedule,
    RecommendedCandidate,
    RejectedSlot,
    ReservationCandidateData,
    ReservationCandidateRequest,
)

STEP_MINUTES = 30           # candidate start granularity
TOO_LATE_MINUTES = 21 * 60  # starts at/after 21:00 are considered "too late"


def _wa_gwa(word: str) -> str:
    """Pick the Korean particle 와/과 based on the final consonant (받침)."""
    if not word:
        return "와"
    last = word[-1]
    if "가" <= last <= "힣":
        has_batchim = (ord(last) - 0xAC00) % 28 != 0
        return "과" if has_batchim else "와"
    return "와"


def _to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


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


def _free_intervals(win_start: int, win_end: int, busy: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Complement of busy within [win_start, win_end]."""
    free: List[Tuple[int, int]] = []
    cursor = win_start
    for bs, be in busy:
        if be <= win_start or bs >= win_end:
            continue
        bs_c, be_c = max(bs, win_start), min(be, win_end)
        if bs_c > cursor:
            free.append((cursor, bs_c))
        cursor = max(cursor, be_c)
    if cursor < win_end:
        free.append((cursor, win_end))
    return free


def recommend_candidates(req: ReservationCandidateRequest) -> ReservationCandidateData:
    c = req.constraints
    win_start, win_end = _to_min(c.preferred_start_time), _to_min(c.preferred_end_time)
    duration = c.duration_minutes

    same_day: List[ExistingSchedule] = [
        s for s in req.existing_schedules if s.date == c.target_date
    ]

    busy_raw = [(_to_min(s.start_time), _to_min(s.end_time)) for s in same_day]
    busy_starts = {b[0] for b in busy_raw}
    busy_ends = {b[1] for b in busy_raw}
    busy = _merge_busy(busy_raw)

    # Rejected slots: existing schedules overlapping the preferred window.
    rejected: List[RejectedSlot] = []
    for s in same_day:
        bs, be = _to_min(s.start_time), _to_min(s.end_time)
        if bs < win_end and win_start < be:
            title = s.title or "기존 일정"
            rejected.append(RejectedSlot(
                start_time=s.start_time,
                end_time=s.end_time,
                reason=f"{title}{_wa_gwa(title)} 시간이 겹칩니다.",
            ))
    rejected.sort(key=lambda r: _to_min(r.start_time))

    # Recommended candidates: windows fully inside a free interval.
    candidates: List[RecommendedCandidate] = []
    for fs, fe in _free_intervals(win_start, win_end, busy):
        gap_len = fe - fs
        if gap_len < duration:
            continue
        start = fs
        while start + duration <= fe:
            end = start + duration
            score = 80
            sandwiched = (start in busy_ends) and (end in busy_starts)
            if sandwiched:
                score += 10
            if gap_len == duration:
                score += 2
            if start >= TOO_LATE_MINUTES:
                score -= 5
            score = max(0, min(100, score))

            if sandwiched:
                reason = f"기존 일정 사이에 있으며 예약 소요 시간 {duration}분을 만족합니다."
            else:
                reason = f"선호 시간대 내 빈 시간으로 예약 소요 시간 {duration}분을 만족합니다."

            candidates.append(RecommendedCandidate(
                candidate_id="",
                start_time=_to_hhmm(start),
                end_time=_to_hhmm(end),
                score=score,
                reason=reason,
                conflict=False,
            ))
            start += STEP_MINUTES

    candidates.sort(key=lambda x: (-x.score, _to_min(x.start_time)))
    for i, cand in enumerate(candidates, 1):
        cand.candidate_id = f"cand_{i:03d}"

    return ReservationCandidateData(
        target_date=c.target_date,
        recommended_candidates=candidates,
        rejected_slots=rejected,
    )
