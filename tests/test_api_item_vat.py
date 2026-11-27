"""Editing positions keeps the document's VAT rate in its gross total (invoices and quotes)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from pdf_text import pdf_strings
from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)


def _vat_rows(strings: list[str]) -> list[str]:
    start = strings.index("Zwischensumme")
    end = strings.index("GESAMTBETRAG") + 2
    return strings[start:end]


@pytest.mark.parametrize("document_type", ["INVOICE", "QUOTE"])
def test_item_crud_keeps_19_percent_vat_in_the_gross_total(artist_api, document_type):
    client, company, payload, _ = artist_api
    company.is_small_business = False
    created = client.post("/api/invoices", json=payload | {"vat_rate": 19, "document_type": document_type})
    assert created.status_code == 201, created.text
    doc = created.json()
    assert doc["total_brutto"] == 357
    item_id = doc["items"][0]["id"]

    added = client.post(f"/api/invoices/{doc['id']}/items",
                        json={"description": "Anfahrt", "quantity": 1, "unit_price": 100})
    assert added.status_code == 201, added.text
    assert added.json()["total_brutto"] == pytest.approx(476)

    changed = client.put(f"/api/invoices/{doc['id']}/items/{item_id}",
                         json={"description": "Live-Set", "quantity": 1, "unit_price": 200})
    assert changed.status_code == 200, changed.text
    assert changed.json()["total_brutto"] == pytest.approx(357)

    removed = client.delete(f"/api/invoices/{doc['id']}/items/{item_id}")
    assert removed.status_code == 200, removed.text
    assert removed.json()["total_brutto"] == pytest.approx(119)


def test_quote_pdf_shows_vat_after_editing_a_position(artist_api):
    client, company, payload, _ = artist_api
    company.is_small_business = False
    quote = client.post("/api/invoices", json=payload | {"vat_rate": 19, "document_type": "QUOTE"}).json()

    client.post(f"/api/invoices/{quote['id']}/items",
                json={"description": "Anfahrt", "quantity": 1, "unit_price": 100})

    strings = pdf_strings(client.get(f"/api/invoices/{quote['id']}/download").content)
    assert _vat_rows(strings) == [
        "Zwischensumme", "400,00 €", "Umsatzsteuer 19 %", "76,00 €", "GESAMTBETRAG", "476,00 €",
    ]


def test_vat_survives_deleting_every_position_and_adding_a_new_one(artist_api):
    client, company, payload, _ = artist_api
    company.is_small_business = False
    doc = client.post("/api/invoices", json=payload | {"vat_rate": 7}).json()

    client.delete(f"/api/invoices/{doc['id']}/items/{doc['items'][0]['id']}")
    added = client.post(f"/api/invoices/{doc['id']}/items",
                        json={"description": "Neu", "quantity": 1, "unit_price": 100})

    assert added.json()["total_brutto"] == pytest.approx(107)


def test_small_business_documents_stay_without_vat_after_item_crud(artist_api):
    client, _, payload, _ = artist_api
    doc = client.post("/api/invoices", json=payload | {"vat_rate": 19}).json()
    assert doc["total_brutto"] == 300

    added = client.post(f"/api/invoices/{doc['id']}/items",
                        json={"description": "Anfahrt", "quantity": 1, "unit_price": 100})

    assert added.json()["total_brutto"] == pytest.approx(400)


def test_stored_gross_follows_belegsummen_rounding_on_create_and_on_item_change(artist_api):
    """1,5 × 33,33 = 49,995 → Netto 50,00, USt 9,50, Brutto 59,50 (#506)."""
    client, company, payload, _ = artist_api
    company.is_small_business = False
    item = {"description": "Stunden", "quantity": 1.5, "unit_price": 33.33}
    created = client.post("/api/invoices", json=payload | {"vat_rate": 19, "items": [item]})
    assert created.status_code == 201, created.text
    doc = created.json()
    assert doc["total_brutto"] == 59.5

    item_url = f"/api/invoices/{doc['id']}/items/{doc['items'][0]['id']}"
    client.put(item_url, json=item | {"unit_price": 100})
    changed = client.put(item_url, json=item)
    assert changed.json()["total_brutto"] == 59.5


MIXED_RATES_MESSAGE = (
    "Ein Beleg hat genau einen Steuersatz. Die Positionen haben unterschiedliche Sätze "
    "(7 %, 19 %). Bitte für jeden Steuersatz einen eigenen Beleg anlegen."
)


def test_creating_a_document_with_mixed_position_rates_is_rejected(artist_api):
    """Ein Beleg hat genau einen Steuersatz (#509): gemischte Sätze → 422 mit deutscher Meldung."""
    client, company, payload, _ = artist_api
    company.is_small_business = False
    items = [
        {"description": "Live-Set", "quantity": 1, "unit_price": 200, "tax_rate": 19},
        {"description": "Buch", "quantity": 1, "unit_price": 20, "tax_rate": 7},
    ]
    response = client.post("/api/invoices", json=payload | {"vat_rate": 19, "items": items})

    assert response.status_code == 422, response.text
    assert response.json()["detail"] == MIXED_RATES_MESSAGE
    assert client.get("/api/invoices").json() == []


def test_creating_a_document_with_one_rate_on_every_position_succeeds(artist_api):
    client, company, payload, _ = artist_api
    company.is_small_business = False
    items = [
        {"description": "Buch", "quantity": 2, "unit_price": 50, "tax_rate": 7},
        {"description": "Heft", "quantity": 1, "unit_price": 100, "tax_rate": 7},
    ]
    body = {k: v for k, v in payload.items() if k != "vat_rate"} | {"items": items}
    response = client.post("/api/invoices", json=body)

    assert response.status_code == 201, response.text
    doc = response.json()
    assert doc["vat_rate"] == 7
    assert doc["total_brutto"] == 214
