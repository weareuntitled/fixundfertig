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
