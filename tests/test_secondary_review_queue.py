"""secondary_review 큐 운영 흐름 테스트 (service + API).

water verified → pending 등록 → 목록/상세 조회 → 결정(approved/rejected/needs_retake).
exercise/study verified 는 큐에 들어가지 않음. Rule Engine core/final_result enum 미변경.
"""
from io import BytesIO

import httpx
import pytest
from PIL import Image
from unittest.mock import patch

from backend.main import app
from backend.database.schema.image_verification_schema import (
    ImageObjectObservation,
    ImageVerificationData,
    RuleEvidence,
    RuleScoreBreakdown,
    VisionAnalysis,
)
from backend.services.image_verification_service import apply_secondary_review_policy
from backend.services.secondary_review_service import SecondaryReviewStore, secondary_review_store
from backend.services.vision_analyzer import MockVisionAnalyzer


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _clear_store():
    secondary_review_store.clear()
    yield
    secondary_review_store.clear()


def _image_bytes(fmt="JPEG"):
    buf = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buf, format=fmt)
    buf.seek(0)
    return buf


def _mk(task, result):
    return ImageVerificationData(
        verification_type=task, result=result, score=65, mandatory_passed=True,
        score_breakdown=RuleScoreBreakdown(), vlm_analysis=VisionAnalysis(),
        rule_evidence=[RuleEvidence(code="object:cup", message="cup", score_delta=15)],
    )


# --------------------------------------------------------------------------- service
def test_store_register_and_decide_flow():
    store = SecondaryReviewStore()
    wv = apply_secondary_review_policy(_mk("water", "verified"))
    assert wv.review_required and wv.review_status == "pending"
    rid = store.register(wv)
    assert len(store.list_pending()) == 1
    assert store.get(rid).review_status == "pending"
    rec = store.decide(rid, "approved", note="ok", reviewer_id="admin")
    assert rec.review_status == "approved"
    assert rec.review_decision == "approved"
    assert rec.reviewed_at is not None
    assert store.list_pending() == []


def test_store_rejects_non_review_result():
    store = SecondaryReviewStore()
    ev = apply_secondary_review_policy(_mk("exercise", "verified"))
    assert ev.review_required is False and ev.review_status == "none"
    with pytest.raises(ValueError):
        store.register(ev)


def test_store_decide_unknown_id_raises():
    store = SecondaryReviewStore()
    with pytest.raises(KeyError):
        store.decide("nope", "approved")


# --------------------------------------------------------------------------- API
async def _post_verify(vtype, analysis, extra=None):
    with patch("backend.services.image_verification_service.get_default_vision_analyzer",
               lambda: MockVisionAnalyzer(analysis)):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            data = {"verification_type": vtype}
            if extra:
                data.update(extra)
            return await c.post("/api/v1/image-verifications", data=data,
                                files={"file": (f"{vtype}.jpg", _image_bytes(), "image/jpeg")})


def _water_verified_analysis():
    return VisionAnalysis(
        objects=[ImageObjectObservation(label="cup", confidence=0.9)],
        water_visual_evidence=["visible_water", "filled_container"],
    )


def _exercise_verified_analysis():
    return VisionAnalysis(
        objects=[ImageObjectObservation(label="dumbbell", confidence=0.9)],
        exercise_visual_evidence=["home_exercise_pose_visible", "home_workout_environment"],
    )


@pytest.mark.anyio
async def test_api_water_verified_enters_pending_queue():
    resp = await _post_verify("water", _water_verified_analysis())
    body = resp.json()
    data = body["data"]
    assert data["result"] == "verified"
    assert data["review_required"] is True
    assert data["review_status"] == "pending"
    assert data["verification_id"]

    # pending 목록에 포함
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        lst = (await c.get("/api/v1/image-verifications/reviews/pending")).json()
    ids = [it["id"] for it in lst["data"]]
    assert data["verification_id"] in ids


@pytest.mark.anyio
async def test_api_exercise_verified_not_in_queue():
    resp = await _post_verify("exercise", _exercise_verified_analysis(),
                              {"activity_type": "home_workout"})
    data = resp.json()["data"]
    assert data["result"] == "verified"
    assert data["review_required"] is False
    assert data["review_status"] == "none"
    assert data["verification_id"] is None

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        lst = (await c.get("/api/v1/image-verifications/reviews/pending")).json()
    assert lst["data"] == []


@pytest.mark.anyio
async def test_api_review_decision_approved():
    rid = (await _post_verify("water", _water_verified_analysis())).json()["data"]["verification_id"]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        dec = (await c.post(
            f"/api/v1/image-verifications/reviews/{rid}/decision",
            json={"decision": "approved", "note": "admin ok", "reviewer_id": "admin1"},
        )).json()
        assert dec["data"]["review_status"] == "approved"
        assert dec["data"]["review_decision"] == "approved"
        # pending 에서 빠짐
        lst = (await c.get("/api/v1/image-verifications/reviews/pending")).json()
        assert dec["data"]["id"] not in [it["id"] for it in lst["data"]]
        # 상세 조회
        detail = (await c.get(f"/api/v1/image-verifications/reviews/{rid}")).json()
        assert detail["data"]["review_status"] == "approved"


@pytest.mark.anyio
async def test_api_review_decision_needs_retake_and_rejected():
    for decision in ("needs_retake", "rejected"):
        secondary_review_store.clear()
        rid = (await _post_verify("water", _water_verified_analysis())).json()["data"]["verification_id"]
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            dec = (await c.post(
                f"/api/v1/image-verifications/reviews/{rid}/decision",
                json={"decision": decision},
            )).json()
        assert dec["data"]["review_status"] == decision


@pytest.mark.anyio
async def test_api_review_unknown_id_404():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/v1/image-verifications/reviews/does-not-exist")
        assert r.status_code == 404
