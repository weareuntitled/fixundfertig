"""Line-Item-Vorschläge lesen nur Rechnungen, nie Angebote (#484 Review)."""
from __future__ import annotations

from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)


def _create(client, payload: dict, document_type: str, items: list[dict]) -> dict:
    body = payload | {"document_type": document_type, "items": items}
    response = client.post("/api/invoices", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_suggestions_ignore_positions_that_only_exist_on_a_quote(artist_api):
    client, _company, payload, _session = artist_api
    _create(client, payload, "QUOTE", [{"description": "Nur im Angebot", "quantity": 1, "unit_price": 500}])
    _create(client, payload, "INVOICE", [{"description": "In der Rechnung", "quantity": 1, "unit_price": 300}])

    response = client.get(f"/api/invoices/suggestions?customer_id={payload['customer_id']}")

    assert response.status_code == 200, response.text
    descriptions = [row["description"] for row in response.json()]
    assert "In der Rechnung" in descriptions
    assert "Nur im Angebot" not in descriptions
