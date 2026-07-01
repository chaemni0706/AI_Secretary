"""Reschedule recommender tests (service-level)."""

from backend.services.reschedule_recommender import recommend


def _ctx(events, current="2026-06-30T15:00:00"):
    return {"current_time": current, "today_schedule": events}


TARGET = {
    "id": "e2", "title": "과제 정리", "category": "study", "priority": "medium",
    "start_time": "2026-06-30T17:00:00", "end_time": "2026-06-30T18:00:00",
    "is_fixed": False,
}
FIXED_MEETING = {
    "id": "e1", "title": "팀 회의", "category": "meeting", "priority": "high",
    "start_time": "2026-06-30T14:00:00", "end_time": "2026-06-30T15:00:00",
    "is_fixed": True,
}


def test_finds_target_by_id():
    out = recommend(_ctx([FIXED_MEETING, TARGET]), target_event_id="e2")
    assert out  # candidates produced for an adjustable target


def test_fixed_or_high_priority_excluded_as_target():
    # e1 is fixed/high -> not adjustable -> no candidates
    out = recommend(_ctx([FIXED_MEETING]), target_event_id="e1")
    assert out == []


def test_no_candidate_overlaps_existing_schedule():
    blocker = {
        "id": "e3", "title": "스터디", "category": "study", "priority": "low",
        "start_time": "2026-06-30T15:00:00", "end_time": "2026-06-30T16:00:00",
        "is_fixed": False,
    }
    out = recommend(_ctx([TARGET, blocker]), target_event_id="e2")
    # none of the returned 1h slots may overlap 15:00-16:00
    for c in out:
        # title carries the start hour like "...15:00로 옮기기"
        assert "15:00" not in c["title"]


def test_afternoon_preference_scores_higher():
    profile = {"preferred_time_blocks": ["afternoon"], "preferred_study_hours": [15, 16]}
    out = recommend(_ctx([TARGET]), user_profile=profile, target_event_id="e2")
    assert out
    # top candidate should be a preferred afternoon slot with a strong score
    assert out[0]["score"] >= 0.5


def test_late_night_penalized():
    # target late so only evening/late candidates exist; ensure late ones rank lower
    late_target = dict(TARGET, start_time="2026-06-30T20:00:00",
                       end_time="2026-06-30T21:00:00")
    out = recommend(_ctx([late_target], current="2026-06-30T08:00:00"),
                    target_event_id="e2")
    late = [c for c in out if "21:00" in c["title"] or "22:00" in c["title"]]
    non_late = [c for c in out if c not in late]
    if late and non_late:
        assert max(c["score"] for c in non_late) >= max(c["score"] for c in late)


def test_candidate_contract_fields():
    out = recommend(_ctx([TARGET]), target_event_id="e2")
    assert out
    for c in out:
        for field in ("reason", "model_basis", "action_buttons",
                      "requires_user_confirmation", "score"):
            assert field in c
        assert c["requires_user_confirmation"] is True
        assert 0.0 <= c["score"] <= 1.0
        assert c["model_basis"]["method"] == "ml_ready_weighted_ranking"


def test_sorted_by_score_desc():
    out = recommend(_ctx([TARGET]), target_event_id="e2")
    scores = [c["score"] for c in out]
    assert scores == sorted(scores, reverse=True)


def test_no_candidates_is_safe_not_error():
    # empty schedule / no adjustable target -> empty list, no exception
    assert recommend(_ctx([FIXED_MEETING])) == []
    assert recommend(None) == []
    assert recommend({"today_schedule": []}) == []
