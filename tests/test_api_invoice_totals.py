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

    assert doc["totals"] == {"net": 300.0, "vat_rate": 7.0, "tax": 21.0, "gross": 321.0,
        "deductions": [], "rest_net": 300.0, "rest_tax": 21.0, "payable": 321.0}
    assert doc["total_brutto"] == pytest.approx(doc["totals"]["payable"])


def test_small_business_invoice_returns_totals_without_vat(artist_api):
    client, _, payload, _ = artist_api
    doc = client.post("/api/invoices", json=payload | {"vat_rate": 19}).json()

    assert doc["totals"] == {"net": 300.0, "vat_rate": 0.0, "tax": 0.0, "gross": 300.0,
        "deductions": [], "rest_net": 300.0, "rest_tax": 0.0, "payable": 300.0}
    assert doc["total_brutto"] == pytest.approx(300)


def test_totals_follow_an_item_change_together_with_the_stored_amount(artist_api):
    client, company, payload, _ = artist_api
    company.is_small_business = False
    doc = client.post("/api/invoices", json=payload | {"vat_rate": 19}).json()

    added = client.post(f"/api/invoices/{doc['id']}/items",
                        json={"description": "Anfahrt", "quantity": 1, "unit_price": 100}).json()

    assert added["totals"] == {"net": 400.0, "vat_rate": 19.0, "tax": 76.0, "gross": 476.0,
        "deductions": [], "rest_net": 400.0, "rest_tax": 76.0, "payable": 476.0}
    assert added["total_brutto"] == pytest.approx(476)


def test_openapi_documents_totals_on_the_invoice_read_model(artist_api):
    client, _, _, _ = artist_api
    components = client.get("/openapi.json").json()["components"]["schemas"]

    assert set(components["TotalsRead"]["required"]) == {"net", "vat_rate", "tax", "gross", "rest_net", "rest_tax", "payable"}
    assert "deductions" in components["TotalsRead"]["properties"]
    assert "totals" in components["InvoiceRead"]["properties"]


# ---- Schlussrechnung (#510)

PLAN_30_30_40 = [
    {"percent": 30, "label": "bei Auftrag"},
    {"percent": 30, "label": "Zwischenstand"},
    {"percent": 40, "label": "bei Abnahme"},
]


def _ok(response):
    assert response.status_code in (200, 201), response.text
    return response.json()


def _final_invoice_after_two_down_payments(client, payload) -> tuple[list[dict], dict]:
    quote = _ok(client.post("/api/invoices", json=payload | {
        "document_type": "QUOTE", "subject": "Relaunch", "vat_rate": 19,
        "items": [{"description": "Website", "quantity": 1, "unit_price": 4000}],
        "payment_plan": PLAN_30_30_40,
    }))
    _ok(client.put(f"/api/invoices/{quote['id']}/status", json={"status": "SENT"}))
    downs = []
    for index in (0, 1):
        down = _ok(client.post(f"/api/invoices/{quote['id']}/down-payment", json={"installment_index": index}))
        _ok(client.put(f"/api/invoices/{down['id']}/status", json={"status": "SENT"}))
        downs.append(down)
    final = _ok(client.post(f"/api/invoices/{quote['id']}/final-invoice"))
    return downs, client.get(f"/api/invoices/{final['id']}").json()


def test_final_invoice_totals_carry_two_deductions_and_the_rest_matching_the_stored_amount(artist_api):
    client, company, payload, _ = artist_api
    company.is_small_business = False
    downs, final = _final_invoice_after_two_down_payments(client, payload)

    totals = final["totals"]
    assert (totals["net"], totals["vat_rate"], totals["tax"], totals["gross"]) == (4000.0, 19.0, 760.0, 4760.0)
    assert [(d["id"], d["nr"], d["net"], d["tax"], d["gross"]) for d in totals["deductions"]] == [
        (downs[0]["id"], downs[0]["nr"], 1200.0, 228.0, 1428.0),
        (downs[1]["id"], downs[1]["nr"], 1200.0, 228.0, 1428.0),
    ]
    assert (totals["rest_net"], totals["rest_tax"], totals["payable"]) == (1600.0, 304.0, 1904.0)
    assert final["total_brutto"] == pytest.approx(totals["payable"])


def test_small_business_final_invoice_totals_have_no_tax(artist_api):
    client, _, payload, _ = artist_api
    _downs, final = _final_invoice_after_two_down_payments(client, payload)

    totals = final["totals"]
    assert (totals["net"], totals["vat_rate"], totals["tax"], totals["gross"]) == (4000.0, 0.0, 0.0, 4000.0)
    assert [(d["net"], d["tax"], d["gross"]) for d in totals["deductions"]] == [(1200.0, 0.0, 1200.0)] * 2
    assert (totals["rest_net"], totals["rest_tax"], totals["payable"]) == (1600.0, 0.0, 1600.0)
    assert final["total_brutto"] == pytest.approx(1600)
