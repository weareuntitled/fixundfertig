"""Angebote annehmen, ablehnen; angenommene Angebote sind gesperrt (#492)."""
from __future__ import annotations

import pytest

from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)


def _create_quote(client, payload: dict) -> dict:
    response = client.post("/api/invoices", json=payload | {"document_type": "QUOTE"})
    assert response.status_code == 201, response.text
    return response.json()


def _set_status(client, doc_id: int, value: str):
    return client.put(f"/api/invoices/{doc_id}/status", json={"status": value})


@pytest.mark.parametrize("value", ["SENT", "ACCEPTED", "REJECTED", "DRAFT"])
def test_quote_status_can_be_set(artist_api, value):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)

    response = _set_status(client, quote["id"], value)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == value
    assert client.get(f"/api/invoices/{quote['id']}").json()["status"] == value


@pytest.mark.parametrize("value", ["OPEN", "PAID", "FINALIZED", "CANCELLED"])
def test_invoice_statuses_are_rejected_for_quotes(artist_api, value):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)

    response = _set_status(client, quote["id"], value)

    assert response.status_code == 400, response.text
    assert client.get(f"/api/invoices/{quote['id']}").json()["status"] == "DRAFT"


@pytest.mark.parametrize("value", ["ACCEPTED", "REJECTED"])
def test_quote_statuses_are_rejected_for_invoices(artist_api, value):
    client, _company, payload, _session = artist_api
    invoice = client.post("/api/invoices", json=payload).json()

    response = _set_status(client, invoice["id"], value)

    assert response.status_code == 400, response.text
    assert client.get(f"/api/invoices/{invoice['id']}").json()["status"] == "OPEN"


@pytest.mark.parametrize("value", ["DRAFT", "OPEN", "SENT", "PAID", "FINALIZED", "CANCELLED"])
def test_invoice_statuses_still_work_for_invoices(artist_api, value):
    client, _company, payload, _session = artist_api
    invoice = client.post("/api/invoices", json=payload).json()

    response = _set_status(client, invoice["id"], value)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == value


def _accepted_quote(client, payload: dict) -> dict:
    quote = _create_quote(client, payload)
    assert _set_status(client, quote["id"], "ACCEPTED").status_code == 200
    return client.get(f"/api/invoices/{quote['id']}").json()


def test_accepted_quote_header_cannot_be_changed(artist_api):
    client, _company, payload, _session = artist_api
    quote = _accepted_quote(client, payload)

    response = client.put(f"/api/invoices/{quote['id']}", json={"subject": "Geändert"})

    assert response.status_code == 409, response.text
    assert client.get(f"/api/invoices/{quote['id']}").json()["subject"] == quote["subject"]


def test_accepted_quote_positions_cannot_be_changed(artist_api):
    client, _company, payload, _session = artist_api
    quote = _accepted_quote(client, payload)
    item_id = quote["items"][0]["id"]
    base = f"/api/invoices/{quote['id']}/items"
    item = {"description": "Technik", "quantity": 1, "unit_price": 80}

    added = client.post(base, json=item)
    changed = client.put(f"{base}/{item_id}", json=item)
    removed = client.delete(f"{base}/{item_id}")

    assert [added.status_code, changed.status_code, removed.status_code] == [409, 409, 409]
    reread = client.get(f"/api/invoices/{quote['id']}").json()
    assert reread["items"] == quote["items"]
    assert reread["total_brutto"] == quote["total_brutto"]


@pytest.mark.parametrize("value", ["DRAFT", "SENT", "REJECTED"])
def test_quotes_that_are_not_accepted_stay_changeable(artist_api, value):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    _set_status(client, quote["id"], value)

    response = client.put(f"/api/invoices/{quote['id']}", json={"subject": "Geändert"})

    assert response.status_code == 200, response.text


@pytest.mark.parametrize(("before", "after"), [("DRAFT", "SENT"), ("ACCEPTED", "ACCEPTED"), ("REJECTED", "REJECTED")])
def test_sending_a_quote_only_moves_a_draft_to_sent(artist_api, monkeypatch, before, after):
    import importlib

    client, _company, payload, session = artist_api
    invoices = importlib.import_module("invoices")
    monkeypatch.setattr(invoices, "send_email", lambda **kwargs: True)
    customer = session.get(invoices.Customer, payload["customer_id"])
    customer.email = "buchhaltung@club.example"
    session.add(customer)
    session.commit()
    quote = _create_quote(client, payload)
    _set_status(client, quote["id"], before)

    response = client.post(f"/api/invoices/{quote['id']}/send", json=None)

    assert response.status_code == 200, response.text
    assert client.get(f"/api/invoices/{quote['id']}").json()["status"] == after


@pytest.mark.parametrize("value", ["OPEN", "PAID"])
def test_invoice_statuses_are_rejected_for_quotes_in_bulk(artist_api, value):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)

    response = client.post("/api/invoices/bulk-status", json={"invoice_ids": [quote["id"]], "status": value})

    assert response.status_code == 400, response.text
    assert client.get(f"/api/invoices/{quote['id']}").json()["status"] == "DRAFT"
