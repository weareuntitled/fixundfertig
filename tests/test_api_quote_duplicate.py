"""Angebot duplizieren erzeugt ein neues Angebot, keine Rechnung (#484 Review)."""
from __future__ import annotations

from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)

PLAN = [
    {"percent": 50, "label": "bei Auftrag"},
    {"percent": 50, "label": "nach Livegang"},
]
NET_4000 = [{"description": "Website", "quantity": 1, "unit_price": 4000}]


def _standard_company(company, session) -> None:
    company.is_small_business = False
    session.add(company)
    session.commit()


def _create_quote(client, payload: dict, **overrides) -> dict:
    body = payload | {
        "document_type": "QUOTE",
        "date": "2026-10-23",
        "items": NET_4000,
        "payment_plan": PLAN,
        "vat_rate": 19,
    } | overrides
    response = client.post("/api/invoices", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_duplicating_a_quote_creates_a_new_quote_with_its_own_number(artist_api):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload)

    response = client.post(f"/api/invoices/{quote['id']}/duplicate")

    assert response.status_code == 201, response.text
    copy = response.json()
    assert copy["id"] != quote["id"]
    assert copy["document_type"] == "QUOTE"
    assert copy["nr"] == "A-10001"
    assert copy["status"] == "DRAFT"
    assert copy["valid_until"] == quote["valid_until"]
    assert [(rate["percent"], rate["label"]) for rate in copy["payment_plan"]] == [
        (50.0, "bei Auftrag"),
        (50.0, "nach Livegang"),
    ]
    assert copy["total_brutto"] == quote["total_brutto"]
    assert [item["description"] for item in copy["items"]] == ["Website"]
    assert copy["quote_id"] is None
    assert copy["down_payment_index"] is None
    assert copy["is_final_invoice"] is False


def test_a_duplicated_quote_is_not_listed_as_an_invoice(artist_api):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload)

    copy = client.post(f"/api/invoices/{quote['id']}/duplicate").json()

    invoice_ids = [item["id"] for item in client.get("/api/invoices").json()]
    assert copy["id"] not in invoice_ids
    quote_ids = [item["id"] for item in client.get("/api/invoices?document_type=QUOTE").json()]
    assert {quote["id"], copy["id"]} <= set(quote_ids)
