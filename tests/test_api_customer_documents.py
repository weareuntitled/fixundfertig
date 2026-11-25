"""Kunden löschen: die Dokumente des Kunden verschwinden ganz (Anhänge, Protokolle)."""
from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

importlib.import_module("app.api")
customers = importlib.import_module("customers")
invoices = importlib.import_module("invoices")
dependencies = importlib.import_module("dependencies")
data = importlib.import_module("data")


@pytest.fixture
def customer_api():
    """Real DB: ein Kunde mit einem Angebot, einem Anhang und einem Protokolleintrag."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        company = data.Company(name="Daniel S.", city="Berlin", next_invoice_nr=10000, next_quote_nr=10000)
        session.add(company)
        session.commit()
        customer = data.Customer(company_id=company.id, kdnr=1, name="Club Beispiel")
        session.add(customer)
        session.commit()

        app = FastAPI()
        app.include_router(customers.router)
        app.include_router(invoices.router)
        app.dependency_overrides[dependencies.require_session_auth] = lambda: 1
        app.dependency_overrides[dependencies.get_current_company] = lambda: company

        def db_session():
            yield session

        app.dependency_overrides[dependencies.db_session] = db_session
        payload = {
            "customer_id": customer.id,
            "document_type": "QUOTE",
            "date": "2026-10-23",
            "recipient_name": "Club Beispiel",
            "vat_rate": 19,
            "items": [{"description": "DJ-Set", "quantity": 1, "unit_price": 150}],
        }
        with TestClient(app) as client:
            yield client, session, customer, payload
    engine.dispose()


def test_deleting_a_customer_removes_the_attachments_of_their_documents(customer_api):
    client, session, customer, payload = customer_api
    quote = client.post("/api/invoices", json=payload).json()
    document = data.Document(company_id=1, filename="rechnung.pdf", title="Rechnung")
    session.add(document)
    session.commit()
    linked = client.post(
        f"/api/invoices/{quote['id']}/attachments", json={"document_id": document.id}
    )
    assert linked.status_code == 201, linked.text
    session.add(data.AuditLog(action="INVOICE_SENT", invoice_id=quote["id"]))
    session.commit()

    response = client.delete(f"/api/customers/{customer.id}")

    assert response.status_code == 204, response.text
    assert session.exec(select(data.InvoiceAttachment)).all() == []
    assert session.exec(select(data.AuditLog)).all() == []


def test_a_new_invoice_does_not_inherit_the_attachments_of_a_deleted_quote(customer_api):
    client, session, customer, payload = customer_api
    quote = client.post("/api/invoices", json=payload).json()
    document = data.Document(company_id=1, filename="rechnung.pdf", title="Rechnung")
    session.add(document)
    session.commit()
    client.post(f"/api/invoices/{quote['id']}/attachments", json={"document_id": document.id})

    assert client.delete(f"/api/customers/{customer.id}").status_code == 204

    # SQLite vergibt die ID des gelöschten Angebots erneut: die neue Rechnung darf
    # die Anhänge des gelöschten Angebots nicht erben.
    other = data.Customer(company_id=1, kdnr=2, name="Club Anders")
    session.add(other)
    session.commit()
    created = client.post("/api/invoices", json=payload | {"customer_id": other.id}).json()

    assert created["id"] == quote["id"]
    assert created["attachments"] == []
