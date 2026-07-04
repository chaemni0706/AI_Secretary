"""Image verification orchestration service."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import BinaryIO, Optional

from PIL import Image, UnidentifiedImageError

from backend.database.schema.image_verification_schema import (
    ExerciseActivityType,
    ImageVerificationContext,
    ImageVerificationData,
    LocationInput,
    TimeContext,
    VerificationType,
)
from backend.services.image_verification_rule_engine import evaluate_image_verification
from backend.services.image_verification_rules_loader import allowed_labels
from backend.services.vision_analyzer import VisionAnalyzer, get_default_vision_analyzer

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def verify_image_upload(
    file_obj: BinaryIO,
    filename: str,
    content_type: Optional[str],
    verification_type: VerificationType,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    target_latitude: Optional[float] = None,
    target_longitude: Optional[float] = None,
    captured_at: Optional[str] = None,
    scheduled_at: Optional[str] = None,
    exercise_activity_type: Optional[ExerciseActivityType] = None,
    analyzer: Optional[VisionAnalyzer] = None,
) -> ImageVerificationData:
    if content_type and content_type not in _ALLOWED_CONTENT_TYPES:
        raise ValueError("지원하지 않는 이미지 형식입니다.")

    tmp_path = _save_temp_upload(file_obj, filename)
    try:
        _validate_image_file(tmp_path)
        labels = allowed_labels(verification_type)
        vision = analyzer or get_default_vision_analyzer()
        analysis = vision.analyze(tmp_path, verification_type, labels)
        context = _build_context(
            latitude,
            longitude,
            target_latitude,
            target_longitude,
            captured_at,
            scheduled_at,
            exercise_activity_type,
        )
        return evaluate_image_verification(verification_type, analysis, context)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _save_temp_upload(file_obj: BinaryIO, filename: str) -> Path:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".img"

    fd, raw_path = tempfile.mkstemp(prefix="image-verification-", suffix=suffix)
    path = Path(raw_path)
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = file_obj.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > _MAX_UPLOAD_BYTES:
                    raise ValueError("이미지 파일은 10MB 이하만 업로드할 수 있습니다.")
                out.write(chunk)
        if size == 0:
            raise ValueError("빈 이미지 파일입니다.")
        return path
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _validate_image_file(path: Path) -> None:
    try:
        with Image.open(path) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("유효한 이미지 파일이 아닙니다.") from exc


def _build_context(
    latitude: Optional[float],
    longitude: Optional[float],
    target_latitude: Optional[float],
    target_longitude: Optional[float],
    captured_at: Optional[str],
    scheduled_at: Optional[str],
    exercise_activity_type: Optional[ExerciseActivityType] = None,
) -> ImageVerificationContext:
    location = None
    if latitude is not None and longitude is not None:
        location = LocationInput(latitude=latitude, longitude=longitude)
    target_location = None
    if target_latitude is not None and target_longitude is not None:
        target_location = LocationInput(latitude=target_latitude, longitude=target_longitude)
    return ImageVerificationContext(
        location=location,
        target_location=target_location,
        time=TimeContext(captured_at=captured_at, scheduled_at=scheduled_at),
        exercise_activity_type=exercise_activity_type,
    )
