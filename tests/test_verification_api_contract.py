"""통합 인증 API 계약(contract) smoke 테스트.

프론트/Swagger 시연에서 기대하는 request/response 계약을 최소한으로 고정한다.
실제 Qwen VLM은 호출하지 않고 MockVisionAnalyzer로 대체한다. 기존 API는 건드리지 않는다.
"""

from __future__ import annotations

from datetime import datetime, timezone
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
from backend.services.vision_analyzer import MockVisionAnalyzer

ANALYZER_PATH = "backend.services.image_verification_service.get_default_vision_analyzer"


def _img(fmt="JPEG"):
    buf = BytesIO()
    Image.new("RGB", (4, 4), color="white").save(buf, format=fmt)
    buf.seek(0)
    return buf


WATER_PASS = VisionAnalysis(
    quality=ImageQuality(usable=True),
    objects=[ImageObjectObservation(label="glass", confidence=0.9)],
    water_visual_evidence=["visible_water", "filled_container"],
)
WATER_FAIL = VisionAnalysis(
    quality=ImageQuality(usable=True),
    objects=[ImageObjectObservation(label="cup", confidence=0.9)],
    water_visual_evidence=["empty_container"],
)
GYM_PASS = VisionAnalysis(
    quality=ImageQuality(usable=True),
    objects=[ImageObjectObservation(label="weight_machine", confidence=0.9)],
    exercise_visual_evidence=["gym_environment", "weight_machine_present"],
)
STUDY_PASS = VisionAnalysis(
    quality=ImageQuality(usable=True),
    objects=[ImageObjectObservation(label="book", confidence=0.9)],
    study_visual_evidence=["open_textbook", "open_workbook", "handwritten_notes"],
)
STUDY_GAMING = VisionAnalysis(
    quality=ImageQuality(usable=True),
    objects=[ImageObjectObservation(label="monitor", confidence=0.9)],
    study_visual_evidence=["gaming_content"],
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _post(path, data=None, files=None, json=None):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(path, data=data, files=files, json=json)


def _envelope(body, *, success=True):
    assert set(body.keys()) == {"success", "message", "data"}, body
    assert body["success"] is success
    assert isinstance(body["message"], str) and body["message"]
    return body["data"]


# ---------------------------------------------------------------------------
# VLM 이미지 인증
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_water_verified_contract(monkeypatch):
    monkeypatch.setattr(ANALYZER_PATH, lambda: MockVisionAnalyzer(WATER_PASS))
    r = await _post("/api/v1/verification/image/water",
                    files={"file": ("w.jpg", _img(), "image/jpeg")})
    assert r.status_code == 200
    data = _envelope(r.json())
    assert data["verification_type"] == "water"
    assert data["result"] == "verified"
    # 프론트 계약 필드 존재
    for key in ("result", "score", "mandatory_passed", "rule_evidence", "vlm_analysis"):
        assert key in data


@pytest.mark.anyio
async def test_water_rejected_contract(monkeypatch):
    monkeypatch.setattr(ANALYZER_PATH, lambda: MockVisionAnalyzer(WATER_FAIL))
    r = await _post("/api/v1/verification/image/water",
                    files={"file": ("w.jpg", _img(), "image/jpeg")})
    assert r.status_code == 200
    data = _envelope(r.json())
    assert data["result"] == "rejected"
    assert any(e["code"].startswith("water_priority") for e in data["rule_evidence"])


@pytest.mark.anyio
async def test_exercise_verified_contract(monkeypatch):
    monkeypatch.setattr(ANALYZER_PATH, lambda: MockVisionAnalyzer(GYM_PASS))
    r = await _post("/api/v1/verification/image/exercise",
                    data={"activity_type": "gym"},
                    files={"file": ("e.jpg", _img(), "image/jpeg")})
    assert r.status_code == 200
    data = _envelope(r.json())
    assert data["verification_type"] == "exercise"
    assert data["result"] == "verified"


@pytest.mark.anyio
async def test_exercise_missing_activity_type_422():
    r = await _post("/api/v1/verification/image/exercise",
                    files={"file": ("e.jpg", _img(), "image/jpeg")})
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False


@pytest.mark.anyio
async def test_study_verified_contract(monkeypatch):
    monkeypatch.setattr(ANALYZER_PATH, lambda: MockVisionAnalyzer(STUDY_PASS))
    r = await _post("/api/v1/verification/image/study",
                    files={"file": ("s.jpg", _img(), "image/jpeg")})
    assert r.status_code == 200
    data = _envelope(r.json())
    assert data["verification_type"] == "study"
    assert data["result"] == "verified"


@pytest.mark.anyio
async def test_study_gaming_rejected_contract(monkeypatch):
    monkeypatch.setattr(ANALYZER_PATH, lambda: MockVisionAnalyzer(STUDY_GAMING))
    r = await _post("/api/v1/verification/image/study",
                    files={"file": ("s.jpg", _img(), "image/jpeg")})
    assert r.status_code == 200
    data = _envelope(r.json())
    assert data["result"] != "verified"


@pytest.mark.anyio
async def test_unknown_image_type_400():
    r = await _post("/api/v1/verification/image/dancing",
                    files={"file": ("x.jpg", _img(), "image/jpeg")})
    assert r.status_code == 400
    assert r.json()["success"] is False


@pytest.mark.anyio
async def test_wakeup_not_allowed_on_image_endpoint_400():
    """wakeup은 이미지 인증 endpoint로 라우팅되면 안 된다."""
    r = await _post("/api/v1/verification/image/wakeup",
                    files={"file": ("x.jpg", _img(), "image/jpeg")})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# 기상(wakeup) 인증
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_wakeup_session_contract():
    r = await _post("/api/v1/verification/wakeup/session",
                    json={"scheduled_at": "2026-07-02T07:00:00+09:00", "session_ttl_seconds": 600})
    assert r.status_code == 200
    data = _envelope(r.json())
    for key in ("session_id", "scheduled_at", "server_issued_at", "expires_at", "max_retries"):
        assert key in data


@pytest.mark.anyio
async def test_wakeup_session_requires_timezone_422():
    r = await _post("/api/v1/verification/wakeup/session",
                    json={"scheduled_at": "2026-07-02T07:00:00"})  # tz 없음
    assert r.status_code == 422
    assert r.json()["success"] is False


@pytest.mark.anyio
async def test_wakeup_submit_contract():
    now_iso = datetime.now(timezone.utc).isoformat()
    sess = await _post("/api/v1/verification/wakeup/session",
                       json={"scheduled_at": now_iso, "session_ttl_seconds": 600})
    session_id = _envelope(sess.json())["session_id"]

    submit = await _post("/api/v1/verification/wakeup/submit",
                         data={"session_id": session_id},
                         files={"file": ("wake.jpg", _img(), "image/jpeg")})
    assert submit.status_code == 200
    data = _envelope(submit.json())
    assert data["verification_type"] == "wakeup"
    assert data["result"] in {"verified", "rejected", "retake_required"}
    wd = data["wakeup_data"]
    for key in ("decision", "received_at", "image_sha256", "reasons", "retry_count", "max_retries"):
        assert key in wd


@pytest.mark.anyio
async def test_wakeup_submit_unknown_session_rejected():
    r = await _post("/api/v1/verification/wakeup/submit",
                    data={"session_id": "does-not-exist"},
                    files={"file": ("wake.jpg", _img(), "image/jpeg")})
    assert r.status_code == 200
    data = _envelope(r.json())
    assert data["result"] == "rejected"
