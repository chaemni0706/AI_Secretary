"""Vision analyzer interface and OpenAI-backed implementation.

The analyzer returns observable image facts only. It must not decide whether an
image is verified; that belongs to the deterministic rule engine.
"""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable

from backend.core.config import settings
from backend.database.schema.image_verification_schema import (
    ImageQuality,
    VerificationType,
    VisionAnalysis,
)


class VisionAnalyzer(ABC):
    """Interface for replaceable VLM implementations."""

    @abstractmethod
    def analyze(
        self,
        image_path: Path,
        verification_type: VerificationType,
        allowed_labels: Iterable[str],
    ) -> VisionAnalysis:
        """Return observable image facts constrained to `allowed_labels`."""


class MockVisionAnalyzer(VisionAnalyzer):
    """Test/deterministic analyzer that returns a provided analysis."""

    def __init__(self, analysis: VisionAnalysis):
        self.analysis = analysis

    def analyze(
        self,
        image_path: Path,
        verification_type: VerificationType,
        allowed_labels: Iterable[str],
    ) -> VisionAnalysis:
        allowed = set(allowed_labels)
        objects = [obj for obj in self.analysis.objects if obj.label in allowed]
        return self.analysis.model_copy(update={"objects": objects})


class OpenAIVisionAnalyzer(VisionAnalyzer):
    """OpenAI vision implementation.

    This class is deliberately thin and replaceable. Any API failure degrades to
    an unusable analysis so callers can return a retake/rejected result without
    leaking provider errors.
    """

    def analyze(
        self,
        image_path: Path,
        verification_type: VerificationType,
        allowed_labels: Iterable[str],
    ) -> VisionAnalysis:
        if not settings.OPENAI_API_KEY:
            return _unavailable_analysis("OpenAI API key is not configured.")

        allowed = sorted(set(allowed_labels))
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
            image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
            prompt = _build_prompt(verification_type, allowed)
            resp = client.responses.parse(
                model=settings.OPENAI_VISION_MODEL,
                temperature=0,
                text_format=VisionAnalysis,
                instructions=(
                    "Return only observable visual facts. "
                    "Never decide final verification status. "
                    "Do not include verified, rejected, retake_required, result, score, "
                    "pass, fail, decision, or judgment."
                ),
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": "input_image",
                                "image_url": f"data:image/jpeg;base64,{image_b64}",
                                "detail": "high",
                            },
                        ],
                    },
                ],
            )
            parsed = resp.output_parsed
            if parsed is None:
                return _unavailable_analysis("Vision response was empty.")
            return _filter_analysis(parsed, allowed)
        except Exception:
            return _unavailable_analysis("Vision analysis failed.")


def _build_prompt(verification_type: VerificationType, allowed_labels: list[str]) -> str:
    labels = ", ".join(allowed_labels)
    return (
        f"Verification type: {verification_type}.\n"
        f"Allowed object labels: {labels}.\n"
        "Return observable fields for quality, scene, objects, visible_text, "
        "visual_evidence, study_visual_evidence, water_visual_evidence, and exercise_visual_evidence.\n"
        "Object labels must be from the allowed object labels only.\n"
        "For study verification, study_visual_evidence must use only these enum values: "
        "open_textbook, open_workbook, handwritten_notes, highlighted_text, "
        "problem_solving_material, study_content_on_screen, lecture_video, "
        "educational_document, code_editor, study_timer, gaming_content, "
        "entertainment_video, social_media, shopping_content, non_study_screen, "
        "closed_study_materials, uncertain_screen_content.\n"
        "For non-study verification, study_visual_evidence must be an empty list.\n"
        "For water verification, water_visual_evidence must use only these enum values: "
        "visible_water, visible_clear_liquid, filled_container, sealed_water_bottle, "
        "water_stream, container_under_dispenser, receiving_water, empty_container, "
        "opaque_closed_container, non_water_beverage, uncertain_liquid.\n"
        "For non-water verification, water_visual_evidence must be an empty list.\n"
        "For exercise verification, exercise_visual_evidence must use only these enum values: "
        "exercise_environment, exercise_equipment_present, exercise_pose_visible, gym_environment, "
        "treadmill_present, dumbbell_present, barbell_present, weight_machine_present, "
        "exercise_bike_present, gym_bench_present, running_environment, running_track_present, "
        "treadmill_running_environment, stadium_track_present, park_running_path_present, "
        "swimming_pool_environment, swimming_lane_present, lane_rope_present, swim_cap_present, "
        "swim_goggles_present, yoga_environment, yoga_mat_present, yoga_studio_present, "
        "yoga_pose_visible, pilates_environment, pilates_reformer_present, pilates_equipment_present, "
        "pilates_studio_present, pilates_pose_visible, home_workout_environment, exercise_mat_present, "
        "resistance_band_present, home_dumbbell_present, kettlebell_present, pull_up_bar_present, "
        "home_exercise_pose_visible, unrelated_environment, wrong_activity_environment, "
        "insufficient_exercise_evidence, uncertain_exercise_environment.\n"
        "For non-exercise verification, exercise_visual_evidence must be an empty list."
    )


def _filter_analysis(analysis: VisionAnalysis, allowed_labels: Iterable[str]) -> VisionAnalysis:
    allowed = set(allowed_labels)
    objects = [obj for obj in analysis.objects if obj.label in allowed]
    return analysis.model_copy(update={"objects": objects})


def _unavailable_analysis(issue: str) -> VisionAnalysis:
    return VisionAnalysis(
        quality=ImageQuality(usable=False, issues=[issue]),
        visual_evidence=[issue],
    )


def get_default_vision_analyzer() -> VisionAnalyzer:
    """1차 VisionAnalyzer 선택.

    기본은 OpenAI 없이 로컬 온디바이스 VLM(IMAGE_VERIFICATION_VLM_PROVIDER, 기본 smolvlm).
    IMAGE_VERIFICATION_USE_OPENAI=true 이거나 provider 가 'openai' 면 OpenAIVisionAnalyzer.
    로컬 provider 로딩이 불가하면 OpenAIVisionAnalyzer 로 폴백(키 없으면 unusable 로 안전 처리).
    """
    provider = (settings.IMAGE_VERIFICATION_VLM_PROVIDER or "smolvlm").strip().lower()
    if settings.IMAGE_VERIFICATION_USE_OPENAI or provider == "openai":
        return OpenAIVisionAnalyzer()
    try:
        from backend.services.local_vlm_analyzer import get_local_vlm_analyzer

        return get_local_vlm_analyzer(provider)
    except Exception:  # noqa: BLE001 - 로컬 provider import/로딩 실패 시 OpenAI 경로로 폴백
        return OpenAIVisionAnalyzer()


def get_study_fallback_analyzer() -> VisionAnalyzer | None:
    """study 재판정용 fallback analyzer(IMAGE_VERIFICATION_STUDY_FALLBACK, 기본 qwen_awq).

    비활성(빈 값/none)이거나 로딩 불가하면 None → 상위에서 fallback 을 건너뛴다.
    """
    key = (settings.IMAGE_VERIFICATION_STUDY_FALLBACK or "").strip().lower()
    if not key or key in {"none", "off", "disabled"}:
        return None
    if key == "openai":
        return OpenAIVisionAnalyzer()
    try:
        from backend.services.local_vlm_analyzer import get_local_vlm_analyzer

        return get_local_vlm_analyzer(key)
    except Exception:  # noqa: BLE001
        return None
