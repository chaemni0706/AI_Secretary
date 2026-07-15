"""[DEPRECATED / ROLE CHANGED] Qwen-3B unified verifier.

역할 변경(2026-07-10): 이 baseline 은 더 이상 Qwen 이 verified/rejected 를 **직접 결정**하지 않는다.
Qwen-3B 는 **기존 이미지 판독 엔진을 대체하는 evidence extractor** 이고, 최종 판정은 **기존 Rule Engine** 이 한다.

→ 사용:
  - evidence 추출: `qwen3b_evidence_engine.extract(image_path, task)`
  - evidence→기존 Rule Engine→final_result: `qwen3b_evidence_adapter.verify(image_path, task)`

이 파일은 하위호환 shim 으로 adapter.verify 에 위임한다(직접 판정 로직 없음).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import qwen3b_evidence_adapter as adapter  # noqa: E402
from prompts import TASKS  # noqa: E402


def verify(image_path: str, task: str, mock_output=None) -> dict:
    """[deprecated name] → adapter.verify. final_result 는 기존 Rule Engine 산출."""
    return adapter.verify(image_path, task, mock_output=mock_output)


def main():
    ap = argparse.ArgumentParser(description="[DEPRECATED] delegates to qwen3b_evidence_adapter.verify")
    ap.add_argument("--image"); ap.add_argument("--task", choices=TASKS)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.dry_run:
        import qwen3b_evidence_engine as engine
        engine._dry_run(); return
    if not (args.image and args.task):
        ap.error("--image and --task required (or --dry-run). 참고: evidence 엔진은 qwen3b_evidence_engine.py")
    print(json.dumps(verify(args.image, args.task), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
