"""Server-time wakeup verification prototype.

Sessions are stored in memory for this PoC and disappear when the server
process restarts. The uploaded photo is only used for image usability and
duplicate checks; phone time, EXIF time, and visible clock text are not trusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from typing import BinaryIO, Callable, Optional
from uuid import uuid4

from PIL import UnidentifiedImageError

from backend.database.schema.image_verification_schema import (
    WakeupSessionData,
    WakeupVerificationData,
)
from backend.services.image_verification_service import _save_temp_upload, _validate_image_file


Clock = Callable[[], datetime]


@dataclass
class WakeupSession:
    session_id: str
    scheduled_at: datetime
    server_issued_at: datetime
    expires_at: datetime
    allowed_early_minutes: int
    allowed_late_minutes: int
    max_retries: int
    retry_count: int = 0
    used: bool = False


class WakeupSessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, WakeupSession] = {}
        self.used_image_hashes: set[str] = set()

    def create_session(
        self,
        scheduled_at: str,
        allowed_early_minutes: int = 5,
        allowed_late_minutes: int = 10,
        session_ttl_seconds: int = 120,
        max_retries: int = 2,
        now: Optional[datetime] = None,
    ) -> WakeupSessionData:
        issued_at = _ensure_aware(now or _utcnow())
        scheduled = _parse_datetime(scheduled_at)
        session_id = uuid4().hex
        expires_at = issued_at + timedelta(seconds=session_ttl_seconds)
        self.sessions[session_id] = WakeupSession(
            session_id=session_id,
            scheduled_at=scheduled,
            server_issued_at=issued_at,
            expires_at=expires_at,
            allowed_early_minutes=allowed_early_minutes,
            allowed_late_minutes=allowed_late_minutes,
            max_retries=max_retries,
        )
        return WakeupSessionData(
            session_id=session_id,
            scheduled_at=scheduled.isoformat(),
            server_issued_at=issued_at.isoformat(),
            expires_at=expires_at.isoformat(),
            display_time=issued_at.isoformat(),
            max_retries=max_retries,
        )

    def verify_upload(
        self,
        session_id: str,
        file_obj: BinaryIO,
        filename: str,
        content_type: Optional[str],
        now: Optional[datetime] = None,
    ) -> WakeupVerificationData:
        received_at = _ensure_aware(now or _utcnow())
        session = self.sessions.get(session_id)
        tmp_path: Optional[Path] = None
        image_hash = ""
        duplicate_image = False
        image_quality_usable = False
        reasons: list[str] = []

        if session is None:
            return _missing_session_result(session_id, received_at)

        try:
            tmp_path = _save_temp_upload(file_obj, filename)
            image_bytes = tmp_path.read_bytes()
            image_hash = hashlib.sha256(image_bytes).hexdigest()
            duplicate_image = image_hash in self.used_image_hashes
            try:
                _validate_image_file(tmp_path)
                image_quality_usable = True
            except (ValueError, UnidentifiedImageError, OSError):
                image_quality_usable = False

            session_expired = received_at > session.expires_at
            too_early = received_at < session.scheduled_at - timedelta(minutes=session.allowed_early_minutes)
            too_late = received_at > session.scheduled_at + timedelta(minutes=session.allowed_late_minutes)
            difference_minutes = (received_at - session.scheduled_at).total_seconds() / 60

            if session_expired:
                reasons.append("session_expired")
            if session.used:
                reasons.append("session_already_used")
            if duplicate_image:
                reasons.append("duplicate_image")
            if not image_quality_usable:
                reasons.append("image_unusable")
            if too_early:
                reasons.append("too_early")
            if too_late:
                reasons.append("too_late")

            if session_expired or session.used or duplicate_image or too_early or too_late:
                decision = "rejected"
            elif not image_quality_usable:
                if session.retry_count < session.max_retries:
                    session.retry_count += 1
                    decision = "retake_required"
                else:
                    decision = "rejected"
                    reasons.append("max_retries_exceeded")
            else:
                decision = "verified"
                reasons.append("server_received_at_within_allowed_window")

            if decision in {"verified", "rejected"}:
                session.used = True
            if image_hash and decision in {"verified", "rejected"}:
                self.used_image_hashes.add(image_hash)

            return WakeupVerificationData(
                decision=decision,
                scheduled_at=session.scheduled_at.isoformat(),
                server_issued_at=session.server_issued_at.isoformat(),
                received_at=received_at.isoformat(),
                difference_minutes=round(difference_minutes, 3),
                session_expired=session_expired,
                duplicate_image=duplicate_image,
                image_quality_usable=image_quality_usable,
                reasons=reasons,
                image_sha256=image_hash,
                retry_count=session.retry_count,
                max_retries=session.max_retries,
            )
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass


def _missing_session_result(session_id: str, received_at: datetime) -> WakeupVerificationData:
    return WakeupVerificationData(
        decision="rejected",
        scheduled_at="",
        server_issued_at="",
        received_at=received_at.isoformat(),
        difference_minutes=0,
        session_expired=True,
        duplicate_image=False,
        image_quality_usable=False,
        reasons=[f"session_not_found:{session_id}"],
        image_sha256="",
        retry_count=0,
        max_retries=0,
    )


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("scheduled_at은 ISO datetime 형식이어야 합니다.") from exc
    if parsed.tzinfo is None:
        raise ValueError("scheduled_at에는 timezone 정보가 필요합니다.")
    return parsed


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


wakeup_session_store = WakeupSessionStore()
