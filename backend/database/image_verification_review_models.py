"""SQLAlchemy ORM model for the secondary_review queue (VLM 이미지 인증).

ledger_models.py 와 동일한 방식으로 ``models.py`` 와 SEPARATE 모듈에 두되 같은 declarative ``Base`` 를 공유한다
(planner 도메인의 "no new tables" 계약을 건드리지 않기 위해). ``database/local_schema.sql`` 에 append 된
``image_verification_reviews`` 테이블을 매핑한다.

conventions:
- 테이블은 local_schema.sql(raw SQL, IF NOT EXISTS)로 생성. ``Base.metadata.create_all`` 미사용.
- review_status/review_decision 은 API/pydantic 과 동일한 lowercase 값 저장(이 도메인 신규 enum → 매핑 레이어 없음).
- 시각은 ISO datetime 문자열(created_at/reviewed_at). rule_evidence 는 JSON TEXT.
- 이미지 인증은 결과 record 를 별도 저장하지 않으므로 user/verification FK 없이 독립.
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, Text

from backend.database.models import Base

REVIEW_STATUS_VALUES = ("none", "pending", "approved", "rejected", "needs_retake")
REVIEW_DECISION_VALUES = ("approved", "rejected", "needs_retake")


class ImageVerificationReviewRow(Base):
    __tablename__ = "image_verification_reviews"

    id = Column(String, primary_key=True)
    verification_type = Column(String, nullable=False)
    result = Column(String, nullable=False)              # final_result (불변)
    score = Column(Integer, nullable=False, default=0)
    review_reason = Column(String, nullable=False, default="")
    review_status = Column(String, nullable=False, default="pending")
    review_decision = Column(String)                     # nullable
    review_note = Column(Text, nullable=False, default="")
    reviewer_id = Column(String)                         # nullable
    rule_evidence_json = Column(Text)                    # JSON array 문자열, 없으면 NULL
    created_at = Column(String, nullable=False)
    reviewed_at = Column(String)                         # nullable
