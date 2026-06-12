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

exports_module = importlib.import_module("exports")
dependencies_module = importlib.import_module("dependencies")
build_exports_router = getattr(exports_module, "router", None)


def _build_test_app() -> FastAPI:
    app = FastAPI()
    if build_exports_router is not None:
        app.include_router(build_exports_router)
    return app


@pytest.fixture
def exports_app():
    """FastAPI app with auth + company deps overridden (no storage_secret required)."""
    app = _build_test_app()
    app.dependency_overrides[exports_module.require_session_auth] = lambda: 1
    app.dependency_overrides[exports_module.get_current_company] = lambda: SimpleNamespace(id=1)
    return app, None


def _patch(monkeypatch, attr_name: str, fake_value):
    """Patch a logic symbol through the exports module's imported binding."""
    monkeypatch.setattr(exports_module, attr_name, fake_value)


# ----------------------- customers-csv -----------------------

@pytest.mark.skipif(build_exports_router is None, reason="app.api.exports.router not yet implemented")
def test_customers_csv_returns_csv_with_attachment_header(exports_app, monkeypatch) -> None:
    """RED: GET /api/exports/customers-csv returns CSV + correct headers."""
    app, _ = exports_app
    _patch(monkeypatch, "export_customers_csv", lambda session, company_id: b"id,name\n1,ACME\n")
    response = TestClient(app).get("/api/exports/customers-csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    cd = response.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert "filename=" in cd
    assert response.content == b"id,name\n1,ACME\n"


# ----------------------- invoices-csv -----------------------

@pytest.mark.skipif(build_exports_router is None, reason="app.api.exports.router not yet implemented")
def test_invoices_csv_returns_csv_with_year_in_filename(exports_app, monkeypatch) -> None:
    """RED: GET /api/exports/invoices-csv?year=2025 returns CSV with year in filename."""
    app, _ = exports_app
    _patch(monkeypatch, "export_invoices_csv", lambda session, company_id, year: f"year={year}\n".encode())
    response = TestClient(app).get("/api/exports/invoices-csv?year=2025")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "invoices-2025.csv" in response.headers.get("content-disposition", "")
    assert response.content == b"year=2025\n"


@pytest.mark.skipif(build_exports_router is None, reason="app.api.exports.router not yet implemented")
def test_invoices_csv_defaults_to_current_year_when_no_year_param(exports_app, monkeypatch) -> None:
    """RED: GET /api/exports/invoices-csv without year param uses current year."""
    from datetime import datetime
    app, _ = exports_app
    captured: dict = {}
    def capture(session, company_id, year):
        captured["year"] = year
        return b""
    _patch(monkeypatch, "export_invoices_csv", capture)
    TestClient(app).get("/api/exports/invoices-csv")
    assert captured["year"] == datetime.now().year


# ----------------------- items-csv -----------------------

@pytest.mark.skipif(build_exports_router is None, reason="app.api.exports.router not yet implemented")
def test_items_csv_returns_csv(exports_app, monkeypatch) -> None:
    """RED: GET /api/exports/items-csv returns CSV."""
    app, _ = exports_app
    _patch(monkeypatch, "export_invoice_items_csv", lambda session, company_id, year: b"item_id,description\n1,Design\n")
    response = TestClient(app).get("/api/exports/items-csv?year=2025")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "items-2025.csv" in response.headers.get("content-disposition", "")
    assert response.content == b"item_id,description\n1,Design\n"


# ----------------------- invoices-pdf (ZIP) -----------------------

@pytest.mark.skipif(build_exports_router is None, reason="app.api.exports.router not yet implemented")
def test_invoices_pdf_returns_zip_with_attachment_header(exports_app, monkeypatch) -> None:
    """RED: GET /api/exports/invoices-pdf returns ZIP with correct content-type."""
    app, _ = exports_app
    _patch(monkeypatch, "export_invoices_pdf_zip", lambda session, company_id, year: b"PK\x03\x04fake-zip")
    response = TestClient(app).get("/api/exports/invoices-pdf?year=2025")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "invoices-2025.zip" in response.headers.get("content-disposition", "")
    assert response.content == b"PK\x03\x04fake-zip"


# ----------------------- db-backup (ZIP) -----------------------

@pytest.mark.skipif(build_exports_router is None, reason="app.api.exports.router not yet implemented")
def test_db_backup_returns_zip_with_date_in_filename(exports_app, monkeypatch) -> None:
    """RED: GET /api/exports/db-backup returns ZIP with today's date in filename."""
    from datetime import datetime
    app, _ = exports_app
    _patch(monkeypatch, "export_database_backup", lambda session, company_id: b"PK\x03\x04fake-zip")
    response = TestClient(app).get("/api/exports/db-backup")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    today = datetime.now().strftime("%Y-%m-%d")
    assert f"backup-{today}.zip" in response.headers.get("content-disposition", "")
    assert response.content == b"PK\x03\x04fake-zip"
