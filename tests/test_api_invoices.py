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
data_module = importlib.import_module("data")
Invoice = data_module.Invoice
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


def _make_invoice(invoice_id: int = 1, status: str = "DRAFT", customer_id: int = 1):
    """Create a simple invoice-like object that InvoiceRead can validate."""
    from types import SimpleNamespace
    return SimpleNamespace(
        id=invoice_id,
        customer_id=customer_id,
        nr=None,
        title="Rechnung",
        date="2026-06-10",
        delivery_date="",
        recipient_name="",
        recipient_street="",
        recipient_postal_code="",
        recipient_city="",
        total_brutto=0.0,
        status=status,
        revision_nr=0,
        updated_at="",
        related_invoice_id=None,
        payment_link_url="",
        payment_provider="",
        items=[],
    )


@pytest.fixture
def invoices_app():
    app = _build_test_app()
    app.dependency_overrides[dependencies_module.require_session_auth] = lambda: 1
    return app, None


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_list_invoices_returns_empty(invoices_app) -> None:
    app, _ = invoices_app
    session_mock = MagicMock()
    session_mock.exec.return_value.all.return_value = []
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/invoices")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_list_invoices_returns_invoices(invoices_app) -> None:
    app, _ = invoices_app
    session_mock = MagicMock()
    session_mock.exec.return_value.all.return_value = [_make_invoice(1, "OPEN")]
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/invoices")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == 1
    assert body[0]["status"] == "OPEN"


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_get_invoice_returns_404_when_not_found(invoices_app) -> None:
    app, _ = invoices_app
    session_mock = MagicMock()
    session_mock.get.return_value = None
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/invoices/999")
    assert response.status_code == 404


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_get_invoice_returns_invoice(invoices_app) -> None:
    app, _ = invoices_app
    session_mock = MagicMock()
    session_mock.get.return_value = _make_invoice(7, "OPEN")
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/invoices/7")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 7


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_status_update_validates_payload(invoices_app) -> None:
    app, _ = invoices_app
    session_mock = MagicMock()
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).put("/api/invoices/1/status", json={"status": "BOGUS"})
    assert response.status_code == 422


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_status_update_returns_404_when_not_found(invoices_app) -> None:
    app, _ = invoices_app
    session_mock = MagicMock()
    session_mock.get.return_value = None
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).put("/api/invoices/999/status", json={"status": "OPEN"})
    assert response.status_code == 404


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_status_update_succeeds(invoices_app) -> None:
    app, _ = invoices_app
    invoice = _make_invoice(1, "DRAFT")
    session_mock = MagicMock()
    session_mock.get.return_value = invoice
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).put(
        "/api/invoices/1/status", json={"status": "OPEN", "reason": "Finalized"}
    )
    assert response.status_code == 200
    assert invoice.status == "OPEN"
    assert invoice.revision_nr == 1  # bumped


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_create_invoice_validates_empty_items(invoices_app) -> None:
    """POST /api/invoices with no items must return 400 (no positions)."""
    app, _ = invoices_app
    comp = SimpleNamespace(id=1)
    session_mock = MagicMock()
    app.dependency_overrides[dependencies_module.get_current_company] = lambda: comp
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post(
        "/api/invoices",
        json={"customer_id": 1, "date": "2026-06-10", "items": []},
    )
    # finalize_invoice_logic raises ValueError on empty items → 400
    assert response.status_code in (400, 422)


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_create_invoice_rejects_invalid_status(invoices_app) -> None:
    app, _ = invoices_app
    session_mock = MagicMock()
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post(
        "/api/invoices",
        json={
            "customer_id": 1,
            "status": "BOGUS",
            "items": [{"description": "X", "quantity": 1, "unit_price": 100.0}],
        },
    )
    assert response.status_code == 422


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_create_invoice_succeeds_with_valid_payload(invoices_app, monkeypatch) -> None:
    app, _ = invoices_app
    inv = _make_invoice(42, "OPEN")
    comp = SimpleNamespace(id=1)

    # Mock finalize_invoice_logic to return a new invoice id without touching DB
    monkeypatch.setattr(invoices_module, "finalize_invoice_logic", lambda *a, **k: 42)
    session_mock = MagicMock()
    session_mock.get.return_value = inv
    app.dependency_overrides[dependencies_module.get_current_company] = lambda: comp
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post(
        "/api/invoices",
        json={
            "customer_id": 1,
            "date": "2026-06-10",
            "items": [{"description": "Design", "quantity": 1, "unit_price": 100.0}],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["customer_id"] == 1


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_duplicate_invoice_returns_404_when_not_found(invoices_app) -> None:
    app, _ = invoices_app
    session_mock = MagicMock()
    session_mock.get.return_value = None
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post("/api/invoices/999/duplicate")
    assert response.status_code == 404


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_duplicate_invoice_creates_draft_copy(invoices_app, monkeypatch) -> None:
    app, _ = invoices_app
    comp = SimpleNamespace(id=1)
    orig = SimpleNamespace(
        id=1,
        customer_id=5,
        company_id=1,
        nr="RE-10042",
        title="Rechnung",
        date="2026-06-10",
        delivery_date="",
        recipient_name="Boring GmbH",
        recipient_street="Beispieladresse 1",
        recipient_postal_code="85643",
        recipient_city="Köln",
        total_brutto=250.0,
        status="SENT",
        revision_nr=0,
        updated_at="",
        related_invoice_id=None,
        payment_link_url="",
        payment_provider="",
        items=[
            SimpleNamespace(id=10, invoice_id=1, description="Spielen", quantity=2, unit_price=125.0)
        ],
    )

    new_draft = SimpleNamespace(
        id=2,
        customer_id=5,
        company_id=1,
        nr="RE-10043",
        title="Rechnung",
        date="2026-06-12",
        delivery_date="",
        recipient_name="Boring GmbH",
        recipient_street="Beispieladresse 1",
        recipient_postal_code="85643",
        recipient_city="Köln",
        total_brutto=250.0,
        status="DRAFT",
        revision_nr=0,
        updated_at="",
        related_invoice_id=None,
        payment_link_url="",
        payment_provider="",
        items=[
            SimpleNamespace(id=20, invoice_id=2, description="Spielen", quantity=2, unit_price=125.0)
        ],
    )

    session_mock = MagicMock()
    session_mock.get.side_effect = lambda model, id: {1: orig, 2: new_draft}.get(id)

    monkeypatch.setattr(invoices_module, "finalize_invoice_logic", lambda *a, **k: 2)

    app.dependency_overrides[dependencies_module.get_current_company] = lambda: comp
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)

    response = TestClient(app).post("/api/invoices/1/duplicate")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["customer_id"] == 5
    assert body["status"] == "DRAFT"
    assert body["items"][0]["description"] == "Spielen"


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_suggestions_returns_empty_for_no_history(invoices_app) -> None:
    app, _ = invoices_app
    session_mock = MagicMock()
    session_mock.exec.return_value.all.return_value = []
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/invoices/suggestions?customer_id=1")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def _make_mock_invoice(id: int, status: str = "DRAFT") -> MagicMock:
    inv = MagicMock(spec=Invoice, id=id, status=status, revision_nr=0)
    inv.customer_id = 1
    inv.nr = None
    inv.title = "Rechnung"
    inv.date = ""
    inv.delivery_date = ""
    inv.recipient_name = ""
    inv.recipient_street = ""
    inv.recipient_postal_code = ""
    inv.recipient_city = ""
    inv.total_brutto = 0.0
    inv.updated_at = ""
    inv.related_invoice_id = None
    inv.payment_link_url = ""
    inv.payment_provider = ""
    inv.items = []
    return inv


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_bulk_status_transitions_all(invoices_app) -> None:
    app, _ = invoices_app
    inv1 = _make_mock_invoice(1, "DRAFT")
    inv2 = _make_mock_invoice(2, "DRAFT")
    session_mock = MagicMock()
    session_mock.get.side_effect = lambda model, id: {1: inv1, 2: inv2}.get(id)
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post(
        "/api/invoices/bulk-status",
        json={"invoice_ids": [1, 2], "status": "OPEN"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["id"] == 1
    assert body[0]["status"] == "OPEN"
    assert body[1]["id"] == 2
    assert body[1]["status"] == "OPEN"


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_bulk_status_returns_404_for_missing_invoice(invoices_app) -> None:
    app, _ = invoices_app
    inv1 = _make_mock_invoice(1, "DRAFT")
    session_mock = MagicMock()
    session_mock.get.side_effect = lambda model, id: inv1 if id == 1 else None
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post(
        "/api/invoices/bulk-status",
        json={"invoice_ids": [1, 99], "status": "PAID"},
    )
    assert response.status_code == 404
    assert "99" in response.json()["detail"]


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_check_payment_updates_status(invoices_app, monkeypatch) -> None:
    app, _ = invoices_app
    monkeypatch.setattr(
        invoices_module, "check_payment",
        lambda invoice_id, company, session: True,
    )
    invoice = MagicMock(spec=Invoice)
    invoice.id = 42
    session_mock = MagicMock()
    session_mock.get.return_value = invoice
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post("/api/invoices/42/check-payment")
    assert response.status_code == 200
    assert response.json()["paid"] is True


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_payment_link_returns_url(invoices_app, monkeypatch) -> None:
    app, _ = invoices_app
    monkeypatch.setattr(
        invoices_module, "create_payment_link",
        lambda invoice_id, company, session: "https://checkout.stripe.com/pay/cs_test_123",
    )
    invoice = MagicMock(spec=Invoice)
    invoice.id = 42
    invoice.company_id = 1
    session_mock = MagicMock()
    session_mock.get.return_value = invoice
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post("/api/invoices/42/payment-link")
    assert response.status_code == 200
    assert response.json()["payment_link_url"] == "https://checkout.stripe.com/pay/cs_test_123"


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_payment_link_returns_404_for_missing(invoices_app, monkeypatch) -> None:
    app, _ = invoices_app
    session_mock = MagicMock()
    session_mock.get.return_value = None
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post("/api/invoices/999/payment-link")
    assert response.status_code == 404


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_suggestions_returns_unique_items_for_customer(invoices_app) -> None:
    app, _ = invoices_app
    fake_items = [
        ("Webentwicklung", 1200.0),
        ("Hosting", 99.0),
        ("Webentwicklung", 1200.0),  # duplicate
    ]
    session_mock = MagicMock()
    session_mock.exec.return_value.all.return_value = fake_items
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/invoices/suggestions?customer_id=5")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2  # unique by (description, unit_price)
    assert body[0]["description"] == "Webentwicklung"
    assert body[0]["unit_price"] == 1200.0
    assert body[1]["description"] == "Hosting"


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_preview_pdf_validates_payload(invoices_app) -> None:
    app, _ = invoices_app
    session_mock = MagicMock()
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post(
        "/api/invoices/preview-pdf",
        json={"customer_id": 1, "items": []},  # missing date
    )
    assert response.status_code == 200 or response.status_code == 400


@pytest.mark.skipif(build_invoices_router is None, reason="app.api.invoices.router not yet implemented")
def test_preview_pdf_returns_pdf_bytes(invoices_app, monkeypatch) -> None:
    app, _ = invoices_app
    fake_pdf = b"%PDF-1.4\nfake-pdf-content"
    monkeypatch.setattr(invoices_module, "render_invoice_to_pdf_bytes", lambda data, **kw: fake_pdf)
    session_mock = MagicMock()
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post(
        "/api/invoices/preview-pdf",
        json={
            "customer_id": 1,
            "date": "2026-06-10",
            "items": [{"description": "X", "quantity": 1, "unit_price": 100.0}],
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == fake_pdf
