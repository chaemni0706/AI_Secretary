"""Secondary review queue service (DB-backed) for VLM-based image verification.

배경: water task 의 `verified` 는 외관만으로 확정 불가한 케이스(오염수/변기물/맥주+물/borderline)가 있어
자동 최종 성공으로 처리하지 않고 `review_required=true` 로 표시한다(→ [image_verification_service.apply_secondary_review_policy]).
이 서비스는 그 결과를 **DB 운영 큐(pending → approved/rejected/needs_retake)** 로 영속화/추적한다.

원칙:
- Rule Engine core / final_result enum 미변경. review_status 는 별개 운영 상태.
- 저장소: SQLite ``image_verification_reviews`` 테이블(local_schema.sql, ledger 와 동일 append-only 방식).
- 최종 성공 판단은 final_result 가 아니라 review_status(approved) 를 우선한다.
- 함수는 FastAPI 의존성으로 주입된 ``Session`` 을 받는다(기존 repository/service 패턴과 동일).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.database import secondary_review_repository as repo
from backend.database.image_verification_review_models import ImageVerificationReviewRow
from backend.database.schema.image_verification_schema import (
    ImageVerificationData,
    ReviewDecision,
    ReviewRecord,
    RuleEvidence,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _evidence_to_json(evidence: list[RuleEvidence]) -> Optional[str]:
    if not evidence:
        return None
    return json.dumps([e.model_dump() for e in evidence], ensure_ascii=False)


def _to_record(row: ImageVerificationReviewRow) -> ReviewRecord:
    evidence: list[RuleEvidence] = []
    if row.rule_evidence_json:
        try:
            evidence = [RuleEvidence(**e) for e in json.loads(row.rule_evidence_json)]
        except (ValueError, TypeError):
            evidence = []
    return ReviewRecord(
        id=row.id,
        verification_type=row.verification_type,
        result=row.result,
        score=row.score,
        review_required=True,
        review_reason=row.review_reason,
        review_status=row.review_status,
        review_decision=row.review_decision,
        review_note=row.review_note,
        reviewer_id=row.reviewer_id,
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
        rule_evidence=evidence,
    )


def register(db: Session, data: ImageVerificationData, now: Optional[str] = None) -> str:
    """review_required 인 결과를 pending 으로 DB 큐에 등록하고 record id 를 반환."""
    if not data.review_required:
        raise ValueError("review_required=false 인 결과는 review queue 에 등록하지 않는다.")
    rid = data.verification_id or uuid4().hex
    repo.create(
        db,
        id=rid,
        verification_type=data.verification_type,
        result=data.result,
        score=data.score,
        review_reason=data.review_reason,
        rule_evidence_json=_evidence_to_json(list(data.rule_evidence)),
        created_at=now or _now_iso(),
        review_status="pending",
    )
    return rid


def list_pending(db: Session) -> list[ReviewRecord]:
    return [_to_record(r) for r in repo.list_by_status(db, "pending")]


def get(db: Session, verification_id: str) -> Optional[ReviewRecord]:
    row = repo.get(db, verification_id)
    return _to_record(row) if row else None


def decide(
    db: Session,
    verification_id: str,
    decision: ReviewDecision,
    note: str = "",
    reviewer_id: Optional[str] = None,
    now: Optional[str] = None,
) -> ReviewRecord:
    row = repo.update_decision(
        db,
        verification_id,
        decision=decision,
        note=note,
        reviewer_id=reviewer_id,
        reviewed_at=now or _now_iso(),
    )
    if row is None:
        raise KeyError(verification_id)
    return _to_record(row)
