# Qwen-3B Task Prompts — EVIDENCE EXTRACTION (not final verdict)

작성 2026-07-10, 개정. 구현: `local_eval/vlm_baseline/prompts.py`.
> **Qwen-3B 는 final_result 를 확정하지 않는다.** evidence 만 추출하고, **기존 Rule Engine 이 최종 판정**한다.
> 프롬프트는 evidence-extraction 중심(출력 스키마에 result 없음). 토큰은 adapter 가 기존 Rule Engine evidence 코드로 매핑.

## 공통
- 보이는 것만, 허용 토큰으로 보고. 추측 금지. 불확실하면 uncertainty=high + *_unclear 토큰. 실격 소견은 blockers 에.
- 출력: `{task, image_quality, visible_objects, visible_actions, scene_type, positive_evidence, negative_evidence, blockers, uncertainty, reason}` (result 없음).

## water
- positive tokens: `visible_water, clear_liquid_visible, transparent_container, cup_visible, bottle_visible, waterline_visible`
- blocker tokens: `empty_cup, empty_bottle, colored_beverage, coffee, juice, milk, tea, soda, opaque_container, liquid_unclear`
- 용기 이름만으로 물 단정 금지(가시 액체 있을 때만 visible_water/clear_liquid_visible).

## study
- positive tokens: `open_book, textbook, notes, study_document, code_screen, lecture_material, study_related_text, writing_or_solving`
- blocker tokens: `game, youtube, video, movie, shopping, sns, empty_desk, laptop_only, closed_book_only, screen_unclear`

## exercise
- positive tokens: `active_exercise_pose, person_exercising, person_using_equipment, workout_action, stretching, yoga_pose, lifting_weight`
- blocker tokens: `equipment_only, gym_background_only, workout_clothes_only, sitting, resting, selfie, folded_mat, pose_unclear`
- 실제 동작/사용이 보일 때만 positive. 장비만 → blocker.

## adapter 매핑(기존 Rule Engine evidence 코드로)
- water: clear_liquid_visible→visible_clear_liquid, visible_water/waterline_visible→visible_water, cup/bottle/transparent_container(+positive)→filled_container(+object); empty_*→empty_container, coffee/juice/milk/tea/soda/colored→non_water_beverage, opaque_container→opaque_closed_container, liquid_unclear→uncertain_liquid.
- study: open_book/textbook→open_textbook, notes→handwritten_notes, writing_or_solving→problem_solving_material, study_document→educational_document, code_screen→code_editor, lecture_material→lecture_video, study_related_text→study_content_on_screen; game→gaming_content, youtube/video/movie→entertainment_video, shopping→shopping_content, sns→social_media, empty_desk/closed_book_only→closed_study_materials, laptop_only→non_study_screen, screen_unclear→uncertain_screen_content.
- exercise(activity-consistent 묶음): pose류→home_exercise_pose_visible+home_workout_environment(activity=home_workout), yoga_pose→yoga_pose_visible+yoga_environment(yoga), lifting_weight→exercise_pose_visible+dumbbell_present(gym), person_using_equipment→exercise_pose_visible+exercise_equipment_present+gym_environment(gym); equipment_only→exercise_equipment_present, gym_background_only→gym_environment, sitting/resting/folded_mat→insufficient_exercise_evidence, workout_clothes_only/selfie→unrelated_environment, pose_unclear→uncertain_exercise_environment.
- uncertainty=high → task별 uncertain 코드(uncertain_liquid/uncertain_screen_content/uncertain_exercise_environment) 추가 → 기존 Rule Engine 이 retake 판단.
- **매핑만 하고 최종 판정은 기존 Rule Engine.** blocker 우선.
