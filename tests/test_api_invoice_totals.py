"""Die Beleg-Antwort liefert `totals` aus den Belegsummen (#507)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)


def test_invoice_with_7_percent_returns_totals_matching_the_stored_amount(artist_api):
    client, company, payload, _ = artist_api
    company.is_small_business = False
    created = client.post("/api/invoices", json=payload | {"vat_rate": 7})
    assert created.status_code == 201, created.text

    doc = client.get(f"/api/invoices/{created.json()['id']}").json()

    assert doc["totals"] == {"net": 300.0, "vat_rate": 7.0, "tax": 21.0, "gross": 321.0, "payable": 321.0}
    assert doc["total_brutto"] == pytest.approx(doc["totals"]["payable"])


def test_small_business_invoice_returns_totals_without_vat(artist_api):
    client, _, payload, _ = artist_api
    doc = client.post("/api/invoices", json=payload | {"vat_rate": 19}).json()

    assert doc["totals"] == {"net": 300.0, "vat_rate": 0.0, "tax": 0.0, "gross": 300.0, "payable": 300.0}
    assert doc["total_brutto"] == pytest.approx(300)


def test_totals_follow_an_item_change_together_with_the_stored_amount(artist_api):
    client, company, payload, _ = artist_api
    company.is_small_business = False
    doc = client.post("/api/invoices", json=payload | {"vat_rate": 19}).json()

    added = client.post(f"/api/invoices/{doc['id']}/items",
                        json={"description": "Anfahrt", "quantity": 1, "unit_price": 100}).json()

    assert added["totals"] == {"net": 400.0, "vat_rate": 19.0, "tax": 76.0, "gross": 476.0, "payable": 476.0}
    assert added["total_brutto"] == pytest.approx(476)


def test_openapi_documents_totals_on_the_invoice_read_model(artist_api):
    client, _, _, _ = artist_api
    components = client.get("/openapi.json").json()["components"]["schemas"]

    assert set(components["TotalsRead"]["required"]) == {"net", "vat_rate", "tax", "gross", "payable"}
    assert "totals" in components["InvoiceRead"]["properties"]
