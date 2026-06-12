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

customers_module = importlib.import_module("app.api.customers")
dependencies_module = importlib.import_module("dependencies")
build_customers_router = getattr(customers_module, "router", None)


def _build_test_app() -> FastAPI:
    app = FastAPI()
    if build_customers_router is not None:
        app.include_router(build_customers_router)
    return app


def _make_company_stub(company_id: int = 1):
    comp = MagicMock()
    comp.id = company_id
    return comp


def _make_session():
    session = MagicMock()
    return session


def _db_session_override(mock_session):
    """Returns a generator function suitable for FastAPI dependency_overrides."""
    def override():
        yield mock_session
    return override


@pytest.fixture
def authenticated_app():
    """FastAPI app with auth + DB dependencies overridden (no real storage/secrets needed)."""
    app = _build_test_app()
    app.dependency_overrides[dependencies_module.require_session_auth] = lambda: 1
    app.dependency_overrides[dependencies_module.get_current_company] = lambda: _make_company_stub()

    session = _make_session()
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session)
    return app, session


@pytest.mark.skipif(build_customers_router is None, reason="app.api.customers.router not yet implemented")
def test_list_customers_returns_empty_when_no_customers(authenticated_app) -> None:
    app, session = authenticated_app
    session.exec.return_value.all.return_value = []
    response = TestClient(app).get("/api/customers")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.skipif(build_customers_router is None, reason="app.api.customers.router not yet implemented")
def test_create_customer_validates_payload(authenticated_app) -> None:
    app, _ = authenticated_app
    response = TestClient(app).post("/api/customers", json={"name": "X", "email": "bad-email"})
    assert response.status_code == 422


@pytest.mark.skipif(build_customers_router is None, reason="app.api.customers.router not yet implemented")
def test_create_customer_rejects_unknown_fields(authenticated_app) -> None:
    app, _ = authenticated_app
    response = TestClient(app).post("/api/customers", json={"name": "X", "evil_field": "injection"})
    assert response.status_code == 422


@pytest.mark.skipif(build_customers_router is None, reason="app.api.customers.router not yet implemented")
def test_create_customer_succeeds_with_valid_payload(authenticated_app) -> None:
    from data import Customer
    app, session = authenticated_app
    # Capture the Customer that the endpoint constructs, so we can verify it.
    created: list = []

    def capture_add(obj):
        created.append(obj)
        obj.id = 42  # simulate DB-assigned id

    session.add.side_effect = capture_add
    session.refresh.side_effect = lambda obj: None
    response = TestClient(app).post("/api/customers", json={"name": "Musterfirma", "email": "x@y.de"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Musterfirma"
    assert body["email"] == "x@y.de"
    assert body["kdnr"] == 0
    assert len(created) == 1
    assert isinstance(created[0], Customer)
    assert created[0].company_id == 1


@pytest.mark.skipif(build_customers_router is None, reason="app.api.customers.router not yet implemented")
def test_get_customer_returns_404_when_not_found(authenticated_app) -> None:
    app, session = authenticated_app
    session.get.return_value = None
    response = TestClient(app).get("/api/customers/999")
    assert response.status_code == 404


@pytest.mark.skipif(build_customers_router is None, reason="app.api.customers.router not yet implemented")
def test_update_customer_returns_404_when_not_found(authenticated_app) -> None:
    app, session = authenticated_app
    session.get.return_value = None
    response = TestClient(app).put("/api/customers/999", json={"name": "Updated"})
    assert response.status_code == 404


@pytest.mark.skipif(build_customers_router is None, reason="app.api.customers.router not yet implemented")
def test_delete_customer_returns_404_when_not_found(authenticated_app) -> None:
    app, session = authenticated_app
    session.get.return_value = None
    response = TestClient(app).delete("/api/customers/999")
    assert response.status_code == 404


@pytest.mark.skipif(build_customers_router is None, reason="app.api.customers.router not yet implemented")
def test_delete_customer_returns_409_when_has_invoices(authenticated_app) -> None:
    app, session = authenticated_app
    existing = MagicMock()
    existing.id = 1
    session.get.return_value = existing
    session.exec.return_value.first.return_value = MagicMock()
    response = TestClient(app).delete("/api/customers/1")
    assert response.status_code == 409
