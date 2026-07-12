"""VLM Fallback Verifier — SmolVLM local-first + Qwen-3B(non-AWQ bf16) fallback + EXISTING Rule Engine.

Camera Image + task
  → SmolVLM Local Evidence Engine → smol adapter → 기존 Rule Engine → local_result
  → confident 이면 local_result 반환
  → 아니면 Qwen-3B Fallback Evidence Engine → qwen adapter → 기존 Rule Engine → final_result
  → Qwen 실패 시 fail-safe retake_required

원칙: Smol/Qwen 은 evidence engine. **final_result 는 반드시 기존 evaluate_image_verification(Rule Engine core 미수정)** 또는
fail-safe retake 에서 나온다. Smol/Qwen raw result 를 직접 final 로 쓰지 않는다.
Qwen fallback runtime 은 **non-AWQ Qwen2.5-VL-3B-Instruct bf16** 사용(AWQ 는 generate 실패).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import os                                            # noqa: E402
import smol_evidence_engine as smol_engine          # noqa: E402
import smol_evidence_adapter as smol_adapter        # noqa: E402
import server_vlm_evidence_engine as server_engine   # noqa: E402  (A.X/Qwen pluggable + FP guard)

# 선택된 server fallback VLM. Gate C full-test(171) 비교: Qwen2.5-VL-7B 가 A.X 대비 FP 6<9,
# study/exercise FP=0, engine_error/parse_failed=0 로 우위 → 기본값 채택. env VLM_FALLBACK_MODEL 로 교체.
FALLBACK_MODEL_KEY = os.environ.get("VLM_FALLBACK_MODEL", "qwen25_7b")


# --------------------------------------------------------------------------- policy
def should_accept_local_result(lo: dict) -> bool:
    """Smol local_result 채택 여부(FP=0 최우선; SmolVLM FP=9 이력 고려).

    핵심 정책: **Smol 의 `verified` 는 절대 로컬에서 채택하지 않는다** — SmolVLM-500M 이 FAIL 이미지에도
    positive 근거를 만들어 FP 를 유발한 이력(FP=9) 때문. verified 후보는 항상 Qwen fallback 이 재확인.
    로컬 채택은 **명확한 blocker 기반 `rejected` 만** 허용(거절 방향은 FP 를 만들 수 없어 안전).
    """
    if lo.get("engine_error") or lo.get("parse_status") not in ("clean", "repaired"):
        return False
    if lo.get("rule_engine_fallback"):
        return False
    fr = lo.get("final_result")
    if fr == "rejected":
        # 명확한 blocker 로 거절 + 불확실하지 않을 때만 로컬 채택(FP 무관, Qwen 부하 절감).
        return bool(lo.get("has_blocker")) and lo.get("uncertainty") == "low"
    # verified / retake_required / error → 항상 Qwen fallback (Smol verified 로컬 채택 금지).
    return False


def should_fallback_to_qwen(lo: dict) -> bool:
    """Smol 결과가 confident 하지 않으면 Qwen fallback."""
    return not should_accept_local_result(lo)


# --------------------------------------------------------------------------- paths
def run_smol_local_path(image_path, task, mock_smol=None):
    er = smol_engine.extract(image_path, task, mock_va=mock_smol)
    return smol_adapter.to_local_output(er, task)


def run_qwen_fallback_path(image_path, task, mock_qwen=None):
    """server VLM(A.X) evidence → 기존 Rule Engine → FP guard. engine 실패(parse failed/rule fallback/engine_error) 감지.
    함수명은 하위호환 유지(orchestrator 호출부). guard 는 sve.verify 내부에서 적용(verified→위험시 retake 강등)."""
    out = server_engine.verify(image_path, task, FALLBACK_MODEL_KEY, mock_output=mock_qwen, guard=True)
    dbg = out.get("debug", {})
    raw = dbg.get("raw_output", "")
    failed = (dbg.get("parse_status") == "failed") or dbg.get("rule_engine_fallback") \
        or (isinstance(raw, str) and raw.startswith("[engine_error]"))
    return out, bool(failed)


# --------------------------------------------------------------------------- orchestrator
def _blank(task, image_id=""):
    return {"task": task, "image_id": image_id, "final_result": "retake_required",
            "engine_used": "fail_safe", "fallback_used": False,
            "local_result": "unknown", "fallback_result": None,
            "review_required": False, "review_reason": "",
            "rule_reason": "", "rule_trace": [], "evidence": {},
            "debug": {"local_engine": "smol", "fallback_engine": FALLBACK_MODEL_KEY,
                      "local_parse_status": "", "fallback_parse_status": "",
                      "local_error": "", "fallback_error": "", "guard_reason": ""}}


def _apply_review_policy(out):
    """VLM-eligible scope 밖(비시각 맥락)일 수 있는 verified 를 secondary_review 로 라우팅.

    확정 근거: full-test 잔여 FP 는 전부 water 에서만, 그리고 변기물/오염수(non_visual_context)·
    맥주+물 동시(label_review)·borderline 처럼 **외관만으론 PASS 물과 구분 불가**한 케이스였다.
    추론 시 이를 사전 판별할 시각 신호가 없으므로, **verified(water) 는 자동 확정하지 않고 review_required 로**
    표시해 앱이 secondary_review(사람/GPS·맥락 rule)로 보낸다. exercise/study 는 full-test FP=0 → 그대로 자동 확정.
    Rule Engine core 미수정; orchestrator layer 정책.
    """
    if out.get("final_result") == "verified" and out.get("task") == "water":
        out["review_required"] = True
        out["review_reason"] = "water_non_visual_context_risk"
    return out


def verify_image_with_vlm_fallback(image_path, task, force_fallback=False, no_qwen=False,
                                   image_id="", mock_smol=None, mock_qwen=None):
    """공개 진입점: 핵심 파이프라인 실행 후 secondary_review 정책 적용."""
    out = _verify_core(image_path, task, force_fallback=force_fallback, no_qwen=no_qwen,
                       image_id=image_id, mock_smol=mock_smol, mock_qwen=mock_qwen)
    return _apply_review_policy(out)


def _verify_core(image_path, task, force_fallback=False, no_qwen=False,
                 image_id="", mock_smol=None, mock_qwen=None):
    out = _blank(task, image_id)
    # 1) Smol local
    lo = run_smol_local_path(image_path, task, mock_smol=mock_smol)
    out["local_result"] = lo.get("final_result", "error")
    out["debug"]["local_parse_status"] = lo.get("parse_status", "")
    out["debug"]["local_error"] = lo.get("engine_error", "")
    accept = should_accept_local_result(lo) and not force_fallback
    if accept:
        out.update({"final_result": lo["final_result"], "engine_used": "smol", "fallback_used": False,
                    "rule_reason": lo.get("rule_reason", ""), "rule_trace": lo.get("rule_trace", []),
                    "evidence": {"source": "smol", "codes": lo.get("evidence_codes", []),
                                 "uncertainty": lo.get("uncertainty"), "image_quality": lo.get("image_quality")}})
        return out
    # 2) fallback needed
    if no_qwen:
        # local-only 모드(smoke): local 결과를 그대로 노출(비채택이면 그대로 반환, 앱은 미사용 권장)
        out.update({"final_result": lo.get("final_result", "retake_required") if lo.get("final_result") != "error" else "retake_required",
                    "engine_used": "smol", "fallback_used": False,
                    "rule_reason": lo.get("rule_reason", "") or "qwen_skipped(no_qwen)",
                    "rule_trace": lo.get("rule_trace", []),
                    "evidence": {"source": "smol", "codes": lo.get("evidence_codes", []),
                                 "uncertainty": lo.get("uncertainty"), "image_quality": lo.get("image_quality")}})
        out["debug"]["fallback_error"] = "qwen_skipped(no_qwen)"
        return out
    qwen_out, qwen_failed = run_qwen_fallback_path(image_path, task, mock_qwen=mock_qwen)
    out["fallback_used"] = True
    out["fallback_result"] = qwen_out.get("final_result")
    out["debug"]["fallback_parse_status"] = qwen_out.get("debug", {}).get("parse_status", "")
    out["debug"]["fallback_error"] = ("fallback_engine_error" if qwen_failed else "")
    out["debug"]["guard_reason"] = qwen_out.get("guard_reason", "")
    if qwen_failed:
        out.update({"final_result": "retake_required", "engine_used": "fail_safe",
                    "rule_reason": "fallback_engine_error", "rule_trace": [],
                    "evidence": {"source": "fallback_failed", "fallback": qwen_out.get("evidence", {})}})
        return out
    out.update({"final_result": qwen_out["final_result"], "engine_used": "server_fallback",
                "rule_reason": qwen_out.get("rule_reason", ""), "rule_trace": qwen_out.get("rule_trace", []),
                "evidence": {"source": FALLBACK_MODEL_KEY, **qwen_out.get("evidence", {})}})
    return out


# --------------------------------------------------------------------------- dry-run (8 cases)
def _smol_va(task, codes, usable=True, obj=None):
    d = {"quality": {"brightness": "normal", "blur": "low", "usable": usable, "issues": []},
         "scene": None, "objects": obj or [], "visible_text": [], "visual_evidence": [],
         "study_visual_evidence": [], "water_visual_evidence": [], "exercise_visual_evidence": []}
    d[f"{task}_visual_evidence"] = codes
    return d


_CUP = [{"label": "cup", "confidence": 0.7}]


def _dry_run():
    cases = [
        # 1 Smol verified → 정책상 로컬 채택 금지, 항상 Qwen fallback 재확인
        ("water", _smol_va("water", ["visible_water", "filled_container"], obj=_CUP),
         {"task": "water", "image_quality": "good",
          "positive_evidence": ["clear_liquid_visible", "transparent_container"],
          "blockers": [], "uncertainty": "low"}, False,
         {"fallback_used": True, "engine_used": "server_fallback", "final_result": "verified"}),
        # 2 Smol confident rejected w/ blocker
        ("water", _smol_va("water", ["non_water_beverage"]), None, False,
         {"fallback_used": False, "engine_used": "smol", "final_result": "rejected"}),
        # 3 Smol retake (empty evidence) → fallback (qwen verified)
        ("water", _smol_va("water", []),
         {"task": "water", "image_quality": "good", "positive_evidence": ["clear_liquid_visible"],
          "blockers": [], "uncertainty": "low"}, False,
         {"fallback_used": True, "engine_used": "server_fallback"}),
        # 4 Smol parse_failed → fallback
        ("study", {"__engine_error__": True}, {"task": "study", "image_quality": "good",
         "positive_evidence": ["open_book", "study_document"], "blockers": [], "uncertainty": "low"}, False,
         {"fallback_used": True}),
        # 5 Smol verified but uncertainty high → fallback
        ("water", _smol_va("water", ["visible_water", "filled_container", "uncertain_liquid"], obj=_CUP),
         {"task": "water", "image_quality": "good", "positive_evidence": ["clear_liquid_visible"],
          "blockers": [], "uncertainty": "low"}, False,
         {"fallback_used": True}),
        # 6 Qwen fallback success (smol empty → qwen verified)
        ("exercise", _smol_va("exercise", []),
         {"task": "exercise", "image_quality": "good", "positive_evidence": ["person_exercising", "workout_action"],
          "blockers": [], "uncertainty": "low"}, False,
         {"fallback_used": True, "engine_used": "server_fallback", "final_result": "verified"}),
        # 7 Qwen fallback engine_error → fail_safe retake
        ("water", _smol_va("water", []), "[qwen engine_error simulated: not json]", False,
         {"fallback_used": True, "engine_used": "fail_safe", "final_result": "retake_required"}),
        # 8 force_fallback (smol would verify, but forced to qwen)
        ("water", _smol_va("water", ["visible_water", "filled_container"], obj=_CUP),
         {"task": "water", "image_quality": "good", "positive_evidence": ["clear_liquid_visible"],
          "blockers": [], "uncertainty": "low"}, True,
         {"fallback_used": True, "engine_used": "server_fallback"}),
    ]
    print("=== DRY-RUN: mock Smol + mock Qwen → EXISTING Rule Engine / fail-safe ===")
    npass = 0
    for i, (task, msmol, mqwen, force, exp) in enumerate(cases, 1):
        # case4 special: engine_error mock
        if isinstance(msmol, dict) and msmol.get("__engine_error__"):
            # simulate smol engine error by passing None va (engine returns failed)
            def _patched_extract(*a, **k):  # noqa: E306
                return {"va_dict": None, "parse_status": "failed", "engine_error": "simulated_engine_error", "raw_text": ""}
            orig = smol_engine.extract
            smol_engine.extract = _patched_extract
            try:
                out = verify_image_with_vlm_fallback(f"<mock{i}>", task, force_fallback=force, mock_qwen=mqwen)
            finally:
                smol_engine.extract = orig
        else:
            out = verify_image_with_vlm_fallback(f"<mock{i}>", task, force_fallback=force,
                                                 mock_smol=msmol, mock_qwen=mqwen)
        ok = all(out.get(k) == v for k, v in exp.items())
        npass += ok
        print(f" case{i} [{task}] force={force} => final={out['final_result']} engine={out['engine_used']} "
              f"fallback={out['fallback_used']} (expect {exp}) {'OK' if ok else 'MISMATCH:'+json.dumps({k:out.get(k) for k in exp})}")
    print(f"DRY-RUN {npass}/8 pass. NOTE: final_result 는 기존 Rule Engine 또는 fail-safe retake 에서만 나옴.")


def main():
    from prompts import TASKS
    ap = argparse.ArgumentParser(description="SmolVLM local-first + Qwen3B fallback + existing Rule Engine")
    ap.add_argument("--image"); ap.add_argument("--task", choices=TASKS); ap.add_argument("--image-id", default="")
    ap.add_argument("--force-fallback", action="store_true")
    ap.add_argument("--no-qwen", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.dry_run:
        _dry_run(); return
    if not (args.image and args.task):
        ap.error("--image and --task required (or --dry-run)")
    out = verify_image_with_vlm_fallback(args.image, args.task, force_fallback=args.force_fallback,
                                         no_qwen=args.no_qwen, image_id=args.image_id)
    if args.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
