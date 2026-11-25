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
