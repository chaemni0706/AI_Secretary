"""Qwen-3B Unified Verification Baseline (VLM task 정리용 skeleton).

Camera Image + task → Qwen2.5-VL-3B[-AWQ] → verified/rejected/retake_required (JSON).
이 baseline 에서는 Qwen-3B 하나가 local/fallback 구분 없이 전체 verification 을 수행한다(임시).

원칙:
- VLM 출력 JSON(result 포함)을 받되, **FP=0 우선**으로 normalize: 애매/불확실→retake_required, 부정근거→rejected.
- **모델 weight 는 git 에 포함하지 않는다.** 모델 경로는 config(환경변수 QWEN3B_MODEL_PATH 또는 --model-path)로 분리.
- 최종 제품 구조 아님. YOLO 전환 예정.

주: 이 파일은 스켈레톤이다. 실제 Qwen2.5-VL 추론(transformers/vLLM)은 런타임 환경에 맞춰 _load_model/_generate 를 채운다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from prompts import build_prompt, TASKS  # local_eval/vlm_baseline/prompts.py

# 모델 경로는 config 로만(weight 는 repo 에 없음).
DEFAULT_MODEL_PATH = os.environ.get(
    "QWEN3B_MODEL_PATH", "/data/models/Qwen2.5-VL-3B-Instruct-AWQ")

RESULTS = ("verified", "rejected", "retake_required")


@dataclass
class VerifyResult:
    task: str
    result: str = "retake_required"
    positive_evidence: list = field(default_factory=list)
    negative_evidence: list = field(default_factory=list)
    uncertainty: str = "high"
    reason: str = ""

    def to_json(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# parsing / normalization (FP=0 우선)
# ---------------------------------------------------------------------------
def _extract_json(text: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    for cand in (m.group(0), re.sub(r",\s*(\}|\])", r"\1", m.group(0))):
        try:
            return json.loads(cand)
        except Exception:
            continue
    return None


def normalize_result(task: str, obj: Optional[dict], image_quality: str = "good") -> VerifyResult:
    """VLM 출력 → FP=0 우선 normalize.
    우선순위: 1) parse 실패/이미지 불량 → retake  2) negative blocker → rejected
             3) uncertainty high / positive 부족 → retake  4) positive 충분 → verified."""
    if obj is None:
        return VerifyResult(task, "retake_required", uncertainty="high", reason="parse_failed_or_no_output")
    pos = obj.get("positive_evidence") or []
    neg = obj.get("negative_evidence") or []
    unc = str(obj.get("uncertainty", "high")).lower()
    raw_result = str(obj.get("result", "")).lower()
    reason = str(obj.get("reason", ""))
    iq = str(obj.get("image_quality", image_quality)).lower()

    if iq in ("poor", "unusable"):
        return VerifyResult(task, "retake_required", pos, neg, unc, reason or "image_quality_poor")
    if neg:  # 부정 근거(blocker) 존재 → reject (FP 방어)
        return VerifyResult(task, "rejected", pos, neg, unc, reason or "negative_blocker_present")
    if unc == "high" or not pos:  # 불확실 또는 positive 근거 부족 → retake
        return VerifyResult(task, "retake_required", pos, neg, unc, reason or "uncertain_or_insufficient_evidence")
    # positive 충분 + blocker 없음 + 불확실 낮음
    result = "verified" if raw_result in ("", "verified") else (raw_result if raw_result in RESULTS else "verified")
    return VerifyResult(task, result, pos, neg, unc, reason or "positive_evidence_sufficient")


# ---------------------------------------------------------------------------
# model call (skeleton) — 런타임 환경에 맞춰 채움. weight 는 config 경로에서 로드.
# ---------------------------------------------------------------------------
class Qwen3BVerifier:
    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, device: str = "cuda"):
        self.model_path = model_path
        self.device = device
        self._model = None
        self._proc = None

    def _load(self):
        """실제 로드는 런타임에서 구현(transformers Qwen2_5_VLForConditionalGeneration + AutoProcessor,
        또는 vLLM). 여기서는 skeleton — 모델 파일이 config 경로에 있어야 함."""
        raise NotImplementedError(
            f"load Qwen2.5-VL-3B from '{self.model_path}' (transformers/vLLM). weight 는 repo 에 없음; "
            f"QWEN3B_MODEL_PATH 로 지정.")

    def _generate(self, image_path: Path, prompt: str) -> str:
        raise NotImplementedError("run VLM generate → raw text (JSON). 런타임 구현.")

    def verify(self, image_path: str, task: str) -> dict:
        if task not in TASKS:
            raise ValueError(f"task must be one of {TASKS}")
        prompt = build_prompt(task)
        if self._model is None:
            self._load()  # skeleton: NotImplementedError until 런타임 구현
        raw = self._generate(Path(image_path), prompt)
        obj = _extract_json(raw)
        return normalize_result(task, obj).to_json()


def main():
    ap = argparse.ArgumentParser(description="Qwen-3B unified verification baseline (skeleton)")
    ap.add_argument("--image", required=True)
    ap.add_argument("--task", required=True, choices=TASKS)
    ap.add_argument("--model-path", default=DEFAULT_MODEL_PATH,
                    help="Qwen2.5-VL-3B 경로(config). weight 는 repo 에 없음.")
    ap.add_argument("--dry-run", action="store_true", help="모델 호출 없이 prompt/normalize 경로만 확인")
    args = ap.parse_args()
    if args.dry_run:
        # 모델 없이 normalize 로직 데모(빈 출력 → retake_required)
        print(json.dumps(normalize_result(args.task, None).to_json(), ensure_ascii=False, indent=2))
        return
    v = Qwen3BVerifier(args.model_path)
    print(json.dumps(v.verify(args.image, args.task), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
