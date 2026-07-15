"""Conservative FP=0 GUARD (Rule Engine core 미수정; adapter/verifier 레이어 post-gate).

배경: fallback VLM(A.X/Qwen)은 빈 잔·색깔 음료(녹차/주스)·애매한 용기를 종종 '물'로 오인해 Rule Engine 이
verified 를 낸다(mini_probe48 water FP). 프롬프트로는 해소 안 됨.

핵심 관찰(mini_probe48 A.X raw 분석):
- A.X 의 구조화 필드(positive_evidence/negative_evidence)는 **신뢰 불가**(vocabulary-dump):
  PASS 물에도 negative_evidence 에 'colored_beverage'/'opaque_container' 를 남발 → 이 필드 스캔 시 PASS 오차단.
- 반면 **reason 자유텍스트는 정확**: 빈 잔→"the glass is empty", 녹차→"yellowish...not colorless...not water",
  PASS→"clear...colorless...waterline" / "정수기...물이 담겨".
→ 따라서 guard 는 **reason(+scene/objects/actions/positive/blockers) 만 스캔하고 negative_evidence 는 제외**한다.

원칙:
- verified 만 차단 대상(rejected/retake 는 FP 무관 → 그대로 통과). FP=0 최우선.
- Rule Engine core 절대 미수정. 이 함수는 최종 판정 '이후'의 보수적 게이트.

guard_final_result(task, final_result, evidence, raw_text) -> (result, guard_reason)
guard_reason 이 비어있지 않으면 강등 발생.
"""
from __future__ import annotations

# 물이 아님 / 판별 불가 신호(reason 자유텍스트 기준). '색이 있는 액체' + '빈 용기' + '불투명/불명'.
_WATER_NEG = (
    # 빈 용기
    "empty", "no liquid", "no water", "without water", "no visible liquid", "appears empty",
    "looks empty", "seems empty", "nothing inside", "빈 ", "빈잔", "비어", "비었", "물이 없", "액체가 없",
    # 물이 아님 / 무색이 아님
    "not water", "not colorless", "is not water", "not colourless", "물이 아니", "물은 아니",
    # 색이 있는 액체 = 음료
    "yellow", "yellowish", "green", "greenish", "brown", "orange", "amber", "golden", "pink",
    "purple", "reddish", "dark liquid", "colored liquid", "coloured liquid", "tinted",
    "노란", "노랑", "녹색", "초록", "갈색", "주황", "분홍", "붉",
    "tea", "green tea", "juice", "주스", "coffee", "커피", "latte", "milk", "우유",
    "soda", "탄산", "cola", "콜라", "wine", "와인", "beer", "맥주", "soju", "소주",
    "smoothie", "cocktail", "syrup", "cider", "sports drink",
    # 불투명 / 판별 불가
    "opaque", "불투명", "cannot see inside", "can't see inside", "unable to see", "hard to tell",
)

# 운동: 실제 동작 없이 장비/포즈/셀카/정지만 → 물이 아니라 '동작 부재'가 disqualifier.
_EX_NEG = (
    "no exercise", "not exercising", "no action", "no movement", "no active", "not performing",
    "equipment only", "장비만", "기구만", "folded", "stored", "접힌", "보관",
    "sitting", "seated", "resting", "앉아", "쉬고", "selfie", "셀카", "just posing", "posing for",
    "standing still", "about to", "preparing to", "empty gym", "background only", "no person",
)


def _blob(evidence, raw_text):
    """reason + 신뢰 가능한 필드 값만 결합. negative_evidence 는 vocabulary-dump 라 **제외**.
    raw_text(모델 JSON) 도 schema 키('uncertainty' 등)가 섞여 오탐 유발 → 미사용."""
    ev = evidence or {}
    parts = [str(ev.get("reason", "")), str(ev.get("scene_type", ""))]
    for k in ("positive_evidence", "blockers", "visible_objects", "visible_actions"):
        v = ev.get(k) or []
        if isinstance(v, (list, tuple)):
            parts.extend(str(x) for x in v)
        else:
            parts.append(str(v))
    return " ".join(parts).lower()


def guard_final_result(task, final_result, evidence, raw_text, enabled=True):
    """verified 를 보수적으로 재검증. 위험신호면 retake_required 로 강등. 반환 (result, guard_reason)."""
    if not enabled or final_result != "verified":
        return final_result, ""
    ev = evidence or {}
    blob = _blob(ev, raw_text)
    unc = str(ev.get("uncertainty", "")).lower()
    iq = str(ev.get("image_quality", "")).lower()

    # 공통: verified 는 low uncertainty + 정상 품질에서만
    if unc and unc != "low":
        return "retake_required", f"guard:{task}:uncertainty_{unc}"
    if iq in ("poor", "unusable"):
        return "retake_required", f"guard:{task}:image_quality_{iq}"

    if task == "water":
        hit = next((k for k in _WATER_NEG if k in blob), None)
        if hit:
            return "retake_required", f"guard:water:neg[{hit.strip()}]"
    elif task == "exercise":
        hit = next((k for k in _EX_NEG if k in blob), None)
        if hit:
            return "retake_required", f"guard:exercise:neg[{hit.strip()}]"
    # study 는 mini_probe FP=0 → guard 미적용.
    return final_result, ""
