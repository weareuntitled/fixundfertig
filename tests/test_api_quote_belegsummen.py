"""Angebote, Umwandlung und Zahlungsplan rechnen über die Belegsummen (#512)."""
from __future__ import annotations

from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)

import data  # noqa: E402  (app/ liegt erst nach dem Fixture-Import im Pfad)

THIRDS = [
    {"percent": 33.33, "label": "Start"},
    {"percent": 33.33, "label": "Mitte"},
    {"percent": 33.34, "label": "Ende"},
]


def _quote(client, payload: dict, **overrides) -> dict:
    body = payload | {"document_type": "QUOTE", "date": "2026-10-23"} | overrides
    response = client.post("/api/invoices", json=body)
    assert response.status_code == 201, response.text
    quote = response.json()
    sent = client.put(f"/api/invoices/{quote['id']}/status", json={"status": "SENT"})
    assert sent.status_code == 200, sent.text
    return quote


def _with_vat(company, session) -> None:
    company.is_small_business = False
    session.add(company)
    session.commit()


def _make_legacy(session, quote_id: int, stored_gross: float) -> None:
    """Altbeleg: kein gespeicherter Satz, ein Bruttobetrag mit Rundungsrest aus dem Altsystem."""
    stored = session.get(data.Invoice, quote_id)
    stored.vat_rate = None
    stored.total_brutto = stored_gross
    session.add(stored)
    session.commit()


def test_installments_add_up_to_the_quote_gross_even_for_a_legacy_quote(artist_api):
    client, company, payload, session = artist_api
    _with_vat(company, session)
    quote = _quote(client, payload, vat_rate=19, payment_plan=THIRDS,
                   items=[{"description": "Website", "quantity": 1, "unit_price": 1000}])
    # 1190,40 € gespeichert: abgeleitet 19,0 %, die Belegsummen weisen 1190,00 € aus.
    _make_legacy(session, quote["id"], 1190.40)

    doc = client.get(f"/api/invoices/{quote['id']}").json()

    amounts = [rate["amount"] for rate in doc["payment_plan"]]
    assert doc["totals"]["gross"] == 1190.0
    assert amounts == [396.63, 396.63, 396.74]
    assert round(sum(amounts), 2) == doc["totals"]["gross"]


def test_converted_invoice_has_the_same_totals_as_the_quote_at_7_percent(artist_api):
    client, company, payload, session = artist_api
    _with_vat(company, session)
    # 3 × 33,335 € = 100,005 € netto: Rundung an der Grenze, 7 % USt.
    quote = _quote(client, payload, vat_rate=7,
                   items=[{"description": "Probe", "quantity": 3, "unit_price": 33.335}])

    invoice = client.post(f"/api/invoices/{quote['id']}/convert").json()

    assert quote["totals"] == {"net": 100.01, "vat_rate": 7.0, "tax": 7.0, "gross": 107.01, "payable": 107.01}
    assert invoice["totals"] == quote["totals"]
    assert invoice["total_brutto"] == quote["totals"]["gross"]


def test_converting_a_legacy_quote_bills_the_gross_the_quote_shows(artist_api):
    client, company, payload, session = artist_api
    _with_vat(company, session)
    quote = _quote(client, payload, vat_rate=19,
                   items=[{"description": "Website", "quantity": 1, "unit_price": 1000}])
    _make_legacy(session, quote["id"], 1190.40)
    shown = client.get(f"/api/invoices/{quote['id']}").json()["totals"]

    invoice = client.post(f"/api/invoices/{quote['id']}/convert").json()

    assert shown["gross"] == 1190.0
    assert invoice["totals"] == shown
    assert invoice["total_brutto"] == shown["gross"]


def test_small_business_quote_converts_without_vat(artist_api):
    client, _company, payload, _session = artist_api
    quote = _quote(client, payload, vat_rate=19)

    invoice = client.post(f"/api/invoices/{quote['id']}/convert").json()

    assert quote["totals"]["vat_rate"] == 0.0
    assert invoice["totals"] == quote["totals"]


def test_down_payment_bills_its_share_of_the_quote_net_and_matches_the_plan(artist_api):
    client, company, payload, session = artist_api
    _with_vat(company, session)
    halves = [{"percent": 50, "label": "bei Auftrag"}, {"percent": 50, "label": "nach Livegang"}]
    quote = _quote(client, payload, vat_rate=7, payment_plan=halves,
                   items=[{"description": "Probe", "quantity": 3, "unit_price": 33.335}])

    response = client.post(f"/api/invoices/{quote['id']}/down-payment", json={"installment_index": 0})

    assert response.status_code == 201, response.text
    invoice = response.json()
    # 50 % von 100,01 € netto = 50,005 € -> 50,01 €; 7 % USt = 3,50 €.
    assert invoice["totals"] == {"net": 50.01, "vat_rate": 7.0, "tax": 3.5, "gross": 53.51, "payable": 53.51}
    assert invoice["total_brutto"] == 53.51
    assert quote["payment_plan"][0]["amount"] == invoice["totals"]["gross"]
