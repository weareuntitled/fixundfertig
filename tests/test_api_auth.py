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

# Make sure `app/api/__init__.py` runs (sets up sys.path for top-level imports)
# before any submodule import.
importlib.import_module("app.api")

auth_module = importlib.import_module("auth")
dependencies_module = importlib.import_module("dependencies")
schemas_auth = importlib.import_module("schemas.auth")
build_auth_router = getattr(auth_module, "router", None)


def _build_test_app() -> FastAPI:
    app = FastAPI()
    if build_auth_router is not None:
        app.include_router(build_auth_router)
    return app


def _make_user(user_id: int = 1, email: str = "owner@example.com"):
    """Create a User-like object with concrete attributes (Pydantic can validate it)."""
    return SimpleNamespace(
        id=user_id,
        email=email,
        first_name="Owner",
        last_name="User",
        is_active=True,
        email_verified=True,
    )


def _db_session_override(mock_session):
    """Returns a generator function suitable for FastAPI dependency_overrides.

    FastAPI's db_session is a generator (yields a session), so the override
    must yield too — not return a bare session object.
    """
    def override():
        yield mock_session
    return override


@pytest.fixture
def auth_app():
    """Auth-API app with no auth requirements (testing login flow)."""
    app = _build_test_app()
    return app


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_login_validates_email_format(auth_app) -> None:
    response = TestClient(auth_app).post("/api/auth/login", json={"email": "bad", "password": "x"})
    assert response.status_code == 422


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_login_rejects_unknown_fields(auth_app) -> None:
    response = TestClient(auth_app).post(
        "/api/auth/login", json={"email": "x@y.de", "password": "secret", "role": "admin"}
    )
    assert response.status_code == 422


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_login_returns_401_for_invalid_credentials(auth_app, monkeypatch) -> None:
    import services.auth as services_auth_module
    monkeypatch.setattr(services_auth_module, "verify_password", lambda *_: False)
    response = TestClient(auth_app).post(
        "/api/auth/login", json={"email": "x@y.de", "password": "wrong"}
    )
    assert response.status_code == 401


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_login_success_sets_cookies_and_returns_user_and_csrf(auth_app, monkeypatch) -> None:
    user = _make_user(user_id=42, email="owner@example.com")
    # Patch the source module so the lazy import inside the endpoint picks up the mock.
    import services.auth as services_auth_module
    monkeypatch.setattr(services_auth_module, "verify_password", lambda *_: True)
    monkeypatch.setattr(services_auth_module, "is_identifier_allowed", lambda *_: True)

    session_mock = MagicMock()
    session_mock.exec.return_value.first.return_value = user
    app = auth_app
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)

    response = TestClient(app).post(
        "/api/auth/login", json={"email": "owner@example.com", "password": "secret"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] == "owner@example.com"
    assert body["csrf_token"], "csrf_token must be present in response body"
    set_cookie_headers = response.headers.get_list("set-cookie")
    cookie_names = [h.split("=", 1)[0] for h in set_cookie_headers]
    assert "ff_session" in cookie_names
    assert "ff_csrf" in cookie_names


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_logout_clears_cookies(auth_app) -> None:
    response = TestClient(auth_app).post("/api/auth/logout")
    assert response.status_code in (200, 204)
    set_cookie_headers = response.headers.get_list("set-cookie")
    cleared = any("ff_session" in h and ("Max-Age=0" in h or "expires=" in h.lower()) for h in set_cookie_headers)
    assert cleared, f"ff_session cookie not cleared: {set_cookie_headers}"


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_me_returns_user_when_authenticated(auth_app) -> None:
    user = _make_user()
    session_mock = MagicMock()
    session_mock.get.return_value = user
    app = auth_app
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)

    with TestClient(app) as client:
        token = auth_module.create_session_token(1)
        client.cookies.set("ff_session", token)
        response = client.get("/api/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == user.email


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_me_returns_401_without_session_cookie(auth_app) -> None:
    response = TestClient(auth_app).get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_session_token_round_trip() -> None:
    user_id = 99
    token = auth_module.create_session_token(user_id)
    loaded = auth_module.load_session_token(token)
    assert loaded == user_id


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_session_token_rejects_tampered_value() -> None:
    with pytest.raises(Exception):
        auth_module.load_session_token("not.a.valid.token")


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_session_token_rejects_expired() -> None:
    # Create a token with very short max_age, then sleep so it expires.
    # itsdangerous uses second-resolution timestamps.
    token = auth_module.create_session_token(99, max_age_seconds=1)
    import time
    time.sleep(2.5)
    with pytest.raises(Exception):
        auth_module.load_session_token(token, max_age_seconds=1)


@pytest.mark.skipif(build_auth_router is None, reason="app.api.auth.router not yet implemented")
def test_csrf_token_round_trip() -> None:
    user_id = 42
    token = auth_module.create_csrf_token(user_id)
    assert auth_module.verify_csrf_token(token, user_id) is True
    assert auth_module.verify_csrf_token(token, user_id + 1) is False
