"""Persistence helpers for the secondary_review queue (image_verification_reviews).

repository.py 와 동일한 스타일: 전달받은 SQLAlchemy ``Session`` 위에서 동작하는 순수 CRUD.
비즈니스 규칙(review_status 전이, JSON 직렬화, ReviewRecord 변환)은 service 계층에서 처리한다.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.image_verification_review_models import ImageVerificationReviewRow


def create(
    db: Session,
    *,
    id: str,
    verification_type: str,
    result: str,
    score: int,
    review_reason: str,
    rule_evidence_json: Optional[str],
    created_at: str,
    review_status: str = "pending",
) -> ImageVerificationReviewRow:
    row = ImageVerificationReviewRow(
        id=id,
        verification_type=verification_type,
        result=result,
        score=score,
        review_reason=review_reason,
        review_status=review_status,
        review_note="",
        rule_evidence_json=rule_evidence_json,
        created_at=created_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get(db: Session, review_id: str) -> Optional[ImageVerificationReviewRow]:
    return db.get(ImageVerificationReviewRow, review_id)


def list_by_status(db: Session, status: str) -> list[ImageVerificationReviewRow]:
    stmt = (
        select(ImageVerificationReviewRow)
        .where(ImageVerificationReviewRow.review_status == status)
        .order_by(ImageVerificationReviewRow.created_at)
    )
    return list(db.execute(stmt).scalars().all())


def update_decision(
    db: Session,
    review_id: str,
    *,
    decision: str,
    note: str,
    reviewer_id: Optional[str],
    reviewed_at: str,
) -> Optional[ImageVerificationReviewRow]:
    row = db.get(ImageVerificationReviewRow, review_id)
    if row is None:
        return None
    # 최종 UI 판단은 review_status 를 우선. review_status 를 decision 값으로 전이.
    row.review_status = decision  # approved | rejected | needs_retake
    row.review_decision = decision
    row.review_note = note
    row.reviewer_id = reviewer_id
    row.reviewed_at = reviewed_at
    db.commit()
    db.refresh(row)
    return row
