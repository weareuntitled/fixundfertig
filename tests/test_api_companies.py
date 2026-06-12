"""Tests für /api/company GET + PUT (Firmenstammdaten).

TDD: erst Tests (RED), dann Implementierung in `app/api/companies.py`.
"""
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

companies_module = importlib.import_module("companies")
dependencies_module = importlib.import_module("dependencies")
build_companies_router = getattr(companies_module, "router", None)


def _build_test_app() -> FastAPI:
    app = FastAPI()
    if build_companies_router is not None:
        app.include_router(build_companies_router)
    return app


def _db_session_override(mock_session):
    def override():
        yield mock_session
    return override


def _make_company(company_id: int = 1, name: str = "Test GmbH") -> SimpleNamespace:
    return SimpleNamespace(
        id=company_id,
        name=name,
        user_id=1,
        first_name="",
        last_name="",
        business_type="",
        is_small_business=False,
        street="",
        postal_code="",
        city="",
        country="Deutschland",
        email="firma@example.com",
        phone="",
        iban="",
        bic="",
        bank_name="",
        tax_id="",
        vat_id="",
        smtp_server="",
        smtp_port=0,
        smtp_user="",
        smtp_password="",
        default_sender_email="",
        n8n_webhook_url="",
        n8n_webhook_url_test="",
        n8n_webhook_url_prod="",
        n8n_secret="",
        n8n_enabled=False,
        google_drive_folder_id="",
        next_invoice_nr=1,
        invoice_number_template="RE-{year}-{nr:04d}",
        invoice_filename_template="rechnung-{nr}.pdf",
    )


@pytest.fixture
def companies_app():
    app = _build_test_app()
    app.dependency_overrides[dependencies_module.require_session_auth] = lambda: 1
    return app


@pytest.mark.skipif(build_companies_router is None, reason="app.api.companies.router not yet implemented")
def test_get_company_returns_current_company(companies_app) -> None:
    app = companies_app
    comp = _make_company()
    app.dependency_overrides[dependencies_module.get_current_company] = lambda: comp
    response = TestClient(app).get("/api/company")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == 1
    assert body["name"] == "Test GmbH"


@pytest.mark.skipif(build_companies_router is None, reason="app.api.companies.router not yet implemented")
def test_get_company_requires_auth():
    app = _build_test_app()

    def _unauth():
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth required")

    app.dependency_overrides[dependencies_module.require_session_auth] = _unauth
    response = TestClient(app).get("/api/company")
    assert response.status_code == 401


@pytest.mark.skipif(build_companies_router is None, reason="app.api.companies.router not yet implemented")
def test_put_company_updates_fields(companies_app, monkeypatch) -> None:
    """PUT /api/company mit Patch → update_company aufgerufen mit nur erlaubten Feldern."""
    app = companies_app
    comp = _make_company()

    captured: dict = {}

    def fake_update_company(user_id, company_id, patch):
        captured["user_id"] = user_id
        captured["company_id"] = company_id
        captured["patch"] = patch
        comp.name = patch.get("name", comp.name)
        return comp

    monkeypatch.setattr(companies_module, "update_company", fake_update_company)
    app.dependency_overrides[dependencies_module.get_current_company] = lambda: comp

    response = TestClient(app).put(
        "/api/company",
        json={"name": "Neue Firma GmbH", "street": "Musterweg 5", "evil_field": "x"},
    )
    assert response.status_code == 200, response.text
    assert captured["user_id"] == 1
    assert captured["company_id"] == 1
    assert captured["patch"]["name"] == "Neue Firma GmbH"
    assert captured["patch"]["street"] == "Musterweg 5"
    assert "evil_field" not in captured["patch"]  # nicht erlaubt


@pytest.mark.skipif(build_companies_router is None, reason="app.api.companies.router not yet implemented")
def test_put_company_handles_company_not_found(companies_app, monkeypatch) -> None:
    app = companies_app
    comp = _make_company()

    def fake_update_company(user_id, company_id, patch):
        raise ValueError("Company not found for user.")

    monkeypatch.setattr(companies_module, "update_company", fake_update_company)
    app.dependency_overrides[dependencies_module.get_current_company] = lambda: comp

    response = TestClient(app).put("/api/company", json={"name": "X"})
    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower()
