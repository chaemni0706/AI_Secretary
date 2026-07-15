"""Robust water PASS/FAIL verdict parsing for the Qwen VLM pipeline.

VLM(또는 그 뒤의 Rule Engine)이 내놓는 판정 출력은 형태가 제각각이다.
- 문자열: "PASS" / "FAIL", "true" / "false", "물 있음" / "물 없음",
          "인증 가능" / "인증 불가", "verified" / "rejected" / "retake_required"
- dict:   {"result": "verified"} / {"label": "PASS"} / {"verdict": true} / {"pass": false}
- VisionAnalysis(또는 그 dict): water_visual_evidence 등 → Rule Engine으로 최종 판정

이 모듈은 그 어떤 형태가 와도 하나의 표준 Verdict(PASS/FAIL/BORDERLINE/UNKNOWN)로
정규화한다. MVP 매핑: verified → PASS, rejected/retake_required → FAIL.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

PASS = "PASS"
FAIL = "FAIL"
BORDERLINE = "BORDERLINE"
UNKNOWN = "UNKNOWN"


@dataclass
class Verdict:
    label: str
    confidence: float | None = None
    reason: str = ""
    source: str = ""  # "text" | "mapping" | "rule_engine"
    raw: Any = field(default=None, repr=False)


# Rule Engine 결과 → PASS/FAIL 매핑 (MVP)
RESULT_LABEL_MAP = {
    "verified": PASS,
    "rejected": FAIL,
    "retake_required": FAIL,
}

# 문자열 판정 토큰. FAIL 계열을 먼저 검사한다.
# ("인증 불가능"이 "가능"을 포함하는 등 부분 문자열 충돌을 피하기 위함)
_FAIL_TOKENS = (
    "인증 불가", "인증불가", "불가능", "불가",
    "물 없음", "물없음", "물이 없", "없음", "없다",
    "빈 컵", "빈컵", "empty",
    "실패", "미인증", "거절",
    "retake", "reject", "not pass", "not verified", "no water",
)
_PASS_TOKENS = (
    "인증 가능", "인증가능", "가능",
    "물 있음", "물있음", "물이 있", "물이 담", "있음", "있다",
    "통과", "성공", "인정",
    "verified", "pass", "yes",
)

# 정확한 단독 토큰(대소문자 무시). 위 substring 검사보다 우선.
_EXACT_MAP = {
    "pass": PASS, "fail": FAIL,
    "true": PASS, "false": FAIL,
    "yes": PASS, "no": FAIL,
    "verified": PASS, "rejected": FAIL, "retake_required": BORDERLINE,
    "o": PASS, "x": FAIL,
}


def _clean(text: str) -> str:
    return text.strip().strip(".!?\"'` \t\n\r").strip()


def parse_text_verdict(text: str) -> Verdict:
    """단순 문자열 판정을 PASS/FAIL/BORDERLINE/UNKNOWN으로 파싱."""
    original = text
    cleaned = _clean(text)
    low = cleaned.lower()

    # 1) 정확한 단독 토큰
    if low in _EXACT_MAP:
        return Verdict(_EXACT_MAP[low], reason=f"exact token '{cleaned}'", source="text", raw=original)

    # 2) retake/borderline 우선 감지 (재촬영 요청)
    if "retake" in low or "재촬영" in cleaned:
        return Verdict(BORDERLINE, reason="retake requested", source="text", raw=original)

    # 3) FAIL 토큰 먼저 (부분 문자열 충돌 방지)
    for tok in _FAIL_TOKENS:
        if tok in low or tok in cleaned:
            return Verdict(FAIL, reason=f"fail token '{tok}'", source="text", raw=original)

    # 4) PASS 토큰
    for tok in _PASS_TOKENS:
        if tok in low or tok in cleaned:
            return Verdict(PASS, reason=f"pass token '{tok}'", source="text", raw=original)

    return Verdict(UNKNOWN, reason=f"no verdict token in '{cleaned}'", source="text", raw=original)


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = parse_text_verdict(value)
        if v.label == PASS:
            return True
        if v.label == FAIL:
            return False
    return None


def _extract_confidence(payload: dict) -> float | None:
    for key in ("confidence", "score", "prob", "probability"):
        if key in payload:
            try:
                val = float(payload[key])
            except (TypeError, ValueError):
                continue
            # 0..100 스케일이면 0..1로 축소
            return val / 100.0 if val > 1.0 else val
    return None


def parse_dict_verdict(payload: dict) -> Verdict:
    """dict 판정. verdict/label/result/pass 등 다양한 키를 지원."""
    conf = _extract_confidence(payload)

    # water_visual_evidence가 있으면 (정규화된) VisionAnalysis로 간주 → Rule Engine 위임
    if "water_visual_evidence" in payload:
        return verdict_from_vision_analysis(payload, confidence=conf)

    for key in ("verdict", "label", "result", "decision", "status", "answer"):
        if key in payload and payload[key] is not None:
            v = normalize_verdict(payload[key])
            v.confidence = conf if v.confidence is None else v.confidence
            v.source = "mapping"
            return v

    for key in ("pass", "passed", "is_water", "water", "has_water", "ok"):
        if key in payload:
            b = _coerce_bool(payload[key])
            if b is not None:
                return Verdict(PASS if b else FAIL, confidence=conf,
                               reason=f"bool field '{key}'={payload[key]}", source="mapping", raw=payload)

    return Verdict(UNKNOWN, confidence=conf, reason="no verdict key in dict", source="mapping", raw=payload)


def verdict_from_vision_analysis(analysis: Any, confidence: float | None = None) -> Verdict:
    """VisionAnalysis(또는 dict)를 Rule Engine에 통과시켜 최종 PASS/FAIL 산출."""
    # 지연 import: torch 등 무거운 의존성 없이 pydantic/yaml만 사용
    from backend.database.schema.image_verification_schema import (
        ImageVerificationContext,
        VisionAnalysis,
    )
    from backend.services.image_verification_rule_engine import evaluate_image_verification

    if isinstance(analysis, VisionAnalysis):
        va = analysis
    else:
        va = VisionAnalysis.model_validate(analysis)

    data = evaluate_image_verification("water", va, ImageVerificationContext())
    label = RESULT_LABEL_MAP.get(data.result, UNKNOWN)
    reasons = "; ".join(e.message for e in data.rule_evidence) or "no rule evidence"
    return Verdict(
        label,
        confidence=confidence if confidence is not None else data.score / 100.0,
        reason=f"[{data.result}] {reasons}",
        source="rule_engine",
        raw=data,
    )


def normalize_verdict(model_output: Any) -> Verdict:
    """어떤 형태의 모델 출력이든 표준 Verdict로 정규화하는 진입점."""
    if isinstance(model_output, Verdict):
        return model_output
    if isinstance(model_output, bool):
        return Verdict(PASS if model_output else FAIL, reason=f"bool {model_output}", source="mapping")
    if isinstance(model_output, (int, float)):
        # 숫자 단독은 신뢰도가 아니라 boolean-ish 값으로 취급 (0=False)
        return Verdict(PASS if model_output else FAIL, reason=f"number {model_output}", source="mapping")
    if isinstance(model_output, dict):
        return parse_dict_verdict(model_output)
    if isinstance(model_output, str):
        return parse_text_verdict(model_output)
    # pydantic VisionAnalysis 등
    if hasattr(model_output, "water_visual_evidence"):
        return verdict_from_vision_analysis(model_output)
    return Verdict(UNKNOWN, reason=f"unsupported type {type(model_output).__name__}", raw=model_output)


def is_pass(model_output: Any) -> bool:
    """편의 함수: 최종 라벨이 PASS이면 True."""
    return normalize_verdict(model_output).label == PASS
