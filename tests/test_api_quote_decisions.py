"""Entscheidungen am Angebot (#497): gesendet markieren, Entscheidung zurücknehmen,
abgelehnte Angebote nur lesbar, Gültigkeit verlängern, Versandfehler in Alltagssprache.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)


def _create_quote(client, payload: dict, **overrides) -> dict:
    body = payload | {"document_type": "QUOTE"} | overrides
    response = client.post("/api/invoices", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _set_status(client, doc_id: int, value: str):
    return client.put(f"/api/invoices/{doc_id}/status", json={"status": value})


def _invoice_for_quote(client, quote_id: int) -> dict:
    """Eine Rechnung zum Angebot (Umwandeln) — damit das Angebot eine Rechnung hat."""
    response = client.post(f"/api/invoices/{quote_id}/convert")
    assert response.status_code == 201, response.text
    return response.json()


def test_a_draft_quote_can_be_marked_as_sent_without_a_mail_server(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)

    response = client.post(f"/api/invoices/{quote['id']}/mark-sent")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "SENT"
    assert client.get(f"/api/invoices/{quote['id']}").json()["status"] == "SENT"


def test_an_invoice_cannot_be_marked_as_sent(artist_api):
    client, _company, payload, _session = artist_api
    invoice = client.post("/api/invoices", json=payload).json()

    response = client.post(f"/api/invoices/{invoice['id']}/mark-sent")

    assert response.status_code == 400, response.text
    assert "Angebot" in response.json()["detail"]


def test_a_draft_quote_stays_unbillable(artist_api):
    """Entwürfe sind nicht abrechenbar — die Regel kommt aus #495 und gilt für jeden Weg.

    Hier nur geprüft, nicht erneut gebaut: der Server weist alle drei Abrechnungswege ab.
    """
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload, payment_plan=[{"percent": 40, "label": "bei Auftrag"}])

    convert = client.post(f"/api/invoices/{quote['id']}/convert")
    down_payment = client.post(f"/api/invoices/{quote['id']}/down-payment", json={"installment_index": 0})
    final_invoice = client.post(f"/api/invoices/{quote['id']}/final-invoice")

    assert [convert.status_code, down_payment.status_code, final_invoice.status_code] == [409, 409, 409]
    assert "Entwurf" in convert.json()["detail"]
    assert client.get("/api/invoices", params={"document_type": "INVOICE"}).json() == []


@pytest.mark.parametrize("decision", ["ACCEPTED", "REJECTED"])
def test_a_decision_can_be_taken_back_without_an_invoice(artist_api, decision):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    assert _set_status(client, quote["id"], decision).status_code == 200

    response = client.post(f"/api/invoices/{quote['id']}/mark-sent")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "SENT"
    assert client.get(f"/api/invoices/{quote['id']}").json()["status"] == "SENT"


def test_a_decision_with_an_invoice_stays_final(artist_api):
    """Mit Rechnung ist die Entscheidung endgültig: zurücknehmen gibt 409.

    Eine Rechnung entsteht nur aus einem angenommenen Angebot; ein abgelehntes Angebot
    hat deshalb nie eine Rechnung und bleibt immer zurücknehmbar.
    """
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    assert _set_status(client, quote["id"], "ACCEPTED").status_code == 200
    _invoice_for_quote(client, quote["id"])

    response = client.post(f"/api/invoices/{quote['id']}/mark-sent")

    assert response.status_code == 409, response.text
    assert "Rechnung" in response.json()["detail"]
    assert client.get(f"/api/invoices/{quote['id']}").json()["status"] == "ACCEPTED"


@pytest.mark.parametrize("decision", ["ACCEPTED", "REJECTED"])
def test_the_status_endpoint_takes_a_decision_back_too(artist_api, decision):
    """Der Rückweg läuft über dieselbe Regel: ohne Rechnung geht er, mit Rechnung nicht."""
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    assert _set_status(client, quote["id"], decision).status_code == 200

    response = _set_status(client, quote["id"], "SENT")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "SENT"


def test_the_status_endpoint_refuses_to_take_back_a_decision_with_an_invoice(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    assert _set_status(client, quote["id"], "ACCEPTED").status_code == 200
    _invoice_for_quote(client, quote["id"])

    response = _set_status(client, quote["id"], "SENT")

    assert response.status_code == 409, response.text
    assert client.get(f"/api/invoices/{quote['id']}").json()["status"] == "ACCEPTED"


def test_a_rejected_quote_cannot_be_changed(artist_api):
    """Ein abgelehntes Angebot ist nur noch lesbar."""
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    assert _set_status(client, quote["id"], "REJECTED").status_code == 200

    header = client.put(f"/api/invoices/{quote['id']}", json={"subject": "Geändert"})
    items = client.post(
        f"/api/invoices/{quote['id']}/items",
        json={"description": "Technik", "quantity": 1, "unit_price": 80},
    )

    assert [header.status_code, items.status_code] == [409, 409]
    reread = client.get(f"/api/invoices/{quote['id']}").json()
    assert reread["subject"] == quote["subject"]
    assert reread["items"] == quote["items"]


def test_an_expired_quote_can_extend_its_validity(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload, valid_until="2020-01-31")

    response = client.post(f"/api/invoices/{quote['id']}/extend-validity")

    assert response.status_code == 200, response.text
    expected = (date.today() + timedelta(days=30)).isoformat()
    assert response.json()["valid_until"] == expected
    assert client.get(f"/api/invoices/{quote['id']}").json()["valid_until"] == expected


@pytest.mark.parametrize("status", ["ACCEPTED", "REJECTED"])
def test_a_decided_quote_keeps_its_validity(artist_api, status):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload, valid_until="2020-01-31")
    assert _set_status(client, quote["id"], status).status_code == 200

    response = client.post(f"/api/invoices/{quote['id']}/extend-validity")

    assert response.status_code == 409, response.text
    assert client.get(f"/api/invoices/{quote['id']}").json()["valid_until"] == "2020-01-31"


def test_a_failed_send_says_it_in_plain_language(artist_api, monkeypatch):
    """Kein Fachwort im Fehlertext: der Dialog spricht mit dem Nutzer, nicht mit der Technik."""
    import importlib

    client, _company, payload, session = artist_api
    invoices = importlib.import_module("invoices")
    monkeypatch.setattr(invoices, "send_email", lambda **kwargs: False)
    customer = session.get(invoices.Customer, payload["customer_id"])
    customer.email = "buchhaltung@club.example"
    session.add(customer)
    session.commit()
    quote = _create_quote(client, payload)

    response = client.post(f"/api/invoices/{quote['id']}/send", json=None)

    assert response.status_code == 502, response.text
    detail = response.json()["detail"]
    assert "E-Mail-Versand" in detail
    for jargon in ("SMTP", "Connection", "connection refused"):
        assert jargon not in detail
