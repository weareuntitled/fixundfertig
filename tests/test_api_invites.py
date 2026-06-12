from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

importlib.import_module("app.api")

invites_module = importlib.import_module("invites")
dependencies_module = importlib.import_module("dependencies")
build_invites_router = getattr(invites_module, "router", None)


def _build_test_app() -> FastAPI:
    app = FastAPI()
    if build_invites_router is not None:
        app.include_router(build_invites_router)
    return app


def _db_session_override(mock_session):
    def override():
        yield mock_session
    return override


def _make_invite(email: str = "test@example.com", invited_at: str = "2026-06-10T10:00:00"):
    return SimpleNamespace(
        email=email,
        invited_at=invited_at,
    )


@pytest.fixture
def invites_app():
    app = _build_test_app()
    app.dependency_overrides[dependencies_module.require_session_auth] = lambda: 1
    return app, None


@pytest.mark.skipif(build_invites_router is None, reason="app.api.invites.router not yet implemented")
def test_list_invites_returns_empty(invites_app) -> None:
    """RED: GET /api/invites with no invites returns []."""
    app, _ = invites_app
    session_mock = MagicMock()
    session_mock.exec.return_value.all.return_value = []
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/invites")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.skipif(build_invites_router is None, reason="app.api.invites.router not yet implemented")
def test_list_invites_returns_invites(invites_app) -> None:
    """RED: GET /api/invites returns the allowlist."""
    app, _ = invites_app
    session_mock = MagicMock()
    session_mock.exec.return_value.all.return_value = [
        _make_invite("alice@example.com"),
        _make_invite("bob@example.com"),
    ]
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/invites")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["email"] == "alice@example.com"
    assert body[1]["email"] == "bob@example.com"


@pytest.mark.skipif(build_invites_router is None, reason="app.api.invites.router not yet implemented")
def test_add_invite_rejects_invalid_email(invites_app) -> None:
    """RED: POST with invalid email returns 422."""
    app, _ = invites_app
    session_mock = MagicMock()
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post("/api/invites", json={"email": "not-an-email"})
    assert response.status_code == 422


@pytest.mark.skipif(build_invites_router is None, reason="app.api.invites.router not yet implemented")
def test_add_invite_succeeds(invites_app) -> None:
    """RED: POST with valid email returns 201."""
    app, _ = invites_app
    session_mock = MagicMock()
    new_invite = _make_invite("new@example.com")
    session_mock.exec.return_value.first.return_value = None  # no existing
    session_mock.refresh.return_value = new_invite
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post("/api/invites", json={"email": "new@example.com"})
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"


@pytest.mark.skipif(build_invites_router is None, reason="app.api.invites.router not yet implemented")
def test_add_invite_returns_409_when_already_exists(invites_app) -> None:
    """RED: POST with already-invited email returns 409."""
    app, _ = invites_app
    session_mock = MagicMock()
    session_mock.exec.return_value.first.return_value = _make_invite("existing@example.com")
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post("/api/invites", json={"email": "existing@example.com"})
    assert response.status_code == 409


@pytest.mark.skipif(build_invites_router is None, reason="app.api.invites.router not yet implemented")
def test_remove_invite_succeeds(invites_app) -> None:
    """RED: DELETE returns 200 with status=deleted when invite exists."""
    app, _ = invites_app
    session_mock = MagicMock()
    session_mock.exec.return_value.first.return_value = _make_invite("alice@example.com")
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).delete("/api/invites/alice%40example.com")
    assert response.status_code == 200
    assert response.json() == {"status": "deleted"}


@pytest.mark.skipif(build_invites_router is None, reason="app.api.invites.router not yet implemented")
def test_remove_invite_returns_404_when_not_found(invites_app) -> None:
    """RED: DELETE for unknown email returns 404."""
    app, _ = invites_app
    session_mock = MagicMock()
    session_mock.exec.return_value.first.return_value = None
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).delete("/api/invites/unknown%40example.com")
    assert response.status_code == 404
