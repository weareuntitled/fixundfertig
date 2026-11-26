"""Abschlagsrechnung aus einer Rate des Zahlungsplans (#490)."""
from __future__ import annotations

import importlib

import pytest

from pdf_text import pdf_text
from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)

PLAN = [
    {"percent": 50, "label": "bei Auftrag"},
    {"percent": 50, "label": "nach Livegang"},
]
NET_4000 = [{"description": "Website", "quantity": 1, "unit_price": 4000}]


def _create_quote(client, payload: dict, **overrides) -> dict:
    body = payload | {
        "document_type": "QUOTE",
        "date": "2026-10-23",
        "items": NET_4000,
        "payment_plan": PLAN,
    } | overrides
    response = client.post("/api/invoices", json=body)
    assert response.status_code == 201, response.text
    quote = response.json()
    # Abrechnen geht nur aus „Gesendet“ oder „Angenommen“ (#495).
    sent = client.put(f"/api/invoices/{quote['id']}/status", json={"status": "SENT"})
    assert sent.status_code == 200, sent.text
    return quote


def _down_payment(client, quote_id: int, index: int):
    return client.post(f"/api/invoices/{quote_id}/down-payment", json={"installment_index": index})


def _flat_pdf(client, invoice_id: int) -> str:
    response = client.get(f"/api/invoices/{invoice_id}/download")
    assert response.status_code == 200, response.text
    return " ".join(pdf_text(response.content).split())


def test_startup_adds_the_installment_index_column(tmp_path):
    from sqlmodel import create_engine

    importlib.import_module("app.api")
    db = importlib.import_module("db")
    engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE invoice (id INTEGER PRIMARY KEY, customer_id INTEGER, date TEXT)")
        conn.exec_driver_sql("INSERT INTO invoice (customer_id, date) VALUES (1, '2025-01-01')")

    db.ensure_invoice_quote_fields(engine)

    with engine.begin() as conn:
        row = conn.exec_driver_sql("SELECT down_payment_index FROM invoice").fetchone()
    assert tuple(row) == (None,)


def test_fifty_percent_rate_becomes_a_draft_invoice_for_half_the_net_amount(artist_api):
    client, company, payload, session = artist_api
    company.is_small_business = False
    session.add(company)
    session.commit()
    quote = _create_quote(client, payload, vat_rate=19)

    response = _down_payment(client, quote["id"], 0)

    assert response.status_code == 201, response.text
    invoice = response.json()
    assert invoice["document_type"] == "INVOICE"
    assert invoice["status"] == "DRAFT"
    assert invoice["quote_id"] == quote["id"]
    assert invoice["down_payment_index"] == 0
    assert invoice["total_brutto"] == 2380.0
    assert [(i["description"], i["quantity"], i["unit_price"]) for i in invoice["items"]] == [
        ("Abschlag 50 % gemäß Angebot A-10000 – bei Auftrag", 1.0, 2000.0)
    ]


def test_small_business_down_payment_has_no_tax(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload, vat_rate=0)

    invoice = _down_payment(client, quote["id"], 0).json()

    assert invoice["total_brutto"] == 2000.0
    assert "Umsatzsteuer 19 %" not in _flat_pdf(client, invoice["id"])
    assert "Umsatzsteuer nicht erhoben" in _flat_pdf(client, invoice["id"])


def test_down_payment_download_names_the_document_type(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    invoice = _down_payment(client, quote["id"], 0).json()
    response = client.get(f"/api/invoices/{invoice['id']}/download")
    assert response.headers["content-disposition"] == f'attachment; filename="abschlagsrechnung_{invoice["nr"]}.pdf"'


def test_down_payment_respects_a_custom_invoice_filename_template(artist_api):
    client, company, payload, session = artist_api
    company.invoice_filename_template = "beleg-{nr}"
    session.add(company)
    session.commit()
    quote = _create_quote(client, payload)
    invoice = _down_payment(client, quote["id"], 0).json()
    response = client.get(f"/api/invoices/{invoice['id']}/download")
    assert response.headers["content-disposition"] == f'attachment; filename="beleg-{invoice["nr"]}.pdf"'


def test_pdf_calls_it_a_down_payment_and_names_quote_and_percentage(artist_api):
    client, company, payload, session = artist_api
    company.is_small_business = False
    session.add(company)
    session.commit()
    quote = _create_quote(client, payload, vat_rate=19)
    invoice = _down_payment(client, quote["id"], 0).json()

    text = _flat_pdf(client, invoice["id"])

    assert "Abschlagsrechnung" in text
    assert "A-10000" in text
    assert "50 %" in text


def test_down_payment_pdf_heading_survives_a_title_change(artist_api):
    client, company, payload, session = artist_api
    company.is_small_business = False
    session.add(company)
    session.commit()
    quote = _create_quote(client, payload, vat_rate=19)
    invoice = _down_payment(client, quote["id"], 0).json()

    changed = client.put(f"/api/invoices/{invoice['id']}", json={"title": "Individueller Titel"})

    assert changed.status_code == 200, changed.text
    assert "ABSCHLAGSRECHNUNG" in _flat_pdf(client, invoice["id"])


def test_a_normal_invoice_stays_an_invoice_when_title_says_abschlagsrechnung(artist_api):
    client, _company, payload, _session = artist_api
    invoice = client.post("/api/invoices", json=payload).json()

    changed = client.put(f"/api/invoices/{invoice['id']}", json={"title": "Abschlagsrechnung"})

    assert changed.status_code == 200, changed.text
    text = _flat_pdf(client, invoice["id"])
    assert "ABSCHLAGSRECHNUNG" not in text
    assert "RECHNUNG" in text


def test_quote_is_accepted_and_the_rate_shows_as_billed_with_its_invoice(artist_api):
    client, company, payload, session = artist_api
    company.is_small_business = False
    session.add(company)
    session.commit()
    quote = _create_quote(client, payload, vat_rate=19)

    invoice = _down_payment(client, quote["id"], 0).json()

    accepted = client.get(f"/api/invoices/{quote['id']}").json()
    assert accepted["status"] == "ACCEPTED"
    assert accepted["linked_invoices"] == [
        {
            "id": invoice["id"],
            "nr": "10000",
            "status": "DRAFT",
            "total_brutto": 2380.0,
            "installment_index": 0,
            "is_down_payment": True,
            "is_final_invoice": False,
        }
    ]


def test_a_rate_cannot_be_billed_twice_until_its_invoice_is_cancelled(artist_api):
    client, company, payload, session = artist_api
    company.is_small_business = False
    session.add(company)
    session.commit()
    quote = _create_quote(client, payload, vat_rate=19)
    first = _down_payment(client, quote["id"], 0).json()

    blocked = _down_payment(client, quote["id"], 0)

    assert blocked.status_code == 409, blocked.text
    assert "bereits abgerechnet" in blocked.json()["detail"]
    assert client.put(f"/api/invoices/{first['id']}/status", json={"status": "CANCELLED"}).status_code == 200

    again = _down_payment(client, quote["id"], 0)

    assert again.status_code == 201, again.text
    assert again.json()["total_brutto"] == 2380.0


def test_the_second_rate_stays_billable_while_the_first_is_billed(artist_api):
    client, company, payload, session = artist_api
    company.is_small_business = False
    session.add(company)
    session.commit()
    quote = _create_quote(client, payload, vat_rate=19)
    _down_payment(client, quote["id"], 0)

    second = _down_payment(client, quote["id"], 1)

    assert second.status_code == 201, second.text
    assert second.json()["down_payment_index"] == 1
    assert second.json()["items"][0]["description"] == "Abschlag 50 % gemäß Angebot A-10000 – nach Livegang"


@pytest.mark.parametrize("index", [-1, 2, 99])
def test_an_index_outside_the_payment_plan_is_rejected(artist_api, index):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)

    response = _down_payment(client, quote["id"], index)

    assert response.status_code == 400, response.text


def test_a_normal_conversion_stays_distinguishable_from_a_down_payment(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)

    invoice = client.post(f"/api/invoices/{quote['id']}/convert").json()

    assert invoice["down_payment_index"] is None
    linked = client.get(f"/api/invoices/{quote['id']}").json()["linked_invoices"]
    assert [(item["installment_index"], item["is_down_payment"]) for item in linked] == [(None, False)]


def test_only_quotes_can_be_billed_by_installment(artist_api):
    client, _company, payload, _session = artist_api
    invoice = client.post("/api/invoices", json=payload).json()

    response = _down_payment(client, invoice["id"], 0)

    assert response.status_code == 400, response.text


@pytest.mark.parametrize("start", ["SENT", "ACCEPTED"])
def test_a_quote_can_be_billed_even_when_it_is_already_accepted(artist_api, start):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    assert client.put(f"/api/invoices/{quote['id']}/status", json={"status": start}).status_code == 200

    assert _down_payment(client, quote["id"], 0).status_code == 201
    assert client.get(f"/api/invoices/{quote['id']}").json()["status"] == "ACCEPTED"
