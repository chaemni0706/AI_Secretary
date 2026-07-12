"""Qwen-3B EVIDENCE ADAPTER → EXISTING Rule Engine.

Qwen evidence(친숙 토큰) → 기존 Rule Engine 이 기대하는 VisionAnalysis evidence schema 로 변환하고,
**기존 evaluate_image_verification(Rule Engine core, 미수정)** 을 호출해 final_result 를 받는다.
Qwen 은 final_result 를 확정하지 않는다. 최종 판정 = 기존 Rule Engine.

pipeline:
  evidence = qwen3b_evidence_engine.extract(image_path, task)        # Qwen evidence
  rule_input = to_existing_rule_input(evidence, task)                # → VisionAnalysis schema
  data = run_existing_rule_engine(rule_input)                        # 기존 Rule Engine
  → final_result / rule_reason / rule_trace  (기존 시스템 호환 output)
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]  # repo root (…/AI_Secretary_FeatureJW_Qwen)
for p in (str(_ROOT), str(_HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import qwen3b_evidence_engine as engine  # noqa: E402

# ---- 기존 Rule Engine / schema import (core 미수정, read-only) ----
try:
    from backend.database.schema.image_verification_schema import (  # noqa: E402
        VisionAnalysis, ImageVerificationContext,
    )
    from backend.services.image_verification_rule_engine import (  # noqa: E402
        evaluate_image_verification,
    )
    _RULE_ENGINE_AVAILABLE = True
    _RULE_ENGINE_IMPORT_ERROR = ""
except Exception as _exc:  # 기존 Rule Engine 위치/의존성 문제 시 최소 fallback
    _RULE_ENGINE_AVAILABLE = False
    _RULE_ENGINE_IMPORT_ERROR = f"{type(_exc).__name__}: {_exc}"

# ---------------------------------------------------------------------------
# Qwen evidence 토큰 → 기존 Rule Engine schema evidence 코드 매핑
# ---------------------------------------------------------------------------
_WATER_POS = {"visible_water": "visible_water", "clear_liquid_visible": "visible_clear_liquid",
              "waterline_visible": "visible_water"}
_UNCERTAIN_CODE = {"water": "uncertain_liquid", "study": "uncertain_screen_content",
                   "exercise": "uncertain_exercise_environment"}


def _has(blob, kws):
    return any(k in blob for k in kws)


def _map(task, ev):
    """returns (schema_codes, objects, has_positive).
    keyword/substring 매칭(한/영) — Qwen 이 정확 토큰이 아니라 자유서술("cup","clear liquid","덤벨")을 줘도 매핑되고,
    dry-run 의 정확 토큰(clear_liquid_visible 등)도 substring 으로 함께 매칭된다.
    하드 disqualifier 는 'blockers' 필드만 사용(스키마 설계; negative_evidence 는 vocabulary-dump 위험으로 reject 근거 제외).
    blocker priority + uncertainty(high)→uncertain code."""
    pos_blob = " || ".join(str(x) for x in (
        (ev.get("positive_evidence") or []) + (ev.get("visible_objects") or []) +
        (ev.get("visible_actions") or []) + ([ev.get("scene_type")] if ev.get("scene_type") else []))).lower()
    block_blob = " || ".join(str(x) for x in (ev.get("blockers") or [])).lower()
    unc = str(ev.get("uncertainty", "high")).lower()
    codes, objs, has_pos = [], [], False

    if task == "water":
        # FP=0 보수 강화: '빈/투명 용기'를 물로 오인(water_009 빈 유리잔, water_035 빈 물병)하는 것이 최대 FP 원인.
        # (a) 빈 용기 신호는 positive/blocker 어디에 있든 empty_container blocker 로 강제하고 positive 를 막는다.
        empty_sig = _has(pos_blob + " || " + block_blob,
                         ("empty", "no liquid", "no water", "without water", "appears empty", "looks empty",
                          "빈 ", "비어", "비었", "물이 없", "액체가 없", "내용물이 없"))
        # (b) 물/맑은 액체는 '실제 담긴 액체 표면/수위'가 확인될 때만 인정(용기명 'water bottle' 만으론 불충분).
        water_liquid = _has(pos_blob, ("visible_water", "waterline", "water surface", "water level",
                                       "water in", "of water", "filled with water", "liquid inside", "liquid in the",
                                       "물이 담", "물을 마", "물이 들어", "물이 채", "수위", "액체가 담", "액체 표면"))
        clear_liquid = _has(pos_blob, ("clear_liquid", "clear liquid", "transparent liquid",
                                       "투명한 액체", "맑은 액체", "맑은 물"))
        container = _has(pos_blob, ("cup", "컵", "glass", "유리", "bottle", "병", "보틀", "transparent_container", "container"))
        if empty_sig:
            codes.append("empty_container")     # blocker → Rule Engine 거절/미verify
        else:
            if water_liquid:
                codes.append("visible_water"); has_pos = True
            elif clear_liquid:
                codes.append("visible_clear_liquid"); has_pos = True
            if has_pos and container:
                codes.append("filled_container")
                objs.append({"label": "water_bottle" if _has(pos_blob, ("bottle", "병", "보틀")) else "cup", "confidence": 0.6})
        # blockers
        if _has(block_blob, ("empty", "빈", "비어")): codes.append("empty_container")
        if _has(block_blob, ("opaque", "불투명", "opaque_container")): codes.append("opaque_closed_container")
        if _has(block_blob, ("coffee", "juice", "milk", "tea", "soda", "cola", "colored", "beverage",
                             "커피", "주스", "우유", "차", "탄산", "음료", "색")): codes.append("non_water_beverage")
        if _has(block_blob, ("unclear", "liquid_unclear", "불명확", "불명")): codes.append("uncertain_liquid")

    elif task == "study":
        if _has(pos_blob, ("open_book", "textbook", "open book", "책", "교재", "workbook", "워크북")): codes.append("open_textbook"); has_pos = True
        if _has(pos_blob, ("handwrit", "notes", "note-taking", "필기", "공책", "노트")): codes.append("handwritten_notes"); has_pos = True
        if _has(pos_blob, ("code", "코드", "programming", "개발환경", "terminal", "터미널", "editor", "에디터")): codes.append("code_editor"); has_pos = True
        if _has(pos_blob, ("document", "pdf", "문서", "보고서", "study_document", "educational")): codes.append("educational_document"); has_pos = True
        if _has(pos_blob, ("lecture", "강의", "강의자료")): codes.append("lecture_video"); has_pos = True
        if _has(pos_blob, ("problem", "문제", "solving", "writing_or_solving")): codes.append("problem_solving_material"); has_pos = True
        if _has(pos_blob, ("study_related_text", "study content", "study screen", "학습 화면", "공부 화면", "study_content")): codes.append("study_content_on_screen"); has_pos = True
        # FP=0 보수 강화: vocabulary-dump 방어. 한 장의 사진에 lecture_video+code_editor+textbook+notes 가
        # 동시에 잡히는 것은 물리적으로 불가능 → Qwen 이 허용 토큰을 나열(dump)한 것으로 보고 positive 전부 폐기.
        _study_pos = [c for c in codes if c not in {"gaming_content", "entertainment_video", "social_media",
                     "shopping_content", "closed_study_materials", "uncertain_screen_content"}]
        if len(_study_pos) >= 4:
            codes = [c for c in codes if c not in _study_pos]; has_pos = False
            objs = []
        if has_pos: objs.append({"label": "book", "confidence": 0.6})
        # blockers
        if _has(block_blob, ("game", "게임", "gaming")): codes.append("gaming_content")
        if _has(block_blob, ("youtube", "video", "movie", "drama", "netflix", "유튜브", "영상", "영화", "드라마")): codes.append("entertainment_video")
        if _has(block_blob, ("sns", "instagram", "인스타", "facebook", "tiktok")): codes.append("social_media")
        if _has(block_blob, ("shopping", "쇼핑")): codes.append("shopping_content")
        if _has(block_blob, ("empty_desk", "빈 책상", "closed", "닫힌", "laptop_only", "노트북만")): codes.append("closed_study_materials")
        if _has(block_blob, ("unclear", "screen_unclear", "불명")): codes.append("uncertain_screen_content")

    elif task == "exercise":
        yoga = _has(pos_blob, ("yoga", "요가"))
        lift = _has(pos_blob, ("lift", "dumbbell", "weight", "barbell", "덤벨", "바벨", "들어올리", "웨이트"))
        using = _has(pos_blob, ("using equipment", "using the equipment", "machine being used", "기구 사용", "기구를 사용"))
        generic = _has(pos_blob, ("push-up", "pushup", "push up", "squat", "run", "jog", "stretch", "exercis",
                                  "workout", "working out", "plank", "lunge", "푸시업", "팔굽혀", "스쿼트",
                                  "달리기", "러닝", "스트레칭", "운동 중", "운동하", "active_exercise_pose",
                                  "person_exercising", "workout_action"))
        if yoga:
            codes += ["yoga_pose_visible", "yoga_environment"]; has_pos = True
        elif lift:
            codes += ["exercise_pose_visible", "dumbbell_present"]; has_pos = True
        elif using:
            codes += ["exercise_pose_visible", "exercise_equipment_present", "gym_environment"]; has_pos = True
        elif generic:
            codes += ["home_exercise_pose_visible", "home_workout_environment"]; has_pos = True
        # blockers
        if _has(block_blob, ("equipment_only", "equipment only", "장비만")): codes.append("exercise_equipment_present")
        if _has(block_blob, ("gym_background", "background only", "배경만")): codes.append("gym_environment")
        if _has(block_blob, ("sitting", "resting", "앉", "쉬", "seated")): codes.append("insufficient_exercise_evidence")
        if _has(block_blob, ("folded", "stored", "접힌", "보관")): codes.append("insufficient_exercise_evidence")
        if _has(block_blob, ("clothes_only", "workout_clothes", "운동복만", "selfie", "셀카")): codes.append("unrelated_environment")
        if _has(block_blob, ("unclear", "pose_unclear", "불명")): codes.append("uncertain_exercise_environment")

    if unc == "high":
        codes.append(_UNCERTAIN_CODE[task])
    seen, out = set(), []
    for c in codes:
        if c not in seen:
            seen.add(c); out.append(c)
    return out, objs, has_pos


def _derive_exercise_activity(codes):
    """emitted exercise 코드 → context.exercise_activity_type (기존 규칙 요구). 기본 gym."""
    s = set(codes)
    if s & {"yoga_pose_visible", "yoga_environment", "yoga_mat_present", "yoga_studio_present"}:
        return "yoga"
    if s & {"home_exercise_pose_visible", "home_workout_environment", "exercise_mat_present", "resistance_band_present"}:
        return "home_workout"
    if s & {"running_environment", "treadmill_present", "treadmill_running_environment", "running_track_present"}:
        return "running"
    if s & {"swimming_pool_environment", "swimming_lane_present"}:
        return "swimming"
    if s & {"pilates_environment", "pilates_reformer_present", "pilates_equipment_present"}:
        return "pilates"
    return "gym"


def to_existing_rule_input(evidence_result, task):
    """Qwen evidence → 기존 Rule Engine 입력(VisionAnalysis + context + verification_type)."""
    ev = evidence_result["evidence"] if "evidence" in evidence_result else evidence_result
    codes, objs, has_pos = _map(task, ev)
    iq = str(ev.get("image_quality", "unknown")).lower()
    usable = iq not in ("poor", "unusable")
    va_dict = {
        "quality": {"brightness": "normal", "blur": "low" if usable else "high", "usable": usable, "issues": []},
        "scene": ev.get("scene_type") or None,
        "objects": objs,
        "visible_text": [],
        "study_visual_evidence": codes if task == "study" else [],
        "water_visual_evidence": codes if task == "water" else [],
        "exercise_visual_evidence": codes if task == "exercise" else [],
    }
    ctx = {}
    if task == "exercise" and has_pos:
        ctx = {"exercise_activity_type": _derive_exercise_activity(codes)}
    return {"verification_type": task, "analysis": va_dict, "context": ctx, "mapped_codes": codes}


def run_existing_rule_engine(rule_input):
    """기존 evaluate_image_verification 호출(core 미수정). Rule Engine 없으면 TODO fallback."""
    task = rule_input["verification_type"]
    if not _RULE_ENGINE_AVAILABLE:
        # TODO: 기존 Rule Engine 연결 지점. import 실패 시 보수적 minimal fallback(FP=0: 기본 retake).
        codes = rule_input.get("mapped_codes", [])
        return {"result": "retake_required", "score": 0, "mandatory_passed": False,
                "rule_reason": f"rule_engine_unavailable({_RULE_ENGINE_IMPORT_ERROR}); minimal fallback",
                "rule_trace": codes, "_fallback": True}
    va = VisionAnalysis(**rule_input["analysis"])
    ctx = ImageVerificationContext(**(rule_input.get("context") or {}))
    data = evaluate_image_verification(task, va, ctx)
    return {"result": data.result, "score": data.score, "mandatory_passed": data.mandatory_passed,
            "rule_reason": (data.rule_evidence[0].message if data.rule_evidence else ""),
            "rule_trace": [e.code for e in data.rule_evidence], "_fallback": False}


def verify(image_path, task, model_path=None, mock_output=None):
    """전체 파이프라인 → 기존 시스템 호환 output. final_result 는 기존 Rule Engine 산출."""
    er = engine.extract(image_path, task, mock_output=mock_output) if model_path is None \
        else engine.extract(image_path, task, model_path=model_path, mock_output=mock_output)
    ev = er["evidence"]
    rule_input = to_existing_rule_input(er, task)
    rule_out = run_existing_rule_engine(rule_input)
    return {
        "task": task,
        "final_result": rule_out["result"],           # ← 앱이 사용할 값(기존 Rule Engine 산출)
        "rule_reason": rule_out["rule_reason"],
        "rule_trace": rule_out["rule_trace"],
        "evidence": {
            "positive_evidence": ev.get("positive_evidence", []),
            "negative_evidence": ev.get("negative_evidence", []),
            "blockers": ev.get("blockers", []),
            "uncertainty": ev.get("uncertainty", "high"),
            "image_quality": ev.get("image_quality", "unknown"),
            "visible_objects": ev.get("visible_objects", []),
            "visible_actions": ev.get("visible_actions", []),
            "mapped_rule_codes": rule_input["mapped_codes"],
        },
        "debug": {  # 앱이 사용하면 안 되는 값
            "engine": "qwen3b",
            "qwen_raw_output": er["qwen_raw_output"],
            "qwen_parse_status": er["qwen_parse_status"],
            "rule_engine_fallback": rule_out.get("_fallback", False),
        },
    }
