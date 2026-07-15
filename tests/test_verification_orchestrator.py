"""Verification orchestrator 라우팅/책임 분리 테스트.

- water/exercise/study → VLM 이미지 pipeline (MockVisionAnalyzer 사용, 실제 Qwen 미호출)
- wakeup → 세션/시간 기반 service (VLM/Rule Engine 미호출)
- 알 수 없는 타입 → UnsupportedVerificationType / 400
- 새 통합 endpoint(/api/v1/verification/...) 스모크
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO

import httpx
import pytest
from PIL import Image

from backend.main import app
from backend.database.schema.image_verification_schema import (
    ImageObjectObservation,
    ImageQuality,
    VisionAnalysis,
)
from backend.services import verification_orchestrator as orch
from backend.services.vision_analyzer import MockVisionAnalyzer
from backend.services.wakeup_verification_service import WakeupSessionStore


def _img(fmt="JPEG"):
    buf = BytesIO()
    Image.new("RGB", (4, 4), color="white").save(buf, format=fmt)
    buf.seek(0)
    return buf


def _now():
    return datetime(2026, 7, 2, 7, 0, tzinfo=timezone.utc)


WATER_PASS = VisionAnalysis(
    quality=ImageQuality(usable=True),
    objects=[ImageObjectObservation(label="glass", confidence=0.9)],
    water_visual_evidence=["visible_water", "filled_container"],
)
STUDY_PASS = VisionAnalysis(
    quality=ImageQuality(usable=True),
    objects=[ImageObjectObservation(label="book", confidence=0.9)],
    study_visual_evidence=["open_textbook", "open_workbook", "handwritten_notes"],
)
GYM_PASS = VisionAnalysis(
    quality=ImageQuality(usable=True),
    objects=[ImageObjectObservation(label="weight_machine", confidence=0.9)],
    exercise_visual_evidence=["gym_environment", "weight_machine_present"],
)
STUDY_DEVICE_ONLY = VisionAnalysis(
    quality=ImageQuality(usable=True),
    objects=[ImageObjectObservation(label="laptop", confidence=0.9)],
)


@pytest.fixture
def fresh_wakeup_store(monkeypatch):
    store = WakeupSessionStore()
    monkeypatch.setattr(orch, "wakeup_session_store", store)
    return store


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# A. VLM 기반 라우팅
# ---------------------------------------------------------------------------

def test_category_routing():
    assert orch.verification_category("water") == "image"
    assert orch.verification_category("exercise") == "image"
    assert orch.verification_category("study") == "image"
    assert orch.verification_category("wakeup") == "session"


def test_verify_water_routes_to_image_pipeline():
    data = orch.verify("water", file_obj=_img(), filename="w.jpg",
                       content_type="image/jpeg", analyzer=MockVisionAnalyzer(WATER_PASS))
    assert data.verification_type == "water"
    assert data.result == "verified"


def test_verify_exercise_uses_activity_context():
    data = orch.verify("exercise", file_obj=_img(), filename="e.jpg", content_type="image/jpeg",
                       exercise_activity_type="gym", analyzer=MockVisionAnalyzer(GYM_PASS))
    assert data.verification_type == "exercise"
    assert data.result == "verified"


def test_verify_study_routes_to_study_rule_engine():
    data = orch.verify("study", file_obj=_img(), filename="s.jpg",
                       content_type="image/jpeg", analyzer=MockVisionAnalyzer(STUDY_PASS))
    assert data.verification_type == "study"
    assert data.result == "verified"


def test_study_device_only_is_not_verified():
    """기기(노트북)만으로는 verified 되면 안 된다."""
    data = orch.verify("study", file_obj=_img(), filename="s.jpg",
                       content_type="image/jpeg", analyzer=MockVisionAnalyzer(STUDY_DEVICE_ONLY))
    assert data.result != "verified"


def test_unknown_verification_type_raises():
    with pytest.raises(orch.UnsupportedVerificationType):
        orch.verify("dancing", file_obj=_img(), filename="x.jpg", content_type="image/jpeg")


def test_exercise_without_activity_type_raises():
    with pytest.raises(ValueError):
        orch.verify("exercise", file_obj=_img(), filename="e.jpg",
                    content_type="image/jpeg", analyzer=MockVisionAnalyzer(GYM_PASS))


# ---------------------------------------------------------------------------
# B. wakeup 라우팅 — VLM 미사용, 서버 시각 기반
# ---------------------------------------------------------------------------

def test_wakeup_does_not_call_vision_analyzer(fresh_wakeup_store):
    class ExplodingAnalyzer:
        def analyze(self, *a, **k):
            raise AssertionError("wakeup must not call the VisionAnalyzer")

    session = orch.create_wakeup_session(scheduled_at=_now().isoformat(), session_ttl_seconds=600, now=_now())
    # analyzer를 넘겨도 wakeup 경로는 이를 무시해야 한다.
    data = orch.verify("wakeup", session_id=session.session_id, file_obj=_img(),
                       filename="wake.jpg", content_type="image/jpeg",
                       analyzer=ExplodingAnalyzer(), now=_now() + timedelta(minutes=3))
    assert data.decision == "verified"
    assert data.image_quality_usable is True


def test_wakeup_uses_server_received_time_not_device_time(fresh_wakeup_store):
    """판정은 서버 수신 시각(now) 기준. EXIF/디바이스 시각은 입력조차 받지 않는다."""
    session = orch.create_wakeup_session(scheduled_at=_now().isoformat(), session_ttl_seconds=600, now=_now())
    data = orch.verify("wakeup", session_id=session.session_id, file_obj=_img(),
                       filename="wake.jpg", content_type="image/jpeg",
                       now=_now() + timedelta(minutes=3))
    assert data.decision == "verified"
    assert data.difference_minutes == 3


def test_wakeup_requires_session_id():
    with pytest.raises(ValueError):
        orch.verify("wakeup", file_obj=_img(), filename="w.jpg", content_type="image/jpeg")


# ---------------------------------------------------------------------------
# D. wakeup 실패 케이스
# ---------------------------------------------------------------------------

def test_wakeup_expired_session_rejected(fresh_wakeup_store):
    session = orch.create_wakeup_session(scheduled_at=_now().isoformat(), session_ttl_seconds=60, now=_now())
    data = orch.verify_wakeup(session.session_id, _img(), "w.jpg", "image/jpeg",
                              now=_now() + timedelta(minutes=10))
    assert data.decision == "rejected"
    assert data.session_expired is True


def test_wakeup_duplicate_image_rejected(fresh_wakeup_store):
    s1 = orch.create_wakeup_session(scheduled_at=_now().isoformat(), session_ttl_seconds=600, now=_now())
    first = orch.verify_wakeup(s1.session_id, _img(), "w.jpg", "image/jpeg", now=_now() + timedelta(minutes=3))
    assert first.decision == "verified"
    s2 = orch.create_wakeup_session(scheduled_at=_now().isoformat(), session_ttl_seconds=600, now=_now())
    dup = orch.verify_wakeup(s2.session_id, _img(), "w.jpg", "image/jpeg", now=_now() + timedelta(minutes=3))
    assert dup.decision == "rejected"
    assert dup.duplicate_image is True


def test_wakeup_max_retries_exceeded_rejected(fresh_wakeup_store):
    session = orch.create_wakeup_session(scheduled_at=_now().isoformat(),
                                         session_ttl_seconds=600, max_retries=2, now=_now())
    # 유효하지 않은 이미지(품질 불가) → retake 2회 후 rejected
    decisions = []
    for i in range(3):
        data = orch.verify_wakeup(session.session_id, BytesIO(f"not-an-image-{i}".encode()),
                                  "w.jpg", "image/jpeg", now=_now() + timedelta(minutes=3))
        decisions.append(data.decision)
    assert decisions[0] == "retake_required"
    assert decisions[1] == "retake_required"
    assert decisions[2] == "rejected"
    assert "max_retries_exceeded" in data.reasons


# ---------------------------------------------------------------------------
# 새 통합 endpoint 스모크 (API 레이어)
# ---------------------------------------------------------------------------

async def _post(path, data=None, files=None, json=None):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(path, data=data, files=files, json=json)


@pytest.mark.anyio
async def test_api_image_water_endpoint(monkeypatch):
    monkeypatch.setattr(
        "backend.services.image_verification_service.get_default_vision_analyzer",
        lambda: MockVisionAnalyzer(WATER_PASS),
    )
    # 오늘 production patch: Smol 단독 verified 없음 -- Qwen7B 자리에도 동등 evidence mock 주입.
    monkeypatch.setattr(
        "backend.services.image_verification_service.get_qwen7b_analyzer",
        lambda: MockVisionAnalyzer(WATER_PASS.model_copy(update={"model_name": "qwen7b-mock"})),
    )
    resp = await _post("/api/v1/verification/image/water",
                       files={"file": ("w.jpg", _img(), "image/jpeg")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["verification_type"] == "water"
    assert body["data"]["result"] == "verified"


@pytest.mark.anyio
async def test_api_image_exercise_requires_activity_type():
    resp = await _post("/api/v1/verification/image/exercise",
                       files={"file": ("e.jpg", _img(), "image/jpeg")})
    assert resp.status_code == 422
    assert resp.json()["success"] is False


@pytest.mark.anyio
async def test_api_image_unknown_type_400():
    resp = await _post("/api/v1/verification/image/dancing",
                       files={"file": ("x.jpg", _img(), "image/jpeg")})
    assert resp.status_code == 400
    assert resp.json()["success"] is False


@pytest.mark.anyio
async def test_api_wakeup_session_and_submit():
    sess = await _post("/api/v1/verification/wakeup/session",
                       json={"scheduled_at": _now().isoformat(), "session_ttl_seconds": 600})
    assert sess.status_code == 200
    session_id = sess.json()["data"]["session_id"]

    submit = await _post("/api/v1/verification/wakeup/submit",
                         data={"session_id": session_id},
                         files={"file": ("wake.jpg", _img(), "image/jpeg")})
    assert submit.status_code == 200
    data = submit.json()["data"]
    assert data["verification_type"] == "wakeup"
    assert data["result"] in {"verified", "rejected", "retake_required"}
    assert "wakeup_data" in data
