"""Server Fallback VLM EVIDENCE ENGINE (pluggable, 후보 공정비교용).

역할: image_path + task → 선택된 server VLM → raw output → evidence JSON. **final_result 미결정.**
최종 판정은 기존 Rule Engine(qwen3b_evidence_adapter 의 to_existing_rule_input + run_existing_rule_engine 재사용).

같은 interface 로 여러 후보(qwen25_3b / ax_4_0_vl_light / qwen25_7b ...) 를 교체 로드한다.
parsing/보수화 로직은 qwen3b_evidence_engine.parse_qwen_evidence 재사용(모델 무관).

FP=0 안전: 모델 로드/generate 오류는 절대 verified 로 이어지면 안 됨 → engine_error 를
failed evidence(uncertainty=high, blockers=[engine_error]) 로 변환 → Rule Engine 이 retake.

CLI:
  smoke : python server_vlm_evidence_engine.py --model ax_4_0_vl_light --image <img> --task water
  evidence-only: ... --evidence-only
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from prompts import build_prompt, TASKS               # noqa: E402
import qwen3b_evidence_engine as qe                    # parse_qwen_evidence 재사용  # noqa: E402
import server_vlm_model_registry as registry          # noqa: E402


# --------------------------------------------------------------------------- runtime
class _Runtime:
    """model_key 별 lazy singleton. 후보 교체 시 이전 모델 GPU 메모리 해제."""
    _inst = None

    def __init__(self, spec):
        self.spec = spec
        self.model = None
        self.processor = None
        self.load_error = ""

    @classmethod
    def get(cls, spec):
        if cls._inst is None or cls._inst.spec["model_path"] != spec["model_path"]:
            if cls._inst is not None:
                cls._inst._free()
            cls._inst = cls(spec)
        return cls._inst

    def _free(self):
        try:
            import torch
            del self.model
            self.model = None
            torch.cuda.empty_cache()
        except Exception:
            pass

    def load(self):
        if self.model is not None or self.load_error:
            return
        spec = self.spec
        if not Path(spec["model_path"]).exists():
            self.load_error = f"model path not found: {spec['model_path']} (weight repo 미포함/미다운로드)"
            return
        try:
            import torch
            dtype = getattr(torch, spec.get("dtype", "bfloat16"))
            loader = spec["loader"]
            trc = bool(spec.get("trust_remote_code"))
            if loader == "qwen2_5_vl":
                from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
                self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                    spec["model_path"], torch_dtype=dtype, device_map="cuda").eval()
                self.processor = AutoProcessor.from_pretrained(spec["model_path"])
            elif loader == "qwen3_vl":
                from transformers import AutoModelForImageTextToText, AutoProcessor
                self.model = AutoModelForImageTextToText.from_pretrained(
                    spec["model_path"], torch_dtype=dtype, device_map="cuda").eval()
                self.processor = AutoProcessor.from_pretrained(spec["model_path"])
            elif loader == "auto_trust":
                from transformers import AutoModelForCausalLM, AutoProcessor
                self.model = AutoModelForCausalLM.from_pretrained(
                    spec["model_path"], torch_dtype=dtype, device_map="cuda",
                    trust_remote_code=trc).eval()
                self.processor = AutoProcessor.from_pretrained(spec["model_path"], trust_remote_code=trc)
            else:
                self.load_error = f"unknown loader={loader}"
        except Exception as exc:  # noqa: BLE001
            self.load_error = f"load_failed: {type(exc).__name__}: {str(exc)[:300]}"

    def generate(self, image_path, prompt, max_new_tokens=256):
        import torch
        self.load()
        if self.load_error:
            raise RuntimeError(self.load_error)
        messages = [{"role": "user", "content": [
            {"type": "image", "image": f"file://{image_path}"},
            {"type": "text", "text": prompt}]}]
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        # image inputs: qwen_vl_utils 우선, 실패 시 PIL fallback
        try:
            from qwen_vl_utils import process_vision_info
            imgs, vids = process_vision_info(messages)
        except Exception:
            from PIL import Image
            imgs, vids = [Image.open(str(image_path)).convert("RGB")], None
        inputs = self.processor(text=[text], images=imgs, videos=vids, return_tensors="pt").to("cuda")
        # use_cache=True 강제: A.X-4.0-VL 등 일부 모델은 generation_config.use_cache=false 로 저장되어
        # 있어(디코드마다 KV 재계산 → O(n²), vision token 수천 개면 이미지당 수 분) 반드시 override.
        with torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False, use_cache=True)
        trimmed = out[:, inputs["input_ids"].shape[1]:]
        return self.processor.batch_decode(trimmed, skip_special_tokens=True,
                                           clean_up_tokenization_spaces=False)[0].strip()


# --------------------------------------------------------------------------- public
def extract(image_path, task, model_key, mock_output=None, max_new_tokens=256):
    """server VLM evidence 추출. 반환: {evidence, raw_output, parse_status, latency_ms, model_key}."""
    if task not in TASKS:
        raise ValueError(f"task must be one of {TASKS}")
    t0 = time.time()
    try:
        if mock_output is not None:
            raw = mock_output if isinstance(mock_output, str) else json.dumps(mock_output, ensure_ascii=False)
        else:
            spec = registry.get(model_key)
            rt = _Runtime.get(spec)
            raw = rt.generate(image_path, build_prompt(task), max_new_tokens=max_new_tokens)
        ev, status = qe.parse_qwen_evidence(raw)
    except Exception as exc:  # noqa: BLE001
        raw = f"[engine_error] {type(exc).__name__}: {str(exc)[:300]}"
        ev = {"task": task, "image_quality": "unknown", "visible_objects": [], "visible_actions": [],
              "scene_type": "", "positive_evidence": [], "negative_evidence": [],
              "blockers": ["engine_error"], "uncertainty": "high", "reason": f"engine_error: {type(exc).__name__}"}
        status = "failed"
    ev["task"] = ev.get("task") or task
    return {"evidence": ev, "raw_output": raw, "parse_status": status,
            "latency_ms": (time.time() - t0) * 1000.0, "model_key": model_key}


def verify(image_path, task, model_key, mock_output=None, guard=True):
    """server VLM evidence → 기존 Rule Engine(qwen adapter 재사용) → FP guard → final_result 호환 output."""
    import qwen3b_evidence_adapter as qa
    import vlm_fp_guard as fpg
    er = extract(image_path, task, model_key, mock_output=mock_output)
    ev = er["evidence"]
    rule_input = qa.to_existing_rule_input({"evidence": ev}, task)
    rule_out = qa.run_existing_rule_engine(rule_input)
    # 보수적 FP=0 guard: Rule Engine 이 verified 를 내도 raw/evidence 위험신호면 retake 로 강등(core 미수정).
    guarded, guard_reason = fpg.guard_final_result(task, rule_out["result"], ev, er["raw_output"], enabled=guard)
    final_reason = rule_out["rule_reason"] if not guard_reason else f"{rule_out['rule_reason']} | {guard_reason}"
    return {
        "task": task,
        "final_result": guarded,
        "rule_engine_result": rule_out["result"],
        "guard_reason": guard_reason,
        "rule_reason": final_reason,
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
        "debug": {
            "engine": f"server:{model_key}",
            "raw_output": er["raw_output"],
            "parse_status": er["parse_status"],
            "latency_ms": er["latency_ms"],
            "rule_engine_fallback": rule_out.get("_fallback", False),
        },
    }


def main():
    ap = argparse.ArgumentParser(description="Server fallback VLM evidence engine (evidence extractor; NOT final decider)")
    ap.add_argument("--model", required=True, help="registry key (e.g. ax_4_0_vl_light, qwen25_3b)")
    ap.add_argument("--image"); ap.add_argument("--task", choices=TASKS)
    ap.add_argument("--evidence-only", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        print(json.dumps({k: registry.get(k)["available"] for k in registry.REGISTRY}, indent=2)); return
    if not (args.image and args.task):
        ap.error("--image and --task required")
    if args.evidence_only:
        print(json.dumps(extract(args.image, args.task, args.model), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(verify(args.image, args.task, args.model), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
