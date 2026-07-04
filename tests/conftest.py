"""Shared pytest fixtures and helpers.

A session-scoped FastAPI TestClient plus reusable contract helpers:
- `check_envelope`: assert the common {success, message, data} envelope.
- `post`: POST a payload, assert status + envelope, return the parsed body.

Run from project root:  python -m pytest -v
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

NOW = "2026-06-29T10:00:00+09:00"   # a Monday, for deterministic relative dates
MD = "2026-06-30"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def check_envelope():
    """Return a function asserting the common API response envelope."""
    def _check(body, *, success=True):
        assert {"success", "message", "data"}.issubset(body.keys()), body
        assert isinstance(body["success"], bool)
        assert body["success"] is success
        assert isinstance(body["message"], str) and body["message"]
        if success:
            assert body["data"] is not None
        return body["data"]
    return _check


@pytest.fixture
def post(client, check_envelope):
    """POST helper: assert status code + envelope, return the JSON body."""
    def _post(path, payload, *, success=True, status_code=200):
        r = client.post(path, json=payload)
        assert r.status_code == status_code, (path, r.status_code, r.text)
        body = r.json()
        check_envelope(body, success=success)
        return body
    return _post
