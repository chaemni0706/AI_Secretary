"""Qwen-3B EVIDENCE ENGINE (기존 이미지 판독 엔진 대체용 evidence extractor).

역할: image_path + task → Qwen-3B task-specific prompt → raw output → evidence JSON(parse/normalize).
**Qwen 은 final_result 를 확정하지 않는다.** 최종 판정은 기존 Rule Engine(adapter 경유). 이 파일은 evidence 추출만.

주요 함수:
- run_qwen_evidence_extraction(image_path, task, model_path, mock_output=None) -> raw text (실모델 추론)
- parse_qwen_evidence(raw) -> (evidence_dict, parse_status)  (clean|repaired|failed; 실패→retake 유도)
- extract(image_path, task, mock_output=None) -> {"evidence":..., "qwen_raw_output":..., "qwen_parse_status":...}

runtime: transformers Qwen2_5_VLForConditionalGeneration + AutoProcessor(+ qwen_vl_utils). lazy singleton(최초 1회 로드).
모델 weight 는 git 에 없음. config: qwen3b_runtime_config(QWEN3B_MODEL_PATH/DEVICE/DTYPE/MAX_NEW_TOKENS/TEMPERATURE/DO_SAMPLE).
dry-run: python local_eval/vlm_baseline/qwen3b_evidence_engine.py --dry-run
smoke : python local_eval/vlm_baseline/qwen3b_evidence_engine.py --image <img> --task water [--model-path ...]
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
from qwen3b_runtime_config import load_config  # noqa: E402

DEFAULT_MODEL_PATH = os.environ.get("QWEN3B_MODEL_PATH", "/data/models/Qwen2.5-VL-3B-Instruct-AWQ")

_EVIDENCE_KEYS = ("task", "image_quality", "visible_objects", "visible_actions", "scene_type",
                  "positive_evidence", "negative_evidence", "blockers", "uncertainty", "reason")


# ---------------------------------------------------------------------------
# Qwen2.5-VL runtime — lazy singleton (모델은 최초 1회만 로드, 이후 재사용).
# ---------------------------------------------------------------------------
class _QwenRuntime:
    _instance = None

    def __init__(self, cfg):
        self.cfg = cfg
        self.model = None
        self.processor = None

    @classmethod
    def get(cls, cfg):
        if cls._instance is None or cls._instance.cfg.model_path != cfg.model_path:
            cls._instance = cls(cfg)
        return cls._instance

    def load(self):
        if self.model is not None:
            return
        import torch  # noqa: F401
        from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            self.cfg.model_path, torch_dtype=self.cfg.torch_dtype(), device_map=self.cfg.device).eval()
        self.processor = AutoProcessor.from_pretrained(self.cfg.model_path)

    def generate(self, image_path, prompt):
        import torch
        self.load()
        messages = [{"role": "user", "content": [{"type": "image", "image": f"file://{image_path}"},
                                                  {"type": "text", "text": prompt}]}]
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        try:
            from qwen_vl_utils import process_vision_info
            imgs, vids = process_vision_info(messages)
        except Exception:
            from PIL import Image
            imgs, vids = [Image.open(str(image_path)).convert("RGB")], None
        inputs = self.processor(text=[text], images=imgs, videos=vids, padding=True,
                                return_tensors="pt").to(self.cfg.device)
        gk = {"max_new_tokens": self.cfg.max_new_tokens, "do_sample": self.cfg.do_sample}
        if self.cfg.do_sample:
            gk["temperature"] = self.cfg.temperature
        with torch.no_grad():
            out = self.model.generate(**inputs, **gk)
        trimmed = out[:, inputs["input_ids"].shape[1]:]
        return self.processor.batch_decode(trimmed, skip_special_tokens=True,
                                           clean_up_tokenization_spaces=False)[0].strip()


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
    """(evidence_dict, parse_status). status: clean|repaired|failed.
    JSON 코드블록/앞뒤 설명 섞여도 첫 JSON object 추출. 실패 시 보수적 기본
    (uncertainty=high, image_quality=unknown, blockers=[parse_failed]) → Rule Engine 이 retake 로."""
    obj = _clean(raw)
    status = "clean"
    if obj is None:
        obj = _repair(raw)
        status = "repaired" if obj is not None else "failed"
    if obj is None:
        return ({"task": "", "image_quality": "unknown", "visible_objects": [], "visible_actions": [],
                 "scene_type": "", "positive_evidence": [], "negative_evidence": [],
                 "blockers": ["parse_failed"], "uncertainty": "high", "reason": "parse_failed"}, status)
    ev = {k: obj.get(k, [] if k in ("visible_objects", "visible_actions", "positive_evidence",
                                     "negative_evidence", "blockers") else "") for k in _EVIDENCE_KEYS}
    if not ev.get("image_quality"):
        ev["image_quality"] = "unknown"
    if not ev.get("uncertainty"):
        ev["uncertainty"] = "high"
    return ev, status


def run_qwen_evidence_extraction(image_path, task, model_path=None, mock_output=None):
    """Qwen-3B raw output 반환. mock_output 주면 그대로 반환(dry-run). 아니면 실모델 추론(lazy singleton)."""
    if mock_output is not None:
        return mock_output if isinstance(mock_output, str) else json.dumps(mock_output, ensure_ascii=False)
    cfg = load_config(model_path)
    if not Path(cfg.model_path).exists():
        raise FileNotFoundError(f"model path not found: {cfg.model_path} (set QWEN3B_MODEL_PATH). weight 는 repo 에 없음.")
    rt = _QwenRuntime.get(cfg)
    return rt.generate(image_path, build_prompt(task))


def extract(image_path, task, model_path=None, mock_output=None):
    if task not in TASKS:
        raise ValueError(f"task must be one of {TASKS}")
    # FP=0 안전: 모델 로드/generate 등 엔진 오류는 절대 verified 로 이어지면 안 됨 →
    # engine_error 를 failed evidence(uncertainty high, blockers=[engine_error])로 변환 → Rule Engine 이 retake.
    try:
        raw = run_qwen_evidence_extraction(image_path, task, model_path=model_path, mock_output=mock_output)
        ev, status = parse_qwen_evidence(raw)
    except Exception as exc:  # noqa: BLE001
        raw = f"[engine_error] {type(exc).__name__}: {str(exc)[:300]}"
        ev = {"task": task, "image_quality": "unknown", "visible_objects": [], "visible_actions": [],
              "scene_type": "", "positive_evidence": [], "negative_evidence": [],
              "blockers": ["engine_error"], "uncertainty": "high", "reason": f"engine_error: {type(exc).__name__}"}
        status = "failed"
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
    npass = 0
    for i, (task, mock) in enumerate(_DRY_CASES, 1):
        out = ad.verify(f"<mock_image_{i}>", task, mock_output=mock)
        exp = {1: "verified", 2: "rejected", 3: "rejected|retake_required", 4: "verified",
               5: "rejected", 6: "verified", 7: "retake_required"}[i]
        fr = out["final_result"]
        ok = fr in exp.split("|"); npass += ok
        print(f" case{i} [{task}] blockers={mock.get('blockers')} pos={mock.get('positive_evidence')} unc={mock.get('uncertainty')} "
              f"=> final_result={fr} (expect {exp}) {'OK' if ok else 'MISMATCH'} | engine={out['debug']['engine']} "
              f"rule_engine_fallback={out['debug']['rule_engine_fallback']}")
    print(f"DRY-RUN {npass}/7 pass. NOTE: final_result 는 기존 Rule Engine 산출; Qwen 은 evidence 만.")


def _smoke(image, task, model_path):
    """단일 이미지 실모델 smoke: raw → parsed → adapter/VisionAnalysis 요약 → final_result/rule_reason/fallback."""
    import qwen3b_evidence_adapter as ad
    out = ad.verify(image, task, model_path=model_path)  # 실모델 경로(mock 없음)
    print(json.dumps({
        "image": str(image), "task": task,
        "qwen_raw_output": out["debug"]["qwen_raw_output"],
        "qwen_parse_status": out["debug"]["qwen_parse_status"],
        "parsed_evidence": out["evidence"],
        "mapped_rule_codes": out["evidence"].get("mapped_rule_codes"),
        "final_result": out["final_result"],
        "rule_reason": out["rule_reason"],
        "rule_trace": out["rule_trace"],
        "rule_engine_fallback": out["debug"]["rule_engine_fallback"],
    }, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(description="Qwen-3B evidence engine (evidence extractor; NOT final decider)")
    ap.add_argument("--image"); ap.add_argument("--task", choices=TASKS)
    ap.add_argument("--model-path", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--evidence-only", action="store_true", help="evidence JSON 만 출력(Rule Engine 미호출)")
    args = ap.parse_args()
    if args.dry_run:
        _dry_run(); return
    if not (args.image and args.task):
        ap.error("--image and --task required (or use --dry-run)")
    if args.evidence_only:
        print(json.dumps(extract(args.image, args.task, model_path=args.model_path), ensure_ascii=False, indent=2))
    else:
        _smoke(args.image, args.task, args.model_path)


if __name__ == "__main__":
    main()
