"""Chat orchestrator — combines the empathy pipeline into one response.

This is an *orchestration* layer: it does not implement classification, scoring
or ranking itself, it only wires the service layers together:

    intent_classifier -> emotion_analyzer (reused) + empathy_engine
    -> solution_recommender -> (schedule_adjustment ? reschedule_recommender)
    -> empathy_engine.generate_empathy_response -> ChatRespondData

Never raises: any unexpected error degrades to a safe minimal response so the
API stays 200 inside the common envelope. No schedule is ever auto-changed.
"""

from __future__ import annotations

from typing import Dict, List

from backend.database.schema.chat_schema import (
    ChatRespondData,
    ChatRespondRequest,
    RescheduleCandidate,
    Solution,
)
from backend.database.schema.emotion_schema import (
    EmotionAnalyzeRequest,
    RecentContext,
)
from backend.services import (
    empathy_engine,
    intent_classifier,
    reschedule_recommender,
    solution_recommender,
    tts_response_builder,
    user_preference_service,
)
from backend.services.emotion_analyzer import analyze_emotion

# rule-based emotion label -> voice-response intent (only the 3 the spec covers;
# anything else is treated as a generic acknowledgment, not a diagnosis).
_EMOTION_TO_INTENT = {
    "fatigue": "emotion_tired",
    "anxiety": "emotion_anxious",
    "stress": "emotion_overload",
}


def _emotion_label(message: str, schedule_context: dict | None) -> dict:
    """Reuse the existing rule-based emotion analyzer (labels only)."""
    sched_count = None
    if schedule_context:
        sched = schedule_context.get("today_schedule") or []
        sched_count = len(sched) or None
    try:
        data = analyze_emotion(
            EmotionAnalyzeRequest(
                input=message,
                recent_context=RecentContext(schedule_count=sched_count),
            )
        )
        return data.model_dump()
    except Exception:
        return {"emotion": "neutral", "risk_level": "low"}


def respond(req: ChatRespondRequest) -> ChatRespondData:
    message = req.message or ""
    schedule_context = req.schedule_context.model_dump() if req.schedule_context else None
    user_profile = req.user_profile.model_dump() if req.user_profile else None

    try:
        # 1. intent
        intent_result = intent_classifier.select_intent(message)

        # 2. emotion (reused analyzer) + empathy strategy
        emotion_result = _emotion_label(message, schedule_context)
        empathy_result = empathy_engine.select_strategy(message, intent_result)

        # 3. solution policy
        solution_result = solution_recommender.recommend_solutions(
            intent_result=intent_result,
            empathy_result=empathy_result,
            schedule_context=schedule_context,
            user_profile=user_profile,
            user_message=message,
        )
        category = solution_result["category"]
        solutions_raw = solution_result["solutions"]

        # 4. optional reschedule candidates
        reschedule_raw: List[dict] = []
        if category == "schedule_adjustment":
            reschedule_raw = reschedule_recommender.recommend(
                schedule_context=schedule_context,
                user_profile=user_profile,
                target_event_id=req.target_event_id,
                emotion_state=emotion_result.get("emotion"),
            )

        # 5. final answer (LLM CoE prompt, else rule-based fallback)
        gen = empathy_engine.generate_empathy_response(
            user_message=message,
            strategy=empathy_result,
            emotion_result=emotion_result,
            solution_context={"category": category, "solutions": solutions_raw},
            schedule_context=schedule_context,
            user_profile=user_profile,
        )
        answer = gen["answer"]

        # tts_text: only for the rule-based fallback path — an LLM-generated
        # `answer` is left as-is (no LLM code added, no styling of LLM output).
        tts_text = None
        if not gen.get("used_llm"):
            voice_intent = _EMOTION_TO_INTENT.get(emotion_result.get("emotion"), "fallback_understood")
            preferences = user_preference_service.get_user_preferences(req.user_id)
            tts_text = tts_response_builder.build_tts_response(
                intent=voice_intent, slots={}, preferences=preferences,
            )
            # enforce response_length (and light tone tweaks) on the spoken line
            try:
                from backend.services import assistant_style_service
                profile = assistant_style_service.build_style_profile(preferences)
                tts_text = assistant_style_service.apply_response_style(tts_text, profile)
            except Exception:
                pass

        solutions = [Solution(**s) for s in solutions_raw]
        reschedule_candidates = [RescheduleCandidate(**c) for c in reschedule_raw]

        return ChatRespondData(
            selected_intent=intent_result["intent"],
            selected_strategy=empathy_result["strategy"],
            selected_solution_category=category,
            intent_scores=intent_result.get("scores", {}),
            empathy_scores=empathy_result.get("scores", {}),
            matched_keywords=empathy_result.get("matched_keywords", {}),
            solutions=solutions,
            reschedule_candidates=reschedule_candidates,
            answer=answer,
            requires_user_confirmation=True,
            tts_text=tts_text,
        )
    except Exception:
        # Degrade gracefully; never surface a 500 for a chat turn.
        return ChatRespondData(
            selected_intent="fallback",
            selected_strategy="fallback_llm_classification",
            selected_solution_category=None,
            answer="지금 마음이 어떤지 조금만 더 들려주실 수 있을까요? 함께 천천히 살펴볼게요.",
            requires_user_confirmation=True,
        )
