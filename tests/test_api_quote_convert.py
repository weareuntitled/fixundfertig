"""Angebot in Rechnung umwandeln (#489)."""
from __future__ import annotations

import pytest

from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)
from pdf_text import pdf_text


def test_startup_adds_quote_link_columns_to_existing_databases(tmp_path):
    import importlib

    from sqlmodel import create_engine

    importlib.import_module("app.api")
    db = importlib.import_module("db")
    engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE invoice (id INTEGER PRIMARY KEY, customer_id INTEGER, date TEXT)")
        conn.exec_driver_sql("INSERT INTO invoice (customer_id, date) VALUES (1, '2025-01-01')")

    db.ensure_invoice_quote_link_fields(engine)

    with engine.begin() as conn:
        row = conn.exec_driver_sql("SELECT intro_text, quote_id FROM invoice").fetchone()
    assert tuple(row) == ("", None)


def _create_quote(client, payload: dict) -> dict:
    response = client.post("/api/invoices", json=payload | {"document_type": "QUOTE"})
    assert response.status_code == 201, response.text
    return response.json()


def _convert(client, quote_id: int):
    return client.post(f"/api/invoices/{quote_id}/convert")


def test_convert_creates_invoice_draft_with_quote_items_and_customer(artist_api):
    client, company, payload, _session = artist_api
    quote = _create_quote(client, payload)

    response = _convert(client, quote["id"])

    assert response.status_code == 201, response.text
    invoice = response.json()
    assert invoice["document_type"] == "INVOICE"
    assert invoice["status"] == "DRAFT"
    assert invoice["customer_id"] == payload["customer_id"]
    assert invoice["recipient_name"] == payload["recipient_name"]
    assert [(i["description"], i["quantity"], i["unit_price"]) for i in invoice["items"]] == [
        ("DJ-Set Daniel S.", 2.0, 150.0)
    ]
    assert invoice["total_brutto"] == 300.0
    listed = client.get("/api/invoices").json()
    assert [inv["id"] for inv in listed] == [invoice["id"]]


def test_converted_invoice_gets_a_normal_invoice_number_and_quote_counter_stays(artist_api):
    client, company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    quote_counter = company.next_quote_nr

    invoice = _convert(client, quote["id"]).json()

    assert quote["nr"] == "A-10000"
    assert invoice["nr"] == "10000"
    assert company.next_quote_nr == quote_counter


def test_only_quotes_can_be_converted(artist_api):
    client, _company, payload, _session = artist_api
    invoice = client.post("/api/invoices", json=payload).json()

    response = _convert(client, invoice["id"])

    assert response.status_code == 400, response.text
    assert len(client.get("/api/invoices").json()) == 1


def _flat_pdf(client, doc_id: int) -> str:
    response = client.get(f"/api/invoices/{doc_id}/download")
    assert response.status_code == 200
    return " ".join(pdf_text(response.content).split())


def test_invoice_pdf_names_the_quote_number_and_date(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)

    invoice = _convert(client, quote["id"]).json()

    assert "Gemäß Angebot A-10000 vom 23.10.2026." in _flat_pdf(client, invoice["id"])


def test_quote_reference_survives_pdf_regeneration(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    invoice = _convert(client, quote["id"]).json()

    assert client.post(f"/api/invoices/{invoice['id']}/regenerate-pdf").status_code == 200

    assert "Gemäß Angebot A-10000 vom 23.10.2026." in _flat_pdf(client, invoice["id"])


def test_quote_reference_survives_editing_the_invoice_draft(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    invoice = _convert(client, quote["id"]).json()

    response = client.put(f"/api/invoices/{invoice['id']}", json={"subject": "Clubnacht"})

    assert response.status_code == 200, response.text
    assert "Gemäß Angebot A-10000 vom 23.10.2026." in _flat_pdf(client, invoice["id"])


@pytest.mark.parametrize("start", ["DRAFT", "SENT", "ACCEPTED"])
def test_converting_marks_the_quote_accepted(artist_api, start):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    assert client.put(f"/api/invoices/{quote['id']}/status", json={"status": start}).status_code == 200

    assert _convert(client, quote["id"]).status_code == 201

    assert client.get(f"/api/invoices/{quote['id']}").json()["status"] == "ACCEPTED"


def test_an_accepted_quote_can_be_converted_several_times(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)

    first = _convert(client, quote["id"]).json()
    second = _convert(client, quote["id"]).json()

    assert (first["nr"], second["nr"]) == ("10000", "10001")


def test_quote_and_invoices_link_to_each_other(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    first = _convert(client, quote["id"]).json()
    second = _convert(client, quote["id"]).json()

    assert (first["quote_id"], first["quote_nr"]) == (quote["id"], "A-10000")
    fetched = client.get(f"/api/invoices/{second['id']}").json()
    assert (fetched["quote_id"], fetched["quote_nr"]) == (quote["id"], "A-10000")
    linked = client.get(f"/api/invoices/{quote['id']}").json()["linked_invoices"]
    assert [(i["id"], i["nr"], i["status"]) for i in linked] == [
        (first["id"], "10000", "DRAFT"),
        (second["id"], "10001", "DRAFT"),
    ]


def test_documents_without_a_link_show_none(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    invoice = client.post("/api/invoices", json=payload).json()

    assert (invoice["quote_id"], invoice["quote_nr"], invoice["linked_invoices"]) == (None, None, [])
    assert client.get(f"/api/invoices/{quote['id']}").json()["linked_invoices"] == []


def test_a_quote_with_invoices_cannot_be_deleted(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    _convert(client, quote["id"])

    response = client.delete(f"/api/invoices/{quote['id']}")

    assert response.status_code == 409, response.text
    assert "Rechnungen" in response.json()["detail"]
    assert client.get(f"/api/invoices/{quote['id']}").status_code == 200


def test_converted_invoice_keeps_the_quote_vat_rate(artist_api):
    client, company, payload, session = artist_api
    company.is_small_business = False
    session.add(company)
    session.commit()
    quote = _create_quote(client, payload | {"vat_rate": 19})

    invoice = _convert(client, quote["id"]).json()

    assert invoice["total_brutto"] == 357.0
    assert "19 %" in _flat_pdf(client, invoice["id"])
    assert "Gemäß Angebot A-10000 vom 23.10.2026." in _flat_pdf(client, invoice["id"])
