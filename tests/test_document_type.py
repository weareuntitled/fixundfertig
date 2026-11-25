"""Dokumentart an der Rechnung (#484).

Jeder Datensatz in `invoice` trägt eine Dokumentart. Bestehende und neue
Datensätze sind Rechnungen. Alle Lesestellen für Rechnungen filtern auf die
Dokumentart Rechnung; Löschungen von Kunde, Firma und Konto nehmen alle
Dokumentarten mit. Die Tests legen dafür einen Datensatz anderer Dokumentart
(Angebot) direkt in einer Temp-Datenbank an.
"""
from __future__ import annotations

import csv
import importlib
import io
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine, select

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app"
if str(APP_PATH) not in sys.path:
    sys.path.append(str(APP_PATH))

importlib.import_module("app.api")
data_module = importlib.import_module("data")
db_module = importlib.import_module("db")

Company = data_module.Company
Customer = data_module.Customer
Invoice = data_module.Invoice
InvoiceItem = data_module.InvoiceItem
InvoiceStatus = data_module.InvoiceStatus
User = data_module.User
DocumentType = data_module.DocumentType


@pytest.fixture
def temp_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/doctype.db")
    SQLModel.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def _seed(SessionLocal):
    """Firma mit einem Kunden, einer Rechnung (119 €) und einem Angebot (5000 €)."""
    with SessionLocal() as s:
        user = User(email="owner@example.test", password_hash="x")
        s.add(user)
        s.commit()
        s.refresh(user)
        comp = Company(name="Musterfirma", user_id=int(user.id))
        s.add(comp)
        s.commit()
        s.refresh(comp)
        cust = Customer(company_id=int(comp.id), kdnr=1, name="Kunde A")
        s.add(cust)
        s.commit()
        s.refresh(cust)
        invoice = Invoice(
            customer_id=int(cust.id), company_id=int(comp.id), nr="R-1",
            date="2026-06-10", total_brutto=119.0, status=InvoiceStatus.OPEN,
        )
        quote = Invoice(
            customer_id=int(cust.id), company_id=int(comp.id), nr="A-1",
            title="Angebot", date="2026-06-11", total_brutto=5000.0,
            document_type=DocumentType.QUOTE,
        )
        s.add(invoice)
        s.add(quote)
        s.commit()
        s.add(InvoiceItem(invoice_id=int(invoice.id), description="Rechnungsposten", quantity=1, unit_price=100))
        s.add(InvoiceItem(invoice_id=int(quote.id), description="Angebotsposten", quantity=1, unit_price=5000))
        s.commit()
        return int(user.id), int(comp.id), int(cust.id), int(invoice.id), int(quote.id)


def test_new_invoice_defaults_to_document_type_invoice() -> None:
    inv = Invoice(customer_id=1, date="2026-06-10", total_brutto=0)
    assert inv.document_type == DocumentType.INVOICE


def test_existing_invoices_get_document_type_invoice_at_startup(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE invoice (id INTEGER PRIMARY KEY, customer_id INTEGER, date TEXT, total_brutto REAL)"
        )
        conn.exec_driver_sql("INSERT INTO invoice (customer_id, date, total_brutto) VALUES (1, '2025-01-01', 10)")

    db_module.ensure_invoice_document_type_field(engine)

    with engine.begin() as conn:
        rows = conn.exec_driver_sql("SELECT document_type FROM invoice").fetchall()
    assert [r[0] for r in rows] == ["INVOICE"]


def _api_client(SessionLocal, company_id: int, *routers) -> TestClient:
    dependencies = importlib.import_module("dependencies")
    app = FastAPI()
    for router in routers:
        app.include_router(router)

    def _session():
        with SessionLocal() as s:
            yield s

    def _company():
        with SessionLocal() as s:
            return s.get(Company, company_id)

    app.dependency_overrides[dependencies.require_session_auth] = lambda: 1
    app.dependency_overrides[dependencies.get_current_company] = _company
    app.dependency_overrides[dependencies.db_session] = _session
    return TestClient(app)


def test_invoice_list_excludes_quotes(temp_db) -> None:
    _, comp_id, _, invoice_id, _ = _seed(temp_db)
    client = _api_client(temp_db, comp_id, importlib.import_module("invoices").router)

    response = client.get("/api/invoices")

    assert response.status_code == 200
    assert [inv["id"] for inv in response.json()] == [invoice_id]


def test_customer_totals_count_only_invoices(temp_db) -> None:
    """Die Kundenseite summiert die Rechnungen des Kunden aus der Rechnungsliste."""
    _, comp_id, cust_id, _, _ = _seed(temp_db)
    client = _api_client(temp_db, comp_id, importlib.import_module("invoices").router)

    invoices = client.get("/api/invoices").json()
    customer_total = sum(inv["total_brutto"] for inv in invoices if inv["customer_id"] == cust_id)

    assert customer_total == 119.0


def test_ledger_excludes_quotes(temp_db) -> None:
    _, comp_id, _, invoice_id, _ = _seed(temp_db)
    client = _api_client(temp_db, comp_id, importlib.import_module("ledger").router)

    response = client.get("/api/ledger")

    assert response.status_code == 200
    invoice_entries = [e for e in response.json() if e["type"] == "invoice"]
    assert [e["id"] for e in invoice_entries] == [invoice_id]


def test_exports_exclude_quotes(temp_db) -> None:
    logic = importlib.import_module("logic")
    _, comp_id, _, _, _ = _seed(temp_db)

    with temp_db() as s:
        invoices_csv = logic.export_invoices_csv(s, comp_id).decode("utf-8-sig")
        items_csv = logic.export_invoice_items_csv(s, comp_id).decode("utf-8-sig")

    invoice_nrs = [row["nr"] for row in csv.DictReader(io.StringIO(invoices_csv), delimiter=";")]
    item_texts = [row["description"] for row in csv.DictReader(io.StringIO(items_csv), delimiter=";")]
    assert invoice_nrs == ["R-1"]
    assert item_texts == ["Rechnungsposten"]


def _assert_no_invoice_rows_left(SessionLocal) -> None:
    with SessionLocal() as s:
        assert s.exec(select(Invoice)).all() == []
        assert s.exec(select(InvoiceItem)).all() == []


def test_deleting_customer_without_invoices_removes_its_quotes(temp_db) -> None:
    _, comp_id, cust_id, invoice_id, _ = _seed(temp_db)
    with temp_db() as s:
        for item in s.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)).all():
            s.delete(item)
        s.delete(s.get(Invoice, invoice_id))
        s.commit()
    client = _api_client(temp_db, comp_id, importlib.import_module("customers").router)

    response = client.delete(f"/api/customers/{cust_id}")

    assert response.status_code == 204
    with temp_db() as s:
        assert s.get(Customer, cust_id) is None
    _assert_no_invoice_rows_left(temp_db)


def test_customer_with_invoices_still_cannot_be_deleted(temp_db) -> None:
    _, comp_id, cust_id, _, _ = _seed(temp_db)
    client = _api_client(temp_db, comp_id, importlib.import_module("customers").router)

    assert client.delete(f"/api/customers/{cust_id}").status_code == 409


def _use_temp_session(module, monkeypatch, SessionLocal) -> None:
    @contextmanager
    def _get_session():
        with SessionLocal() as s:
            yield s

    monkeypatch.setattr(module, "get_session", _get_session)


def test_deleting_company_removes_quotes(temp_db, monkeypatch) -> None:
    companies = importlib.import_module("services.companies")
    _use_temp_session(companies, monkeypatch, temp_db)
    user_id, comp_id, _, _, _ = _seed(temp_db)

    companies.delete_company(user_id, comp_id)

    _assert_no_invoice_rows_left(temp_db)


def test_deleting_account_removes_quotes(temp_db, monkeypatch) -> None:
    account = importlib.import_module("services.account")
    _use_temp_session(account, monkeypatch, temp_db)
    monkeypatch.setattr(account, "_cleanup_company_storage", lambda *a, **kw: None)
    monkeypatch.setattr(account, "delete_company_dirs", lambda *a, **kw: None)
    user_id, _, _, _, _ = _seed(temp_db)

    account.delete_account(user_id)

    _assert_no_invoice_rows_left(temp_db)


def test_payment_link_is_not_created_for_quotes(temp_db, monkeypatch) -> None:
    payment = importlib.import_module("services.payment")
    stripe_calls: list = []
    monkeypatch.setattr(payment, "_stripe", lambda: stripe_calls.append("called"))
    _, comp_id, _, _, quote_id = _seed(temp_db)

    with temp_db() as s:
        company = s.get(Company, comp_id)
        company.stripe_secret_key = "sk_test_dummy"
        url = payment.create_payment_link(invoice_id=quote_id, company=company, session=s)

    assert url is None
    assert stripe_calls == []


def test_correction_cannot_reference_a_quote(temp_db, monkeypatch) -> None:
    actions = importlib.import_module("actions")
    _use_temp_session(actions, monkeypatch, temp_db)
    _, _, _, _, quote_id = _seed(temp_db)

    correction, err = actions.create_correction(quote_id)

    assert correction is None
    assert err == "Rechnung nicht gefunden"
    with temp_db() as s:
        assert s.exec(select(Invoice).where(Invoice.related_invoice_id == quote_id)).all() == []
