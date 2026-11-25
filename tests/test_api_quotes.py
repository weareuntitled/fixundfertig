"""Angebote über die Rechnungs-API anlegen, ändern und löschen (#485)."""
from __future__ import annotations

import importlib

from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)

importlib.import_module("app.api")
data = importlib.import_module("data")


def test_startup_adds_quote_columns_to_existing_databases(tmp_path):
    from sqlmodel import create_engine

    db = importlib.import_module("db")
    engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE company (id INTEGER PRIMARY KEY, name TEXT)")
        conn.exec_driver_sql("INSERT INTO company (name) VALUES ('Altfirma')")
        conn.exec_driver_sql("CREATE TABLE invoice (id INTEGER PRIMARY KEY, customer_id INTEGER, date TEXT)")
        conn.exec_driver_sql("INSERT INTO invoice (customer_id, date) VALUES (1, '2025-01-01')")

    db.ensure_company_schema(engine)
    db.ensure_invoice_valid_until_field(engine)

    with engine.begin() as conn:
        company = conn.exec_driver_sql("SELECT next_quote_nr, quote_prefix FROM company").fetchone()
        invoice = conn.exec_driver_sql("SELECT valid_until FROM invoice").fetchone()
    assert tuple(company) == (10000, "A-")
    assert tuple(invoice) == ("",)


def _quote(payload: dict, **overrides) -> dict:
    return payload | {"document_type": "QUOTE"} | overrides


def test_first_quote_gets_quote_number_and_stays_draft(artist_api):
    client, _company, payload, _session = artist_api

    response = client.post("/api/invoices", json=_quote(payload))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["document_type"] == "QUOTE"
    assert body["nr"] == "A-10000"
    assert body["status"] == "DRAFT"
    assert body["title"] == "Angebot"


def test_valid_until_defaults_to_quote_date_plus_30_days(artist_api):
    client, _company, payload, _session = artist_api

    body = client.post("/api/invoices", json=_quote(payload, date="2026-10-23")).json()

    assert body["valid_until"] == "2026-11-22"


def test_valid_until_can_be_chosen(artist_api):
    client, _company, payload, _session = artist_api

    body = client.post("/api/invoices", json=_quote(payload, valid_until="2026-12-31")).json()

    assert body["valid_until"] == "2026-12-31"


def test_invoice_and_quote_counters_are_independent(artist_api):
    client, _company, payload, _session = artist_api

    first_invoice = client.post("/api/invoices", json=payload).json()
    first_quote = client.post("/api/invoices", json=_quote(payload)).json()
    second_quote = client.post("/api/invoices", json=_quote(payload)).json()
    second_invoice = client.post("/api/invoices", json=payload).json()

    assert first_invoice["document_type"] == "INVOICE"
    assert [first_invoice["nr"], second_invoice["nr"]] == ["10000", "10001"]
    assert [first_quote["nr"], second_quote["nr"]] == ["A-10000", "A-10001"]


def test_quote_number_uses_invoice_template_and_quote_prefix(artist_api):
    client, company, payload, _session = artist_api
    company.invoice_number_template = "RE-{seq}"
    company.quote_prefix = "ANG-"
    company.next_quote_nr = 7

    body = client.post("/api/invoices", json=_quote(payload)).json()

    assert body["nr"] == "ANG-RE-7"


def test_two_companies_count_quotes_independently(artist_api):
    client, company, payload, session = artist_api
    dependencies = importlib.import_module("dependencies")
    other = data.Company(name="Zweite Firma")
    session.add(other)
    session.commit()
    other_customer = data.Customer(company_id=other.id, kdnr=1, name="Kunde B")
    session.add(other_customer)
    session.commit()

    client.post("/api/invoices", json=_quote(payload))
    client.app.dependency_overrides[dependencies.get_current_company] = lambda: other
    other_quote = client.post(
        "/api/invoices", json=_quote(payload, customer_id=other_customer.id, recipient_name="Kunde B")
    ).json()
    client.app.dependency_overrides[dependencies.get_current_company] = lambda: company
    second_quote = client.post("/api/invoices", json=_quote(payload)).json()

    assert other_quote["nr"] == "A-10000"
    assert second_quote["nr"] == "A-10001"


def test_quote_appears_in_quote_list_not_in_invoice_list(artist_api):
    client, _company, payload, _session = artist_api
    invoice = client.post("/api/invoices", json=payload).json()
    quote = client.post("/api/invoices", json=_quote(payload)).json()

    invoices = client.get("/api/invoices").json()
    quotes = client.get("/api/invoices", params={"document_type": "QUOTE"}).json()

    assert [i["id"] for i in invoices] == [invoice["id"]]
    assert [q["id"] for q in quotes] == [quote["id"]]
    assert quotes[0]["valid_until"]


def test_quote_can_be_changed(artist_api):
    client, _company, payload, _session = artist_api
    quote = client.post("/api/invoices", json=_quote(payload)).json()

    updated = client.put(
        f"/api/invoices/{quote['id']}",
        json={"subject": "Hochzeit Juni", "valid_until": "2027-01-15"},
    )
    added = client.post(
        f"/api/invoices/{quote['id']}/items",
        json={"description": "Technik", "quantity": 1, "unit_price": 80},
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["subject"] == "Hochzeit Juni"
    assert updated.json()["valid_until"] == "2027-01-15"
    assert added.status_code == 201, added.text
    reread = client.get(f"/api/invoices/{quote['id']}").json()
    assert [it["description"] for it in reread["items"]] == ["DJ-Set Daniel S.", "Technik"]
    assert reread["nr"] == "A-10000"
    assert reread["document_type"] == "QUOTE"


def test_quote_can_be_deleted(artist_api, monkeypatch):
    from contextlib import contextmanager

    client, _company, payload, session = artist_api
    actions = importlib.import_module("actions")

    @contextmanager
    def _test_session():
        yield session

    monkeypatch.setattr(actions, "get_session", _test_session)
    quote = client.post("/api/invoices", json=_quote(payload)).json()

    response = client.delete(f"/api/invoices/{quote['id']}")

    assert response.status_code == 200, response.text
    assert client.get("/api/invoices", params={"document_type": "QUOTE"}).json() == []
    assert client.get(f"/api/invoices/{quote['id']}").status_code == 404


def test_company_quote_prefix_and_counter_can_be_changed(tmp_path, monkeypatch):
    from contextlib import contextmanager

    from sqlmodel import Session, SQLModel, create_engine

    companies = importlib.import_module("services.companies")
    engine = create_engine(f"sqlite:///{tmp_path}/companies.db")
    SQLModel.metadata.create_all(engine)

    @contextmanager
    def _session():
        with Session(engine, expire_on_commit=False) as s:
            yield s

    monkeypatch.setattr(companies, "get_session", _session)
    with _session() as s:
        user = data.User(email="owner@example.test", password_hash="x")
        s.add(user)
        s.commit()
        company = data.Company(name="Firma", user_id=user.id)
        s.add(company)
        s.commit()
        user_id, company_id = int(user.id), int(company.id)

    updated = companies.update_company(user_id, company_id, {"quote_prefix": "ANG-", "next_quote_nr": 500})

    assert (updated.quote_prefix, updated.next_quote_nr) == ("ANG-", 500)
