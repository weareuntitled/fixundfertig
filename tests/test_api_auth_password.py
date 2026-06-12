"""Tests für /api/auth/password (Passwort ändern)."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

importlib.import_module("app.api")

auth_module = importlib.import_module("auth")
dependencies_module = importlib.import_module("dependencies")
build_auth_router = getattr(auth_module, "router", None)


def _build_test_app() -> FastAPI:
    app = FastAPI()
    if build_auth_router is not None:
        app.include_router(build_auth_router)
    return app


def _db_session_override(mock_session):
    def override():
        yield mock_session
    return override


@pytest.fixture
def auth_app():
    app = _build_test_app()
    app.dependency_overrides[dependencies_module.require_session_auth] = lambda: 1
    return app


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_change_password_succeeds(auth_app, monkeypatch) -> None:
    captured: dict = {}

    def fake_change_password(*, user_id, current_password, new_password):
        captured["user_id"] = user_id
        captured["current_password"] = current_password
        captured["new_password"] = new_password

    monkeypatch.setattr(auth_module, "change_password", fake_change_password)
    response = TestClient(auth_app).post(
        "/api/auth/password",
        json={"current_password": "old123", "new_password": "new456"},
    )
    assert response.status_code == 204, response.text
    assert captured["user_id"] == 1
    assert captured["current_password"] == "old123"
    assert captured["new_password"] == "new456"


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_change_password_rejects_wrong_current(auth_app, monkeypatch) -> None:
    def fake_change_password(*, user_id, current_password, new_password):
        raise ValueError("Current password is incorrect")

    monkeypatch.setattr(auth_module, "change_password", fake_change_password)
    response = TestClient(auth_app).post(
        "/api/auth/password",
        json={"current_password": "wrong", "new_password": "new456"},
    )
    assert response.status_code == 400
    assert "incorrect" in response.json()["detail"].lower()


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_change_password_propagates_service_error(auth_app, monkeypatch) -> None:
    """Wenn der Service einen ValueError wirft (z.B. 'New password is required'),
    wird 400 zurückgegeben."""
    def fake_change_password(*, user_id, current_password, new_password):
        raise ValueError("New password is required")

    monkeypatch.setattr(auth_module, "change_password", fake_change_password)
    response = TestClient(auth_app).post(
        "/api/auth/password",
        json={"current_password": "old", "new_password": "validlength"},
    )
    assert response.status_code == 400
    assert "required" in response.json()["detail"].lower()


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_change_password_validates_too_short(auth_app) -> None:
    """new_password < 6 Zeichen wird von Pydantic mit 422 abgelehnt (vor dem Service-Call)."""
    response = TestClient(auth_app).post(
        "/api/auth/password",
        json={"current_password": "old", "new_password": "x"},
    )
    assert response.status_code == 422


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_change_password_requires_auth():
    app = _build_test_app()

    def _unauth():
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth required")

    app.dependency_overrides[dependencies_module.require_session_auth] = _unauth
    response = TestClient(app).post(
        "/api/auth/password",
        json={"current_password": "old", "new_password": "new"},
    )
    assert response.status_code == 401
