"""Shared pytest fixtures: a FastAPI TestClient against backend.main:app.

Run from project root:  pytest -q
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


NOW = "2026-06-29T10:00:00+09:00"
MD = "2026-06-30"
