"""Qwen-3B EVIDENCE ENGINE (기존 이미지 판독 엔진 대체용 evidence extractor).

역할: image_path + task → Qwen-3B task-specific prompt → raw output → evidence JSON(parse/normalize).
**Qwen 은 final_result 를 확정하지 않는다.** 최종 판정은 기존 Rule Engine(adapter 경유). 이 파일은 evidence 추출만.

주요 함수:
- run_qwen_evidence_extraction(image_path, task, model_path, mock_output=None) -> raw text
- parse_qwen_evidence(raw) -> (evidence_dict, parse_status)
- extract(image_path, task, mock_output=None) -> {"evidence":..., "qwen_raw_output":..., "qwen_parse_status":...}

모델 weight 는 git 에 없음. 경로는 config(QWEN3B_MODEL_PATH). 실제 로드/generate 는 skeleton(런타임 구현).
dry-run: python local_eval/vlm_baseline/qwen3b_evidence_engine.py --dry-run  (mock → engine → adapter → Rule Engine)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from prompts import build_prompt, TASKS  # noqa: E402

DEFAULT_MODEL_PATH = os.environ.get("QWEN3B_MODEL_PATH", "/data/models/Qwen2.5-VL-3B-Instruct-AWQ")

_EVIDENCE_KEYS = ("task", "image_quality", "visible_objects", "visible_actions", "scene_type",
                  "positive_evidence", "negative_evidence", "blockers", "uncertainty", "reason")


def _clean(raw: str):
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _repair(raw: str):
    m = re.search(r"\{.*", raw or "", re.S)
    if not m:
        return None
    s = re.sub(r",\s*(\}|\])", r"\1", m.group(0))
    s = s + "]" * max(0, s.count("[") - s.count("]")) + "}" * max(0, s.count("{") - s.count("}"))
    try:
        return json.loads(s)
    except Exception:
        return None


def parse_qwen_evidence(raw: str):
    """(evidence_dict, parse_status). status: clean|repaired|failed. 실패 시 보수적 기본(uncertainty high)."""
    obj = _clean(raw)
    status = "clean"
    if obj is None:
        obj = _repair(raw)
        status = "repaired" if obj is not None else "failed"
    if obj is None:
        return ({"task": "", "image_quality": "unknown", "visible_objects": [], "visible_actions": [],
                 "scene_type": "", "positive_evidence": [], "negative_evidence": [], "blockers": [],
                 "uncertainty": "high", "reason": "parse_failed"}, status)
    ev = {k: obj.get(k, [] if k in ("visible_objects", "visible_actions", "positive_evidence",
                                     "negative_evidence", "blockers") else "") for k in _EVIDENCE_KEYS}
    if not ev.get("image_quality"):
        ev["image_quality"] = "unknown"
    if not ev.get("uncertainty"):
        ev["uncertainty"] = "high"
    return ev, status


def run_qwen_evidence_extraction(image_path, task, model_path=DEFAULT_MODEL_PATH, mock_output=None):
    """Qwen-3B raw output 반환. mock_output 주면 그대로 반환(dry-run). 실제 추론은 skeleton."""
    if mock_output is not None:
        return mock_output if isinstance(mock_output, str) else json.dumps(mock_output, ensure_ascii=False)
    raise NotImplementedError(
        f"Load Qwen2.5-VL-3B from '{model_path}' and run generate on {image_path} with prompt=build_prompt('{task}'). "
        f"Weight 는 repo 에 없음(QWEN3B_MODEL_PATH). 런타임에서 구현.")


def extract(image_path, task, model_path=DEFAULT_MODEL_PATH, mock_output=None):
    if task not in TASKS:
        raise ValueError(f"task must be one of {TASKS}")
    _ = build_prompt(task)  # prompt 생성(런타임에서 모델에 전달)
    raw = run_qwen_evidence_extraction(image_path, task, model_path, mock_output=mock_output)
    ev, status = parse_qwen_evidence(raw)
    ev["task"] = ev.get("task") or task
    return {"evidence": ev, "qwen_raw_output": raw, "qwen_parse_status": status}


# --------------------------------------------------------------------------- dry-run
_DRY_CASES = [
    ("water", {"task": "water", "image_quality": "good", "positive_evidence": ["clear_liquid_visible", "bottle_visible"],
               "negative_evidence": [], "blockers": [], "uncertainty": "low", "reason": "clear liquid in transparent bottle"}),
    ("water", {"task": "water", "image_quality": "good", "positive_evidence": ["bottle_visible"],
               "negative_evidence": [], "blockers": ["empty_bottle"], "uncertainty": "low", "reason": "empty bottle"}),
    ("study", {"task": "study", "image_quality": "good", "positive_evidence": [],
               "negative_evidence": [], "blockers": ["laptop_only"], "uncertainty": "medium", "reason": "laptop only, no study content"}),
    ("study", {"task": "study", "image_quality": "good", "positive_evidence": ["open_book", "study_document"],
               "negative_evidence": [], "blockers": [], "uncertainty": "low", "reason": "open textbook + document"}),
    ("exercise", {"task": "exercise", "image_quality": "good", "positive_evidence": [],
                  "negative_evidence": [], "blockers": ["equipment_only"], "uncertainty": "low", "reason": "dumbbells only, no action"}),
    ("exercise", {"task": "exercise", "image_quality": "good", "positive_evidence": ["person_exercising", "workout_action"],
                  "negative_evidence": [], "blockers": [], "uncertainty": "low", "reason": "person doing exercise"}),
    ("water", {"task": "water", "image_quality": "good", "positive_evidence": ["clear_liquid_visible"],
               "negative_evidence": [], "blockers": [], "uncertainty": "high", "reason": "liquid maybe water, unsure"}),
]


def _dry_run():
    import qwen3b_evidence_adapter as ad
    print("=== DRY-RUN: mock Qwen → engine.parse → adapter → EXISTING Rule Engine → final_result ===")
    for i, (task, mock) in enumerate(_DRY_CASES, 1):
        out = ad.verify(f"<mock_image_{i}>", task, mock_output=mock)
        exp = {1: "verified", 2: "rejected", 3: "rejected|retake_required", 4: "verified",
               5: "rejected", 6: "verified", 7: "retake_required"}[i]
        fr = out["final_result"]
        ok = fr in exp.split("|")
        print(f" case{i} [{task}] blockers={mock.get('blockers')} pos={mock.get('positive_evidence')} unc={mock.get('uncertainty')} "
              f"=> final_result={fr} (expect {exp}) {'OK' if ok else 'MISMATCH'} | engine={out['debug']['engine']} rule_evidence={[e for e in out['rule_trace'][:3]]}")
    print("NOTE: final_result 는 기존 Rule Engine 산출. Qwen 은 evidence 만.")


def main():
    ap = argparse.ArgumentParser(description="Qwen-3B evidence engine (evidence extractor; NOT final decider)")
    ap.add_argument("--image"); ap.add_argument("--task", choices=TASKS)
    ap.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.dry_run:
        _dry_run(); return
    if not (args.image and args.task):
        ap.error("--image and --task required (or use --dry-run)")
    print(json.dumps(extract(args.image, args.task, args.model_path), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
