"""Abrechnungsstand und Beträge auf der Angebotsseite (#499).

Der Abrechnungsstand zählt die gestellten Rechnungen zum Angebot (nicht storniert,
nicht im Entwurf) gegen das Angebotsbrutto. Netto, USt und Gesamt kommen aus dem
Dokument selbst.
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


def _settlement(client, quote_id: int) -> dict:
    quote = client.get(f"/api/invoices/{quote_id}").json()
    assert quote["settlement"] is not None
    return quote["settlement"]


def _set_status(client, invoice_id: int, status: str) -> None:
    response = client.put(f"/api/invoices/{invoice_id}/status", json={"status": status})
    assert response.status_code == 200, response.text


def test_a_fresh_quote_has_nothing_billed(artist_api):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload)

    settlement = _settlement(client, quote["id"])
    assert settlement["billed_brutto"] == 0
    assert settlement["total_brutto"] == quote["total_brutto"]
    assert settlement["open_brutto"] == quote["total_brutto"]
    assert settlement["billed_count"] == 0


def test_an_issued_down_payment_counts_as_billed(artist_api):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload)
    down = client.post(f"/api/invoices/{quote['id']}/down-payment", json={"installment_index": 0})
    assert down.status_code == 201, down.text

    # Ein Entwurf ist noch nicht gestellt und zählt nicht mit.
    assert _settlement(client, quote["id"])["billed_brutto"] == 0

    _set_status(client, down.json()["id"], "SENT")
    settlement = _settlement(client, quote["id"])
    assert settlement["billed_brutto"] == down.json()["total_brutto"]
    assert settlement["total_brutto"] == quote["total_brutto"]
    assert settlement["open_brutto"] == round(quote["total_brutto"] - down.json()["total_brutto"], 2)
    assert settlement["billed_count"] == 1


def test_a_cancelled_invoice_does_not_count(artist_api):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload)
    down = client.post(f"/api/invoices/{quote['id']}/down-payment", json={"installment_index": 0})
    assert down.status_code == 201, down.text
    _set_status(client, down.json()["id"], "SENT")

    _set_status(client, down.json()["id"], "CANCELLED")

    settlement = _settlement(client, quote["id"])
    assert settlement["billed_brutto"] == 0
    assert settlement["open_brutto"] == quote["total_brutto"]


def test_the_final_invoice_closes_the_remaining_amount(artist_api):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload)
    down = client.post(f"/api/invoices/{quote['id']}/down-payment", json={"installment_index": 0})
    assert down.status_code == 201, down.text
    _set_status(client, down.json()["id"], "SENT")

    final = client.post(f"/api/invoices/{quote['id']}/final-invoice")
    assert final.status_code == 201, final.text
    _set_status(client, final.json()["id"], "SENT")

    settlement = _settlement(client, quote["id"])
    assert settlement["billed_count"] == 2
    assert settlement["billed_brutto"] == quote["total_brutto"]
    assert settlement["open_brutto"] == 0


def test_the_settlement_is_also_part_of_the_quote_list(artist_api):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload)

    listed = client.get("/api/invoices?document_type=QUOTE").json()
    assert len(listed) == 1
    assert listed[0]["settlement"]["total_brutto"] == quote["total_brutto"]
    assert listed[0]["settlement"]["billed_brutto"] == 0


def test_the_quote_reports_net_vat_and_gross(artist_api):
    client, company, payload, _session = artist_api
    company.is_small_business = False
    quote = _quote(client, payload | {"vat_rate": 19, "ust_enabled": True, "items": [
        {"description": "Website", "quantity": 1, "unit_price": 1000},
    ]})

    detail = client.get(f"/api/invoices/{quote['id']}").json()
    assert detail["total_net"] == 1000
    assert detail["vat_rate"] == 19
    assert detail["total_brutto"] == 1190


def test_an_invoice_has_no_settlement(artist_api):
    client, _company, payload, _session = artist_api
    invoice = client.post("/api/invoices", json=payload).json()

    detail = client.get(f"/api/invoices/{invoice['id']}").json()
    assert detail["settlement"] is None
    assert detail["billing"] is None


@pytest.mark.parametrize("status", ["DRAFT", "REJECTED"])
def test_a_draft_or_rejected_quote_is_not_billable_but_reports_its_stand(artist_api, status):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload, status=status)

    settlement = _settlement(client, quote["id"])
    assert settlement["billed_brutto"] == 0
    assert settlement["open_brutto"] == quote["total_brutto"]
