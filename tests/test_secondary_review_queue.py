"""secondary_review 큐 운영 흐름 테스트 (DB-backed service + API).

water verified → DB pending 등록 → 목록/상세 조회 → 결정(approved/rejected/needs_retake) 영속화.
exercise/study verified 는 큐에 들어가지 않음. Rule Engine core/final_result enum 미변경.
isolated temp SQLite(get_db override) — test_todo.py 와 동일 패턴.
"""
from io import BytesIO

import httpx
import pytest
from PIL import Image
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from backend.main import app
from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.database.schema.image_verification_schema import (
    ImageObjectObservation,
    ImageVerificationData,
    RuleEvidence,
    RuleScoreBreakdown,
    VisionAnalysis,
)
from backend.services import secondary_review_service as review_svc
from backend.services.image_verification_service import apply_secondary_review_policy
from backend.services.vision_analyzer import MockVisionAnalyzer


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def db_session(tmp_path):
    """isolated temp SQLite + get_db override (test_todo 패턴)."""
    db_file = tmp_path / "review.db"
    apply_schema_to_sqlite_file(db_file)
    engine = create_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.pop(get_db, None)


def _image_bytes():
    buf = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buf, format="JPEG")
    buf.seek(0)
    return buf


def _mk(task, result):
    return ImageVerificationData(
        verification_type=task, result=result, score=65, mandatory_passed=True,
        score_breakdown=RuleScoreBreakdown(), vlm_analysis=VisionAnalysis(),
        rule_evidence=[RuleEvidence(code="object:cup", message="cup 객체가 확인되었습니다.", score_delta=15)],
    )


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


# --------------------------------------------------------------------------- service (DB)
def test_service_register_persists_pending(db_session):
    wv = apply_secondary_review_policy(_mk("water", "verified"))
    assert wv.review_required and wv.review_status == "pending"
    rid = review_svc.register(db_session, wv)
    pend = review_svc.list_pending(db_session)
    assert [p.id for p in pend] == [rid]
    rec = review_svc.get(db_session, rid)
    assert rec.review_status == "pending"
    assert rec.rule_evidence and rec.rule_evidence[0].code == "object:cup"


def test_service_decide_persists_and_removes_from_pending(db_session):
    rid = review_svc.register(db_session, apply_secondary_review_policy(_mk("water", "verified")))
    rec = review_svc.decide(db_session, rid, "approved", note="ok", reviewer_id="admin")
    assert rec.review_status == "approved"
    assert rec.review_decision == "approved"
    assert rec.reviewer_id == "admin" and rec.review_note == "ok"
    assert rec.reviewed_at is not None
    assert review_svc.list_pending(db_session) == []
    # 영속화 확인: 재조회
    assert review_svc.get(db_session, rid).review_status == "approved"


def test_service_register_blocks_non_review(db_session):
    ev = apply_secondary_review_policy(_mk("exercise", "verified"))
    assert ev.review_required is False and ev.review_status == "none"
    with pytest.raises(ValueError):
        review_svc.register(db_session, ev)


def test_service_decide_unknown_id_raises(db_session):
    with pytest.raises(KeyError):
        review_svc.decide(db_session, "nope", "approved")


# --------------------------------------------------------------------------- API (DB)
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


@pytest.mark.anyio
async def test_api_water_verified_persisted_and_listed(db_session):
    data = (await _post_verify("water", _water_verified_analysis())).json()["data"]
    assert data["result"] == "verified"
    assert data["review_required"] is True
    assert data["review_status"] == "pending"
    assert data["verification_id"]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        lst = (await c.get("/api/v1/image-verifications/reviews/pending")).json()
    assert data["verification_id"] in [it["id"] for it in lst["data"]]


@pytest.mark.anyio
async def test_api_exercise_verified_not_in_queue(db_session):
    data = (await _post_verify("exercise", _exercise_verified_analysis(),
                               {"activity_type": "home_workout"})).json()["data"]
    assert data["result"] == "verified"
    assert data["review_required"] is False
    assert data["review_status"] == "none"
    assert data["verification_id"] is None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        lst = (await c.get("/api/v1/image-verifications/reviews/pending")).json()
    assert lst["data"] == []


@pytest.mark.anyio
async def test_api_decision_approved_persists(db_session):
    rid = (await _post_verify("water", _water_verified_analysis())).json()["data"]["verification_id"]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        dec = (await c.post(f"/api/v1/image-verifications/reviews/{rid}/decision",
                            json={"decision": "approved", "note": "admin ok", "reviewer_id": "admin1"})).json()
        assert dec["data"]["review_status"] == "approved"
        assert dec["data"]["review_decision"] == "approved"
        assert dec["data"]["reviewed_at"]
        lst = (await c.get("/api/v1/image-verifications/reviews/pending")).json()
        assert rid not in [it["id"] for it in lst["data"]]
        detail = (await c.get(f"/api/v1/image-verifications/reviews/{rid}")).json()
        assert detail["data"]["review_status"] == "approved"
        assert detail["data"]["review_note"] == "admin ok"


@pytest.mark.anyio
async def test_api_decision_rejected_and_needs_retake(db_session):
    for decision in ("rejected", "needs_retake"):
        rid = (await _post_verify("water", _water_verified_analysis())).json()["data"]["verification_id"]
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            dec = (await c.post(f"/api/v1/image-verifications/reviews/{rid}/decision",
                                json={"decision": decision})).json()
        assert dec["data"]["review_status"] == decision


@pytest.mark.anyio
async def test_api_review_unknown_id_404(db_session):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/v1/image-verifications/reviews/does-not-exist")
        assert r.status_code == 404
