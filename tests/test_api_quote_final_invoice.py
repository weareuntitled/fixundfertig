"""Schlussrechnung mit Abzug der Abschlagsrechnungen (#491)."""
from __future__ import annotations

import importlib

import pytest

from pdf_text import pdf_text
from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)

PLAN = [
    {"percent": 50, "label": "bei Auftrag"},
    {"percent": 25, "label": "nach Livegang"},
    {"percent": 25, "label": "bei Abnahme"},
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


def _down_payment(client, quote_id: int, index: int) -> dict:
    response = client.post(f"/api/invoices/{quote_id}/down-payment", json={"installment_index": index})
    assert response.status_code == 201, response.text
    return response.json()


def _send(client, invoice_id: int) -> None:
    response = client.put(f"/api/invoices/{invoice_id}/status", json={"status": "SENT"})
    assert response.status_code == 200, response.text


def _cancel(client, invoice_id: int) -> None:
    response = client.put(f"/api/invoices/{invoice_id}/status", json={"status": "CANCELLED"})
    assert response.status_code == 200, response.text


def _final(client, quote_id: int):
    return client.post(f"/api/invoices/{quote_id}/final-invoice")


def _flat_pdf(client, invoice_id: int) -> str:
    response = client.get(f"/api/invoices/{invoice_id}/download")
    assert response.status_code == 200, response.text
    return " ".join(pdf_text(response.content).split())


def _standard_company(company, session) -> None:
    company.is_small_business = False
    session.add(company)
    session.commit()


def test_startup_adds_the_final_invoice_marker_column(tmp_path):
    from sqlmodel import create_engine

    importlib.import_module("app.api")
    db = importlib.import_module("db")
    engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE invoice (id INTEGER PRIMARY KEY, customer_id INTEGER, date TEXT)")
        conn.exec_driver_sql("INSERT INTO invoice (customer_id, date) VALUES (1, '2025-01-01')")

    db.ensure_invoice_quote_fields(engine)

    with engine.begin() as conn:
        row = conn.exec_driver_sql("SELECT is_final_invoice FROM invoice").fetchone()
    assert tuple(row) == (0,)


def test_final_invoice_deducts_only_sent_and_not_cancelled_down_payments(artist_api):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    sent = _down_payment(client, quote["id"], 0)
    cancelled = _down_payment(client, quote["id"], 1)
    _send(client, sent["id"])
    _cancel(client, cancelled["id"])

    response = _final(client, quote["id"])

    assert response.status_code == 201, response.text
    invoice = response.json()
    assert invoice["document_type"] == "INVOICE"
    assert invoice["status"] == "DRAFT"
    assert invoice["quote_id"] == quote["id"]
    assert invoice["is_final_invoice"] is True
    assert invoice["down_payment_index"] is None
    assert [item["description"] for item in invoice["items"]] == ["Website"]
    # 4.000 netto + 760 Steuer − (2.000 netto + 380 Steuer) = 2.380 Restbetrag.
    assert invoice["total_brutto"] == 2380.0


def test_final_invoice_shows_in_the_quote_list_and_links_both_ways(artist_api):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    sent = _down_payment(client, quote["id"], 0)
    _send(client, sent["id"])

    invoice = _final(client, quote["id"]).json()

    accepted = client.get(f"/api/invoices/{quote['id']}").json()
    assert accepted["status"] == "ACCEPTED"
    final_links = [item for item in accepted["linked_invoices"] if item["is_final_invoice"]]
    assert [(item["id"], item["nr"], item["status"]) for item in final_links] == [
        (invoice["id"], invoice["nr"], "DRAFT")
    ]
    fetched = client.get(f"/api/invoices/{invoice['id']}").json()
    assert (fetched["quote_id"], fetched["quote_nr"]) == (quote["id"], "A-10000")


def test_final_invoice_pdf_names_itself_and_lists_the_deduction(artist_api):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    sent = _down_payment(client, quote["id"], 0)
    cancelled = _down_payment(client, quote["id"], 1)
    _send(client, sent["id"])
    _cancel(client, cancelled["id"])
    invoice = _final(client, quote["id"]).json()

    text = _flat_pdf(client, invoice["id"])

    assert "SCHLUSSRECHNUNG" in text
    assert "A-10000" in text
    assert "abzüglich Abschlagsrechnung 10000 vom" in text
    assert "2.000,00" in text
    assert "380,00" in text
    assert "Gesamtleistung" in text
    assert "Restbetrag" in text


def test_small_business_final_invoice_has_no_tax_lines_or_amounts(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload, vat_rate=0)
    sent = _down_payment(client, quote["id"], 0)
    _send(client, sent["id"])

    invoice = _final(client, quote["id"]).json()

    assert invoice["total_brutto"] == 2000.0
    text = _flat_pdf(client, invoice["id"])
    assert "Umsatzsteuer" not in text
    assert "380,00" not in text
    assert "Restbetrag" in text


def test_changing_a_position_changes_the_rest_amount(artist_api):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    sent = _down_payment(client, quote["id"], 0)
    _send(client, sent["id"])
    invoice = _final(client, quote["id"]).json()
    item_id = invoice["items"][0]["id"]

    response = client.put(
        f"/api/invoices/{invoice['id']}/items/{item_id}",
        json={"description": "Website", "quantity": 1, "unit_price": 5000},
    )

    assert response.status_code == 200, response.text
    # 5.000 netto + 950 Steuer − 2.380 Abschlag = 3.570 Restbetrag.
    assert response.json()["total_brutto"] == 3570.0


def test_the_final_invoice_shows_a_payment_due_date_and_the_deductions(artist_api):
    """Die Schlussrechnung ist eine Forderung: Zahlungsziel und Zahlungskasten stehen drin."""
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    sent = _down_payment(client, quote["id"], 0)
    _send(client, sent["id"])
    invoice = _final(client, quote["id"]).json()

    text = _flat_pdf(client, invoice["id"])

    assert "Zahlbar bis" in text
    assert "ZAHLUNGSINFORMATIONEN" in text
    assert "IBAN" in text
    assert "ABRECHNUNG" in text
    assert "Gesamtleistung" in text
    assert "Restbetrag" in text


def test_a_draft_down_payment_does_not_qualify_a_final_invoice(artist_api):
    """„Gestellt" heißt: nicht Entwurf, nicht storniert. Ein Entwurf genügt nicht."""
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    draft = _down_payment(client, quote["id"], 0)

    response = _final(client, quote["id"])

    assert response.status_code == 409, response.text
    assert f"Abschlagsrechnung {draft['nr']}" in response.json()["detail"]
    assert "Entwurf zählt nicht" in response.json()["detail"]
    assert all(item["is_final_invoice"] is False for item in client.get("/api/invoices").json())


def test_a_sent_down_payment_qualifies_a_final_invoice_and_is_deducted(artist_api):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    sent = _down_payment(client, quote["id"], 0)
    _send(client, sent["id"])

    invoice = _final(client, quote["id"]).json()

    # 4.000 netto + 760 Steuer − (2.000 netto + 380 Steuer) = 2.380 Restbetrag.
    assert invoice["total_brutto"] == 2380.0


def test_deleting_a_down_payment_frees_the_rest_amount(artist_api):
    """Eine gelöschte Abschlagsrechnung wird nicht mehr abgezogen."""
    client, company, payload, session = artist_api
    _standard_company(company, session)

    quote = _create_quote(client, payload, vat_rate=19)
    sent = _down_payment(client, quote["id"], 0)
    _send(client, sent["id"])
    invoice = _final(client, quote["id"]).json()
    assert invoice["total_brutto"] == 2380.0

    deleted = client.delete(f"/api/invoices/{sent['id']}")

    assert deleted.status_code == 200, deleted.text
    refreshed = client.get(f"/api/invoices/{invoice['id']}").json()
    assert refreshed["total_brutto"] == 4760.0


def test_changing_the_amount_of_a_down_payment_moves_the_rest_amount(artist_api):
    """Der Betrag der Abschlagsrechnung verschiebt den Restbetrag der Schlussrechnung."""
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    sent = _down_payment(client, quote["id"], 0)
    _send(client, sent["id"])
    invoice = _final(client, quote["id"]).json()
    item_id = sent["items"][0]["id"]

    changed = client.put(
        f"/api/invoices/{sent['id']}/items/{item_id}",
        json={"description": "Abschlag 50 % gemäß Angebot A-10000 – bei Auftrag",
              "quantity": 1, "unit_price": 1000},
    )

    assert changed.status_code == 200, changed.text
    refreshed = client.get(f"/api/invoices/{invoice['id']}").json()
    # 4.000 netto + 760 Steuer − (1.000 netto + 190 Steuer) = 3.570 Restbetrag.
    assert refreshed["total_brutto"] == 3570.0


def test_only_quotes_can_become_a_final_invoice(artist_api):
    client, _company, payload, _session = artist_api
    invoice = client.post("/api/invoices", json=payload).json()

    response = _final(client, invoice["id"])

    assert response.status_code == 400, response.text


def test_a_second_final_invoice_is_rejected_until_the_first_is_cancelled(artist_api):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    sent = _down_payment(client, quote["id"], 0)
    _send(client, sent["id"])
    first = _final(client, quote["id"]).json()

    blocked = _final(client, quote["id"])
    assert blocked.status_code == 409, blocked.text
    assert "Schlussrechnung" in blocked.json()["detail"]

    _cancel(client, first["id"])
    again = _final(client, quote["id"])
    assert again.status_code == 201, again.text


def test_a_final_invoice_needs_an_issued_down_payment(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload, vat_rate=19)

    response = _final(client, quote["id"])

    assert response.status_code == 409, response.text
    assert "gestellten Abschlagsrechnung" in response.json()["detail"]
    assert client.get("/api/invoices").json() == []


def test_a_cancelled_down_payment_does_not_qualify_a_final_invoice(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload, vat_rate=19)
    cancelled = _down_payment(client, quote["id"], 0)
    _cancel(client, cancelled["id"])

    response = _final(client, quote["id"])

    assert response.status_code == 409, response.text
    invoices = client.get("/api/invoices").json()
    assert all(item["is_final_invoice"] is False for item in invoices)


def test_a_final_invoice_is_distinguishable_from_a_normal_conversion(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload, vat_rate=0)

    converted = client.post(f"/api/invoices/{quote['id']}/convert").json()

    assert converted["is_final_invoice"] is False
    assert converted["down_payment_index"] is None
