from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from PIL import Image

from backend.services.wakeup_verification_service import WakeupSessionStore


def _now():
    return datetime(2026, 7, 2, 7, 0, tzinfo=timezone.utc)


def _image_bytes(fmt="JPEG"):
    buffer = BytesIO()
    Image.new("RGB", (4, 4), color="white").save(buffer, format=fmt)
    buffer.seek(0)
    return buffer


def _session(store, scheduled_at=None, issued_at=None, ttl=120):
    scheduled = scheduled_at or _now()
    scheduled_value = scheduled if isinstance(scheduled, str) else scheduled.isoformat()
    return store.create_session(
        scheduled_at=scheduled_value,
        session_ttl_seconds=ttl,
        now=issued_at or _now(),
    )


def test_wakeup_verify_within_allowed_window_is_verified():
    store = WakeupSessionStore()
    session = _session(store, ttl=600)

    data = store.verify_upload(
        session.session_id,
        _image_bytes(),
        filename="wakeup.jpg",
        content_type="image/jpeg",
        now=_now() + timedelta(minutes=3),
    )

    assert data.decision == "verified"
    assert data.difference_minutes == 3
    assert data.session_expired is False
    assert data.duplicate_image is False
    assert data.image_quality_usable is True
    assert store.sessions[session.session_id].used is True


def test_wakeup_too_early_is_rejected():
    store = WakeupSessionStore()
    session = _session(store)

    data = store.verify_upload(
        session.session_id,
        _image_bytes(),
        filename="wakeup.jpg",
        content_type="image/jpeg",
        now=_now() - timedelta(minutes=6),
    )

    assert data.decision == "rejected"
    assert "too_early" in data.reasons
    assert store.sessions[session.session_id].used is True


def test_wakeup_too_late_is_rejected():
    store = WakeupSessionStore()
    session = _session(store)

    data = store.verify_upload(
        session.session_id,
        _image_bytes(),
        filename="wakeup.jpg",
        content_type="image/jpeg",
        now=_now() + timedelta(minutes=11),
    )

    assert data.decision == "rejected"
    assert "too_late" in data.reasons


def test_wakeup_expired_session_is_rejected():
    store = WakeupSessionStore()
    session = _session(store, issued_at=_now() - timedelta(minutes=10), ttl=60)

    data = store.verify_upload(
        session.session_id,
        _image_bytes(),
        filename="wakeup.jpg",
        content_type="image/jpeg",
        now=_now(),
    )

    assert data.decision == "rejected"
    assert data.session_expired is True
    assert "session_expired" in data.reasons


def test_wakeup_used_session_cannot_be_reused():
    store = WakeupSessionStore()
    session = _session(store)

    first = store.verify_upload(session.session_id, _image_bytes(), "wakeup.jpg", "image/jpeg", now=_now())
    second = store.verify_upload(
        session.session_id,
        _image_bytes("PNG"),
        "wakeup.png",
        "image/png",
        now=_now() + timedelta(minutes=1),
    )

    assert first.decision == "verified"
    assert second.decision == "rejected"
    assert "session_already_used" in second.reasons


def test_wakeup_duplicate_image_hash_is_rejected():
    store = WakeupSessionStore()
    image = _image_bytes().getvalue()
    first_session = _session(store)
    second_session = _session(store)

    first = store.verify_upload(first_session.session_id, BytesIO(image), "wakeup.jpg", "image/jpeg", now=_now())
    second = store.verify_upload(second_session.session_id, BytesIO(image), "wakeup.jpg", "image/jpeg", now=_now())

    assert first.decision == "verified"
    assert second.decision == "rejected"
    assert second.duplicate_image is True


def test_wakeup_corrupt_image_requires_retake():
    store = WakeupSessionStore()
    session = _session(store)
    image = b"not-an-image"

    data = store.verify_upload(
        session.session_id,
        BytesIO(image),
        filename="wakeup.jpg",
        content_type="image/jpeg",
        now=_now(),
    )

    assert data.decision == "retake_required"
    assert data.image_quality_usable is False
    assert "image_unusable" in data.reasons
    assert data.retry_count == 1
    assert data.max_retries == 2
    assert store.sessions[session.session_id].used is False
    assert data.image_sha256 not in store.used_image_hashes


def test_wakeup_retake_then_new_valid_image_can_be_verified_with_same_session():
    store = WakeupSessionStore()
    session = _session(store, ttl=600)

    retake = store.verify_upload(
        session.session_id,
        BytesIO(b"not-an-image"),
        filename="wakeup.jpg",
        content_type="image/jpeg",
        now=_now(),
    )
    verified = store.verify_upload(
        session.session_id,
        _image_bytes(),
        filename="wakeup.jpg",
        content_type="image/jpeg",
        now=_now() + timedelta(minutes=1),
    )

    assert retake.decision == "retake_required"
    assert verified.decision == "verified"
    assert verified.retry_count == 1
    assert store.sessions[session.session_id].used is True
    assert verified.image_sha256 in store.used_image_hashes


def test_wakeup_retake_is_limited_by_max_retries():
    store = WakeupSessionStore()
    session = store.create_session(
        scheduled_at="2026-07-02T16:00:00+09:00",
        session_ttl_seconds=600,
        max_retries=2,
        now=_now(),
    )

    first = store.verify_upload(session.session_id, BytesIO(b"bad-1"), "wakeup.jpg", "image/jpeg", now=_now())
    second = store.verify_upload(session.session_id, BytesIO(b"bad-2"), "wakeup.jpg", "image/jpeg", now=_now())
    third = store.verify_upload(session.session_id, BytesIO(b"bad-3"), "wakeup.jpg", "image/jpeg", now=_now())

    assert first.decision == "retake_required"
    assert second.decision == "retake_required"
    assert third.decision == "rejected"
    assert "max_retries_exceeded" in third.reasons
    assert third.retry_count == 2
    assert store.sessions[session.session_id].used is True


def test_wakeup_scheduled_at_with_timezone_offset_is_accepted():
    store = WakeupSessionStore()

    session = store.create_session(
        scheduled_at="2026-07-02T07:00:00+09:00",
        now=_now(),
    )

    assert session.scheduled_at == "2026-07-02T07:00:00+09:00"


def test_wakeup_scheduled_at_without_timezone_is_rejected():
    store = WakeupSessionStore()

    try:
        store.create_session(scheduled_at="2026-07-02T07:00:00", now=_now())
    except ValueError as exc:
        assert "timezone" in str(exc)
    else:
        raise AssertionError("timezone 없는 scheduled_at은 거절되어야 합니다.")


def test_wakeup_server_received_at_is_the_decision_basis():
    store = WakeupSessionStore()
    session = _session(store, scheduled_at=_now().isoformat())

    data = store.verify_upload(
        session.session_id,
        _image_bytes(),
        filename="client-claims-0700.jpg",
        content_type="image/jpeg",
        now=_now() + timedelta(minutes=20),
    )

    assert data.decision == "rejected"
    assert data.difference_minutes == 20
    assert "too_late" in data.reasons


def test_wakeup_exif_or_client_time_is_not_trusted():
    store = WakeupSessionStore()
    session = _session(store, scheduled_at=_now().isoformat())

    data = store.verify_upload(
        session.session_id,
        _image_bytes(),
        filename="exif-time-inside-window.jpg",
        content_type="image/jpeg",
        now=_now() - timedelta(minutes=30),
    )

    assert data.decision == "rejected"
    assert "too_early" in data.reasons


def test_wakeup_display_time_is_guidance_only():
    store = WakeupSessionStore()
    session = _session(store)

    assert session.display_time == session.server_issued_at
    data = store.verify_upload(session.session_id, _image_bytes(), "wakeup.jpg", "image/jpeg", now=_now())
    assert data.decision == "verified"


def test_wakeup_temp_image_is_deleted_after_success_and_failure(monkeypatch):
    store = WakeupSessionStore()
    seen_paths = []
    original_save = "backend.services.wakeup_verification_service._save_temp_upload"

    from backend.services import wakeup_verification_service as service

    save_func = service._save_temp_upload

    def recording_save(*args, **kwargs):
        path = save_func(*args, **kwargs)
        seen_paths.append(Path(path))
        return path

    monkeypatch.setattr(original_save, recording_save)
    success_session = _session(store)
    failure_session = _session(store)

    success = store.verify_upload(success_session.session_id, _image_bytes(), "wakeup.jpg", "image/jpeg", now=_now())
    failure = store.verify_upload(
        failure_session.session_id,
        BytesIO(b"not-an-image"),
        "wakeup.jpg",
        "image/jpeg",
        now=_now(),
    )

    assert success.decision == "verified"
    assert failure.decision == "retake_required"
    assert seen_paths
    assert all(path.exists() is False for path in seen_paths)
