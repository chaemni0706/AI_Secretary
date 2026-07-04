from backend.database.schema.image_verification_schema import (
    ImageObjectObservation,
    ImageVerificationContext,
    ImageQuality,
    LocationInput,
    TimeContext,
    VisionAnalysis,
)
from backend.services.image_verification_rule_engine import evaluate_image_verification


def test_clear_unrelated_photo_is_rejected():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        scene="street",
        objects=[],
    )

    data = evaluate_image_verification("gym", analysis, ImageVerificationContext())

    assert data.result == "rejected"
    assert data.mandatory_passed is False


def test_low_quality_photo_requires_retake():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=False, blur="high", issues=["blurred"]),
        scene="gym",
        objects=[ImageObjectObservation(label="treadmill", confidence=0.9)],
    )

    data = evaluate_image_verification("gym", analysis, ImageVerificationContext())

    assert data.result == "retake_required"
    assert data.mandatory_passed is False


def test_duplicate_objects_score_once():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        scene="table",
        objects=[
            ImageObjectObservation(label="pill_pack", confidence=0.9),
            ImageObjectObservation(label="pill_pack", confidence=0.8),
            ImageObjectObservation(label="blister_pack", confidence=0.9),
        ],
    )

    data = evaluate_image_verification("medicine", analysis, ImageVerificationContext())

    assert data.score_breakdown.object_score == 35
    assert any(e.code == "similar_group_cap" for e in data.rule_evidence)


def test_gps_is_optional_and_not_penalized_when_missing():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        scene="gym",
        objects=[ImageObjectObservation(label="treadmill", confidence=0.9)],
    )

    without_gps = evaluate_image_verification("gym", analysis, ImageVerificationContext())
    with_gps = evaluate_image_verification(
        "gym",
        analysis,
        ImageVerificationContext(
            location=LocationInput(latitude=37.5665, longitude=126.9780),
            target_location=LocationInput(latitude=37.5665, longitude=126.9780),
        ),
    )

    assert without_gps.score_breakdown.gps_score == 0
    assert with_gps.score_breakdown.gps_score == 5
    assert with_gps.score == without_gps.score + 5


def test_gps_target_location_is_required_for_score():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        scene="gym",
        objects=[ImageObjectObservation(label="treadmill", confidence=0.9)],
    )

    data = evaluate_image_verification(
        "gym",
        analysis,
        ImageVerificationContext(location=LocationInput(latitude=37.5665, longitude=126.9780)),
    )

    assert data.score_breakdown.gps_score == 0


def test_medicine_does_not_use_gps_score():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        scene="table",
        objects=[ImageObjectObservation(label="pill_pack", confidence=0.9)],
    )
    data = evaluate_image_verification(
        "medicine",
        analysis,
        ImageVerificationContext(
            location=LocationInput(latitude=37.5665, longitude=126.9780),
            target_location=LocationInput(latitude=37.5665, longitude=126.9780),
        ),
    )

    assert data.score_breakdown.gps_score == 0
    assert not any(e.code == "gps" for e in data.rule_evidence)


def test_empty_cup_is_not_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        scene="table",
        objects=[ImageObjectObservation(label="cup", confidence=0.9)],
        water_visual_evidence=["empty_container"],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result != "verified"
    assert data.result == "rejected"
    assert any(e.code == "water_priority:empty_container" for e in data.rule_evidence)


def test_water_container_with_liquid_can_be_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        scene="table",
        objects=[ImageObjectObservation(label="water_bottle", confidence=0.9)],
        water_visual_evidence=["visible_clear_liquid", "filled_container"],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "verified"


def test_water_clear_cup_is_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        scene="table",
        objects=[ImageObjectObservation(label="glass", confidence=0.9)],
        water_visual_evidence=["visible_water", "filled_container"],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "verified"
    assert data.score == 65


def test_two_liter_pet_bottle_with_water_is_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="pet_bottle", confidence=0.9)],
        water_visual_evidence=["visible_clear_liquid", "filled_container"],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "verified"


def test_sealed_water_bottle_is_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="water_bottle", confidence=0.9)],
        water_visual_evidence=["sealed_water_bottle"],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "verified"
    assert data.score >= 60


def test_receiving_water_from_dispenser_into_cup_is_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[
            ImageObjectObservation(label="water_dispenser", confidence=0.9),
            ImageObjectObservation(label="cup", confidence=0.9),
        ],
        water_visual_evidence=["water_stream", "receiving_water", "container_under_dispenser"],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "verified"


def test_empty_pet_bottle_is_rejected():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="pet_bottle", confidence=0.9)],
        water_visual_evidence=["empty_container"],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "rejected"


def test_coffee_or_juice_is_rejected():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="cup", confidence=0.9)],
        water_visual_evidence=["non_water_beverage", "filled_container"],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "rejected"


def test_closed_opaque_tumbler_requires_retake():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="tumbler", confidence=0.9)],
        water_visual_evidence=["opaque_closed_container"],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "retake_required"


def test_dispenser_without_stream_and_container_is_rejected():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="water_dispenser", confidence=0.9)],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "rejected"
    assert data.mandatory_passed is False


def test_water_scene_scores_do_not_increase_for_table_kitchen_or_desk():
    for scene in ["table", "kitchen", "desk"]:
        analysis = VisionAnalysis(
            quality=ImageQuality(usable=True),
            scene=scene,
            objects=[],
        )

        data = evaluate_image_verification("water", analysis, ImageVerificationContext())

        assert data.score_breakdown.base_score == 0
        assert data.score_breakdown.scene_score == 0
        assert data.score == 0


def test_clear_water_in_transparent_glass_is_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="glass", confidence=0.9)],
        water_visual_evidence=["visible_water", "filled_container"],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "verified"


def test_clear_water_in_tall_transparent_glass_is_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        scene="kitchen",
        objects=[ImageObjectObservation(label="glass", confidence=0.9)],
        water_visual_evidence=["visible_water", "filled_container"],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "verified"
    assert data.score_breakdown.scene_score == 0


def test_blue_lemon_drink_is_rejected():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="glass", confidence=0.9)],
        water_visual_evidence=["non_water_beverage"],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "rejected"


def test_uncertain_clear_liquid_requires_retake():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="glass", confidence=0.9)],
        water_visual_evidence=["uncertain_liquid"],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "retake_required"


def test_multiple_empty_pet_bottles_are_rejected():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[
            ImageObjectObservation(label="pet_bottle", confidence=0.9),
            ImageObjectObservation(label="pet_bottle", confidence=0.8),
        ],
        water_visual_evidence=["empty_container"],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "rejected"


def test_colored_drink_pet_bottle_is_rejected():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="pet_bottle", confidence=0.9)],
        water_visual_evidence=["non_water_beverage"],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "rejected"


def test_duplicate_water_objects_and_evidence_score_once():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[
            ImageObjectObservation(label="cup", confidence=0.9),
            ImageObjectObservation(label="cup", confidence=0.8),
            ImageObjectObservation(label="glass", confidence=0.9),
        ],
        water_visual_evidence=[
            "visible_water",
            "visible_water",
            "visible_clear_liquid",
            "filled_container",
            "filled_container",
        ],
    )

    data = evaluate_image_verification("water", analysis, ImageVerificationContext())

    assert data.result == "verified"
    assert data.score_breakdown.object_score == 65


def test_laptop_alone_is_not_verified_for_study():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        scene="desk",
        objects=[ImageObjectObservation(label="laptop", confidence=0.9)],
        visible_text=["chapter"],
    )

    data = evaluate_image_verification("study", analysis, ImageVerificationContext())

    assert data.result != "verified"
    assert data.result == "rejected"


def test_wakeup_requires_scheduled_time_and_window():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        scene="bedroom",
        objects=[
            ImageObjectObservation(label="bed", confidence=0.9),
            ImageObjectObservation(label="sunlight", confidence=0.9),
        ],
    )

    missing_time = evaluate_image_verification("wakeup", analysis, ImageVerificationContext())
    in_window = evaluate_image_verification(
        "wakeup",
        analysis,
        ImageVerificationContext(
            time=TimeContext(
                captured_at="2026-07-01T07:20:00+09:00",
                scheduled_at="2026-07-01T07:00:00+09:00",
            )
        ),
    )

    assert missing_time.mandatory_passed is False
    assert missing_time.result == "rejected"
    assert in_window.mandatory_passed is True
    assert in_window.result == "verified"


def _exercise_context(activity_type):
    return ImageVerificationContext(exercise_activity_type=activity_type)


def test_exercise_gym_with_weight_machine_is_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="weight_machine", confidence=0.9)],
        exercise_visual_evidence=["gym_environment", "weight_machine_present"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("gym"))

    assert data.result == "verified"


def test_exercise_gym_mirror_selfie_with_equipment_is_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[
            ImageObjectObservation(label="gym_mirror", confidence=0.9),
            ImageObjectObservation(label="dumbbell", confidence=0.9),
        ],
        exercise_visual_evidence=["gym_environment", "dumbbell_present"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("gym"))

    assert data.result == "verified"


def test_exercise_empty_gym_with_core_equipment_is_environment_verification_only():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[
            ImageObjectObservation(label="treadmill", confidence=0.9),
            ImageObjectObservation(label="exercise_bike", confidence=0.9),
        ],
        exercise_visual_evidence=["gym_environment", "treadmill_present", "exercise_bike_present"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("gym"))

    assert data.result == "verified"
    assert not any("완료" in item.message for item in data.rule_evidence)


def test_exercise_home_pull_up_bar_is_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="pull_up_bar", confidence=0.9)],
        exercise_visual_evidence=["pull_up_bar_present"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("home_workout"))

    assert data.result == "verified"


def test_exercise_gym_stair_climber_environment_is_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="stair_climber", confidence=0.9)],
        exercise_visual_evidence=["gym_environment", "weight_machine_present"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("gym"))

    assert data.result == "verified"


def test_exercise_yoga_mat_and_pose_is_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="yoga_mat", confidence=0.9)],
        exercise_visual_evidence=["yoga_environment", "yoga_mat_present", "yoga_pose_visible"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("yoga"))

    assert data.result == "verified"


def test_exercise_yoga_mat_without_pose_can_be_verified_when_environment_is_clear():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="yoga_mat", confidence=0.9)],
        exercise_visual_evidence=["yoga_environment", "yoga_mat_present"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("yoga"))

    assert data.result == "verified"


def test_exercise_pilates_reformer_is_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="pilates_reformer", confidence=0.9)],
        exercise_visual_evidence=["pilates_reformer_present", "pilates_equipment_present"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("pilates"))

    assert data.result == "verified"


def test_exercise_outdoor_running_track_is_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="running_track", confidence=0.9)],
        exercise_visual_evidence=["running_track_present"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("running"))

    assert data.result == "verified"
    assert any(item.code == "exercise_limitation:running" for item in data.rule_evidence)


def test_exercise_swimming_lane_is_verified():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="swimming_lane", confidence=0.9)],
        exercise_visual_evidence=["swimming_pool_environment", "swimming_lane_present"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("swimming"))

    assert data.result == "verified"
    assert any(item.code == "exercise_limitation:swimming" for item in data.rule_evidence)


def test_exercise_plain_room_for_gym_is_rejected():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="home_interior", confidence=0.9)],
        exercise_visual_evidence=["unrelated_environment"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("gym"))

    assert data.result == "rejected"


def test_exercise_swimming_pool_requested_as_gym_is_wrong_activity_rejected():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="swimming_pool", confidence=0.9)],
        exercise_visual_evidence=["swimming_pool_environment", "swimming_lane_present"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("gym"))

    assert data.result == "rejected"
    assert any(item.code == "exercise_priority:wrong_activity_environment" for item in data.rule_evidence)


def test_exercise_blurry_gym_requires_retake():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=False, blur="high"),
        objects=[ImageObjectObservation(label="weight_machine", confidence=0.9)],
        exercise_visual_evidence=["gym_environment", "weight_machine_present"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("gym"))

    assert data.result == "retake_required"


def test_exercise_laptop_and_desk_are_rejected():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[
            ImageObjectObservation(label="laptop", confidence=0.9),
            ImageObjectObservation(label="desk", confidence=0.9),
        ],
        exercise_visual_evidence=["unrelated_environment"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("gym"))

    assert data.result == "rejected"


def test_exercise_pose_is_not_required_when_environment_and_equipment_exist():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[ImageObjectObservation(label="barbell", confidence=0.9)],
        exercise_visual_evidence=["gym_environment", "barbell_present"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("gym"))

    assert data.result == "verified"


def test_exercise_pose_only_with_uncertain_environment_requires_retake():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        exercise_visual_evidence=["exercise_pose_visible", "uncertain_exercise_environment"],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("gym"))

    assert data.result == "retake_required"


def test_duplicate_exercise_equipment_and_evidence_score_once():
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[
            ImageObjectObservation(label="dumbbell", confidence=0.9),
            ImageObjectObservation(label="dumbbell", confidence=0.8),
            ImageObjectObservation(label="barbell", confidence=0.9),
        ],
        exercise_visual_evidence=[
            "gym_environment",
            "dumbbell_present",
            "dumbbell_present",
            "barbell_present",
        ],
    )

    data = evaluate_image_verification("exercise", analysis, _exercise_context("gym"))

    assert data.result == "verified"
    assert data.score_breakdown.object_score == 65
