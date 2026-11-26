"""Ein Abrechnungsweg pro Angebot (#495).

Zwei Wege: Vollrechnung (Umwandeln) oder Abschläge plus genau eine Schlussrechnung.
Abrechnen geht nur aus „Gesendet“ oder „Angenommen“.
"""
from __future__ import annotations

import pytest

from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)

PLAN = [
    {"percent": 40, "label": "bei Auftrag"},
    {"percent": 60, "label": "nach Abnahme"},
]


def _quote(client, payload: dict, status: str = "SENT", **overrides) -> dict:
    body = payload | {"document_type": "QUOTE", "payment_plan": PLAN} | overrides
    response = client.post("/api/invoices", json=body)
    assert response.status_code == 201, response.text
    quote = response.json()
    if status != "DRAFT":
        changed = client.put(f"/api/invoices/{quote['id']}/status", json={"status": status})
        assert changed.status_code == 200, changed.text
    return quote


def _convert(client, quote_id: int):
    return client.post(f"/api/invoices/{quote_id}/convert")


def _down_payment(client, quote_id: int, index: int):
    return client.post(f"/api/invoices/{quote_id}/down-payment", json={"installment_index": index})


def _final(client, quote_id: int):
    return client.post(f"/api/invoices/{quote_id}/final-invoice")


def _set_status(client, invoice_id: int, status: str) -> None:
    response = client.put(f"/api/invoices/{invoice_id}/status", json={"status": status})
    assert response.status_code == 200, response.text


def _invoice_count(client) -> int:
    return len([doc for doc in client.get("/api/invoices").json() if doc["document_type"] == "INVOICE"])


@pytest.mark.parametrize("status", ["DRAFT", "REJECTED"])
@pytest.mark.parametrize("action", ["convert", "down_payment"])
def test_a_draft_or_rejected_quote_cannot_be_billed(artist_api, status, action):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload, status=status)

    response = _convert(client, quote["id"]) if action == "convert" else _down_payment(client, quote["id"], 0)

    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert ("Entwurf" in detail) if status == "DRAFT" else ("abgelehnt" in detail)
    assert _invoice_count(client) == 0
    assert client.get(f"/api/invoices/{quote['id']}").json()["status"] == status


def test_a_converted_quote_cannot_be_converted_again(artist_api):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload)
    first = _convert(client, quote["id"]).json()

    response = _convert(client, quote["id"])

    assert response.status_code == 409, response.text
    assert f"Rechnung {first['nr']}" in response.json()["detail"]
    assert _invoice_count(client) == 1


def test_a_quote_with_a_down_payment_cannot_be_converted(artist_api):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload)
    assert _down_payment(client, quote["id"], 0).status_code == 201

    response = _convert(client, quote["id"])

    assert response.status_code == 409, response.text
    assert "Schlussrechnung" in response.json()["detail"]
    assert _invoice_count(client) == 1


def test_a_converted_quote_gets_no_down_payment_and_no_final_invoice(artist_api):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload)
    full = _convert(client, quote["id"]).json()

    down = _down_payment(client, quote["id"], 0)
    final = _final(client, quote["id"])

    assert down.status_code == 409, down.text
    assert final.status_code == 409, final.text
    assert f"Rechnung {full['nr']}" in down.json()["detail"]
    assert _invoice_count(client) == 1


def test_no_further_installment_after_the_final_invoice(artist_api):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload)
    first = _down_payment(client, quote["id"], 0).json()
    _set_status(client, first["id"], "SENT")
    final = _final(client, quote["id"])
    assert final.status_code == 201, final.text

    response = _down_payment(client, quote["id"], 1)

    assert response.status_code == 409, response.text
    assert f"Schlussrechnung {final.json()['nr']}" in response.json()["detail"]
    assert _invoice_count(client) == 2


def test_final_invoice_waits_for_every_draft_down_payment(artist_api):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload)
    issued = _down_payment(client, quote["id"], 0).json()
    draft = _down_payment(client, quote["id"], 1).json()
    _set_status(client, issued["id"], "SENT")

    billing = _billing(client, quote["id"])["final_invoice"]
    response = _final(client, quote["id"])

    assert billing["allowed"] is False
    assert billing["invoice_id"] == draft["id"]
    assert "Entwurf" in billing["reason"]
    assert response.status_code == 409
    _set_status(client, draft["id"], "CANCELLED")
    assert _final(client, quote["id"]).status_code == 201


@pytest.mark.parametrize("path", ["status", "bulk-status", "send", "payment-link"])
def test_legacy_draft_cannot_be_issued_after_final_invoice(artist_api, path):
    from data import Invoice, InvoiceStatus

    client, _company, payload, session = artist_api
    quote = _quote(client, payload)
    issued = _down_payment(client, quote["id"], 0).json()
    draft = _down_payment(client, quote["id"], 1).json()
    _set_status(client, issued["id"], "SENT")
    _set_status(client, draft["id"], "CANCELLED")
    assert _final(client, quote["id"]).status_code == 201
    legacy = session.get(Invoice, draft["id"])
    legacy.status = InvoiceStatus.DRAFT
    session.add(legacy)
    session.commit()

    if path == "status":
        response = client.put(f"/api/invoices/{draft['id']}/status", json={"status": "SENT"})
    elif path == "bulk-status":
        response = client.post("/api/invoices/bulk-status", json={"invoice_ids": [draft["id"]], "status": "SENT"})
    elif path == "send":
        response = client.post(f"/api/invoices/{draft['id']}/send")
    else:
        response = client.post(f"/api/invoices/{draft['id']}/payment-link")
    assert response.status_code == 409, response.text
    assert "Schlussrechnung" in response.json()["detail"]


def test_cancelling_the_full_invoice_frees_the_quote_again(artist_api):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload)
    full = _convert(client, quote["id"]).json()
    _set_status(client, full["id"], "CANCELLED")

    assert _down_payment(client, quote["id"], 0).status_code == 201


def _billing(client, quote_id: int) -> dict:
    return client.get(f"/api/invoices/{quote_id}").json()["billing"]


def test_the_quote_api_tells_which_billing_actions_are_allowed(artist_api):
    client, _company, payload, _session = artist_api
    draft = _quote(client, payload, status="DRAFT")
    sent = _quote(client, payload)

    assert _billing(client, draft["id"])["convert"] == {
        "allowed": False,
        "reason": "Ein Entwurf lässt sich nicht abrechnen. Senden Sie das Angebot zuerst.",
        "invoice_id": None,
        "invoice_nr": None,
    }
    open_billing = _billing(client, sent["id"])
    assert open_billing["requires_acceptance"] is True
    assert open_billing["convert"]["allowed"] is True
    assert open_billing["down_payment"]["allowed"] is True
    assert open_billing["final_invoice"]["allowed"] is False


def test_a_blocked_action_names_the_invoice_that_blocks_it(artist_api):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload)
    down = _down_payment(client, quote["id"], 0).json()

    billing = _billing(client, quote["id"])

    assert billing["requires_acceptance"] is False
    assert billing["convert"]["allowed"] is False
    assert (billing["convert"]["invoice_id"], billing["convert"]["invoice_nr"]) == (down["id"], down["nr"])
    assert billing["final_invoice"]["invoice_id"] == down["id"]
    assert client.get(f"/api/invoices/{down['id']}").json()["billing"] is None


OVER_100 = [{"percent": 80, "label": "bei Auftrag"}, {"percent": 50, "label": "nach Abnahme"}]


def test_a_payment_plan_over_100_percent_cannot_be_created(artist_api):
    client, company, payload, _session = artist_api

    response = client.post("/api/invoices", json=payload | {"document_type": "QUOTE", "payment_plan": OVER_100})

    assert response.status_code == 422, response.text
    assert "130 %" in response.text
    assert company.next_quote_nr == 10000


def test_a_payment_plan_over_100_percent_cannot_be_saved(artist_api):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload)

    response = client.put(f"/api/invoices/{quote['id']}", json={"payment_plan": OVER_100})

    assert response.status_code == 422, response.text
    plan = client.get(f"/api/invoices/{quote['id']}").json()["payment_plan"]
    assert [rate["percent"] for rate in plan] == [40, 60]


def test_a_payment_plan_under_100_percent_is_saved(artist_api):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload)

    response = client.put(f"/api/invoices/{quote['id']}", json={"payment_plan": [{"percent": 30, "label": ""}]})

    assert response.status_code == 200, response.text
