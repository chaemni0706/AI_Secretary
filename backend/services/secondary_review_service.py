"""Secondary review queue (in-memory PoC) for VLM-based image verification.

배경: water task 의 `verified` 는 외관만으로 확정 불가한 케이스(오염수/변기물/맥주+물/borderline)가 있어
자동 최종 성공으로 처리하지 않고 `review_required=true` 로 표시한다(→ [image_verification_service.apply_secondary_review_policy]).
이 스토어는 그 결과를 **운영 큐(pending → approved/rejected/needs_retake)** 로 추적한다.

주의:
- Rule Engine core / final_result enum 미변경. review_status 는 별개 운영 상태.
- **in-memory(PoC)** — 서버 재시작 시 사라진다(기존 wakeup_session_store 선례와 동일). 프로덕션은 DB 테이블 백킹 필요.
- 이미지 인증은 현재 DB 저장이 없어 record 는 응답 시점 데이터로 구성한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from backend.database.schema.image_verification_schema import (
    ImageVerificationData,
    ReviewDecision,
    ReviewRecord,
    ReviewStatus,
    RuleEvidence,
    VerificationResult,
    VerificationType,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ReviewEntry:
    id: str
    verification_type: VerificationType
    result: VerificationResult
    score: int
    review_reason: str
    created_at: str
    rule_evidence: list[RuleEvidence] = field(default_factory=list)
    review_status: ReviewStatus = "pending"
    review_decision: Optional[ReviewDecision] = None
    review_note: str = ""
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[str] = None


class SecondaryReviewStore:
    def __init__(self) -> None:
        self._records: dict[str, ReviewEntry] = {}

    # ---- 등록 ---------------------------------------------------------------
    def register(self, data: ImageVerificationData, now: Optional[str] = None) -> str:
        """review_required 인 결과를 pending 으로 큐에 등록하고 record id 를 반환."""
        if not data.review_required:
            raise ValueError("review_required=false 인 결과는 review queue 에 등록하지 않는다.")
        rid = data.verification_id or uuid4().hex
        self._records[rid] = ReviewEntry(
            id=rid,
            verification_type=data.verification_type,
            result=data.result,
            score=data.score,
            review_reason=data.review_reason,
            created_at=now or _now_iso(),
            rule_evidence=list(data.rule_evidence),
            review_status="pending",
        )
        return rid

    # ---- 조회 ---------------------------------------------------------------
    def list_pending(self) -> list[ReviewRecord]:
        return [self._to_record(e) for e in self._records.values() if e.review_status == "pending"]

    def get(self, verification_id: str) -> Optional[ReviewRecord]:
        entry = self._records.get(verification_id)
        return self._to_record(entry) if entry else None

    # ---- 결정 ---------------------------------------------------------------
    def decide(
        self,
        verification_id: str,
        decision: ReviewDecision,
        note: str = "",
        reviewer_id: Optional[str] = None,
        now: Optional[str] = None,
    ) -> ReviewRecord:
        entry = self._records.get(verification_id)
        if entry is None:
            raise KeyError(verification_id)
        # 최종 UI 판단은 review_status 를 우선. review_required 는 '검수 대상이었는가' 의미라 유지.
        entry.review_status = decision  # approved | rejected | needs_retake
        entry.review_decision = decision
        entry.review_note = note
        entry.reviewer_id = reviewer_id
        entry.reviewed_at = now or _now_iso()
        return self._to_record(entry)

    # ---- 유틸 ---------------------------------------------------------------
    def _to_record(self, e: ReviewEntry) -> ReviewRecord:
        return ReviewRecord(
            id=e.id,
            verification_type=e.verification_type,
            result=e.result,
            score=e.score,
            review_required=True,
            review_reason=e.review_reason,
            review_status=e.review_status,
            review_decision=e.review_decision,
            review_note=e.review_note,
            reviewer_id=e.reviewer_id,
            created_at=e.created_at,
            reviewed_at=e.reviewed_at,
            rule_evidence=e.rule_evidence,
        )

    def clear(self) -> None:
        """테스트용 초기화."""
        self._records.clear()


# 모듈 싱글턴(기존 wakeup_session_store 선례와 동일 패턴).
secondary_review_store = SecondaryReviewStore()
