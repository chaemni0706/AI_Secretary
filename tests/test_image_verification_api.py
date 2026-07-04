from io import BytesIO
from pathlib import Path

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
from backend.services.image_verification_service import verify_image_upload


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _post_multipart(data, files):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/v1/image-verifications", data=data, files=files)


def _image_bytes(fmt="JPEG"):
    buffer = BytesIO()
    Image.new("RGB", (4, 4), color="white").save(buffer, format=fmt)
    buffer.seek(0)
    return buffer


@pytest.mark.anyio
async def test_image_verification_multipart_uses_mock_analyzer(monkeypatch):
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        scene="desk",
        objects=[
            ImageObjectObservation(label="book", confidence=0.9),
            ImageObjectObservation(label="forbidden_label", confidence=0.9),
        ],
        visible_text=["chapter 1"],
        study_visual_evidence=["open_textbook", "handwritten_notes", "highlighted_text"],
    )
    monkeypatch.setattr(
        "backend.services.image_verification_service.get_default_vision_analyzer",
        lambda: MockVisionAnalyzer(analysis),
    )

    response = await _post_multipart(
        data={"verification_type": "study"},
        files={"file": ("study.jpg", _image_bytes("JPEG"), "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["verification_type"] == "study"
    assert data["result"] == "verified"
    assert [obj["label"] for obj in data["vlm_analysis"]["objects"]] == ["book"]


@pytest.mark.anyio
async def test_fake_jpeg_bytes_return_422(monkeypatch):
    monkeypatch.setattr(
        "backend.services.image_verification_service.get_default_vision_analyzer",
        lambda: MockVisionAnalyzer(VisionAnalysis()),
    )

    response = await _post_multipart(
        data={"verification_type": "study"},
        files={"file": ("fake.jpg", BytesIO(b"not-a-real-jpeg"), "image/jpeg")},
    )

    assert response.status_code == 422
    assert response.json()["success"] is False


@pytest.mark.anyio
async def test_image_verification_rejects_non_image_content_type():
    response = await _post_multipart(
        data={"verification_type": "water"},
        files={"file": ("note.txt", BytesIO(b"hello"), "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["success"] is False


@pytest.mark.anyio
async def test_exercise_requires_activity_type():
    response = await _post_multipart(
        data={"verification_type": "exercise"},
        files={"file": ("exercise.jpg", _image_bytes("JPEG"), "image/jpeg")},
    )

    assert response.status_code == 422
    assert response.json()["success"] is False


@pytest.mark.anyio
async def test_exercise_rejects_unknown_activity_type():
    response = await _post_multipart(
        data={"verification_type": "exercise", "activity_type": "cycling"},
        files={"file": ("exercise.jpg", _image_bytes("JPEG"), "image/jpeg")},
    )

    assert response.status_code == 422
    assert response.json()["success"] is False


@pytest.mark.anyio
async def test_exercise_multipart_uses_activity_type_and_mock_analyzer(monkeypatch):
    analysis = VisionAnalysis(
        quality=ImageQuality(usable=True),
        objects=[
            ImageObjectObservation(label="weight_machine", confidence=0.9),
            ImageObjectObservation(label="book", confidence=0.9),
        ],
        exercise_visual_evidence=["gym_environment", "weight_machine_present"],
    )
    monkeypatch.setattr(
        "backend.services.image_verification_service.get_default_vision_analyzer",
        lambda: MockVisionAnalyzer(analysis),
    )

    response = await _post_multipart(
        data={"verification_type": "exercise", "activity_type": "gym"},
        files={"file": ("exercise.jpg", _image_bytes("JPEG"), "image/jpeg")},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["verification_type"] == "exercise"
    assert data["result"] == "verified"
    assert data["vlm_analysis"]["exercise_visual_evidence"] == ["gym_environment", "weight_machine_present"]
    assert [obj["label"] for obj in data["vlm_analysis"]["objects"]] == ["weight_machine"]


@pytest.mark.anyio
async def test_temp_file_is_deleted_after_success(monkeypatch):
    seen_path = {}

    class RecordingAnalyzer:
        def analyze(self, image_path, verification_type, allowed_labels):
            seen_path["path"] = Path(image_path)
            assert seen_path["path"].exists()
            return VisionAnalysis(
                quality=ImageQuality(usable=True),
                scene="table",
                objects=[ImageObjectObservation(label="water_bottle", confidence=0.9)],
            )

    monkeypatch.setattr(
        "backend.services.image_verification_service.get_default_vision_analyzer",
        lambda: RecordingAnalyzer(),
    )

    response = await _post_multipart(
        data={"verification_type": "water"},
        files={"file": ("water.png", _image_bytes("PNG"), "image/png")},
    )

    assert response.status_code == 200
    assert seen_path["path"].exists() is False


@pytest.mark.parametrize(
    "exc",
    [
        RuntimeError("VLM call failed"),
        TimeoutError("VLM timeout"),
        ValueError("Structured Output validation failed"),
    ],
)
def test_temp_file_is_deleted_after_vlm_failure(exc):
    seen_path = {}

    class FailingAnalyzer:
        def analyze(self, image_path, verification_type, allowed_labels):
            seen_path["path"] = Path(image_path)
            assert seen_path["path"].exists()
            raise exc

    with pytest.raises(type(exc)):
        verify_image_upload(
            _image_bytes("JPEG"),
            filename="study.jpg",
            content_type="image/jpeg",
            verification_type="study",
            analyzer=FailingAnalyzer(),
        )

    assert seen_path["path"].exists() is False
