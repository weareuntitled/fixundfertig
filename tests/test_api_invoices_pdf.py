"""Tests für /api/invoices/{id}/preview-pdf und /download Endpoints.

Diese Endpoints werden für die React-Detail-Page gebraucht:
- preview-pdf: Server-PDF der finalisierten Rechnung (Bytes-Stream)
- download: Wie preview-pdf, aber mit Content-Disposition: attachment
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

invoices_module = importlib.import_module("invoices")
dependencies_module = importlib.import_module("dependencies")
build_invoices_router = getattr(invoices_module, "router", None)


def _build_test_app() -> FastAPI:
    app = FastAPI()
    if build_invoices_router is not None:
        app.include_router(build_invoices_router)
    return app


def _db_session_override(mock_session):
    def override():
        yield mock_session
    return override


def _make_invoice_with_pdf(invoice_id: int = 1, pdf_bytes: bytes = b"%PDF-1.4\ntest"):
    return SimpleNamespace(
        id=invoice_id,
        customer_id=1,
        nr="RE-2026-0001",
        title="Test-Rechnung",
        date="2026-06-10",
        delivery_date="",
        recipient_name="Max Mustermann",
        recipient_street="",
        recipient_postal_code="",
        recipient_city="",
        total_brutto=119.0,
        status="OPEN",
        revision_nr=0,
        updated_at="",
        related_invoice_id=None,
        items=[],
        pdf_filename="test.pdf",
        pdf_bytes=pdf_bytes,
    )


@pytest.fixture
def invoices_app():
    app = _build_test_app()
    app.dependency_overrides[dependencies_module.require_session_auth] = lambda: 1
    return app


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_preview_pdf_returns_pdf_bytes_for_existing_invoice(invoices_app) -> None:
    """RED: GET /api/invoices/{id}/preview-pdf muss 200 + application/pdf liefern."""
    app = invoices_app
    invoice = _make_invoice_with_pdf(7)
    session_mock = MagicMock()
    session_mock.get.return_value = invoice
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/invoices/7/preview-pdf")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_preview_pdf_returns_404_for_unknown_invoice(invoices_app) -> None:
    app = invoices_app
    session_mock = MagicMock()
    session_mock.get.return_value = None
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/invoices/999/preview-pdf")
    assert response.status_code == 404


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_preview_pdf_renders_fallback_when_pdf_bytes_missing(invoices_app, monkeypatch) -> None:
    """Falls invoice.pdf_bytes leer ist, fällt der Endpoint auf render_invoice_to_pdf_bytes zurück."""
    app = invoices_app
    invoice = SimpleNamespace(
        id=7,
        pdf_filename="",
        pdf_bytes=b"",
        items=[],
    )
    fake_pdf = b"%PDF-1.4\nrendered-on-demand"
    monkeypatch.setattr(invoices_module, "render_invoice_to_pdf_bytes", lambda *a, **k: fake_pdf)
    session_mock = MagicMock()
    session_mock.get.return_value = invoice
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/invoices/7/preview-pdf")
    assert response.status_code == 200
    assert response.content == fake_pdf


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_download_returns_pdf_with_attachment_header(invoices_app) -> None:
    """RED: GET /api/invoices/{id}/download muss Content-Disposition: attachment senden."""
    app = invoices_app
    invoice = _make_invoice_with_pdf(7, pdf_bytes=b"%PDF-1.4\ndownload-test")
    session_mock = MagicMock()
    session_mock.get.return_value = invoice
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/invoices/7/download")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    cd = response.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert ".pdf" in cd


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_download_returns_404_for_unknown_invoice(invoices_app) -> None:
    app = invoices_app
    session_mock = MagicMock()
    session_mock.get.return_value = None
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/invoices/999/download")
    assert response.status_code == 404
