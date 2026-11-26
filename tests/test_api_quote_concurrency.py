"""Gleichzeitige Abrechnungsanfragen erzeugen genau ein Dokument (#495).

Jede Anfrage bekommt ihre eigene Datenbanksitzung auf einer Datei-Datenbank, wie im
Betrieb. Zwischen Prüfung und Anlegen wird künstlich gewartet, damit sich zwei
Anfragen sicher überschneiden.
"""
from __future__ import annotations

import importlib
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

importlib.import_module("app.api")
invoices = importlib.import_module("invoices")
dependencies = importlib.import_module("dependencies")
data = importlib.import_module("data")
quote_conversion = importlib.import_module("logic.quote_conversion")


@pytest.fixture
def parallel_api(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/parallel.db", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        company = data.Company(name="Daniel S.", first_name="Daniel", last_name="Beispiel", is_small_business=True)
        session.add(company)
        session.commit()
        customer = data.Customer(company_id=company.id, kdnr=1, name="Club Beispiel")
        session.add(customer)
        session.commit()
        session.refresh(company)
        session.refresh(customer)
        session.expunge(company)
        customer_id = int(customer.id)

    app = FastAPI()
    app.include_router(invoices.router)
    app.dependency_overrides[dependencies.require_session_auth] = lambda: 1
    app.dependency_overrides[dependencies.get_current_company] = lambda: company

    def db_session():
        with Session(engine) as request_session:
            yield request_session

    app.dependency_overrides[dependencies.db_session] = db_session

    slow_finalize = quote_conversion.finalize_invoice_logic

    def finalize_slowly(*args, **kwargs):
        time.sleep(0.3)
        return slow_finalize(*args, **kwargs)

    payload = {
        "customer_id": customer_id,
        "date": "2026-10-23",
        "document_type": "QUOTE",
        "vat_rate": 0,
        "items": [{"description": "DJ-Set", "quantity": 2, "unit_price": 150}],
        "payment_plan": [{"percent": 40, "label": "bei Auftrag"}, {"percent": 60, "label": "nach Abnahme"}],
    }
    with TestClient(app) as client:
        quote = client.post("/api/invoices", json=payload).json()
        assert client.put(f"/api/invoices/{quote['id']}/status", json={"status": "SENT"}).status_code == 200
        monkeypatch.setattr(quote_conversion, "finalize_invoice_logic", finalize_slowly)
        yield client, engine, quote
    engine.dispose()


def _twice(client: TestClient, path: str, body: dict | None = None) -> list[int]:
    """Dieselbe Anfrage zweimal gleichzeitig senden; die Statuscodes zurückgeben."""
    start = threading.Barrier(2)
    codes: list[int] = []

    def send():
        start.wait()
        codes.append(client.post(path, json=body).status_code)

    threads = [threading.Thread(target=send) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return sorted(codes)


def _invoices_of(engine, quote_id: int) -> list:
    with Session(engine) as session:
        return session.exec(select(data.Invoice).where(data.Invoice.quote_id == quote_id)).all()


def test_two_simultaneous_conversions_create_one_invoice(parallel_api):
    client, engine, quote = parallel_api

    codes = _twice(client, f"/api/invoices/{quote['id']}/convert")

    assert codes == [201, 409]
    assert len(_invoices_of(engine, quote["id"])) == 1


def test_two_simultaneous_down_payments_for_one_rate_create_one_invoice(parallel_api):
    client, engine, quote = parallel_api

    codes = _twice(client, f"/api/invoices/{quote['id']}/down-payment", {"installment_index": 0})

    assert codes == [201, 409]
    assert len(_invoices_of(engine, quote["id"])) == 1
