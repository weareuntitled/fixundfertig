"""Zahlungsplan in Raten am Angebot, gepflegt über die Rechnungs-API und gezeigt im PDF (#487)."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from pdf_text import pdf_strings
from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)

PLAN = [
    {"percent": 50, "label": "bei Auftrag"},
    {"percent": 50, "label": "nach Livegang"},
]


def _quote(payload: dict, **overrides) -> dict:
    return payload | {"document_type": "QUOTE", "date": "2026-10-23"} | overrides


def _create(client, body: dict) -> dict:
    response = client.post("/api/invoices", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _plan(doc: dict) -> list[tuple]:
    return [(rate["percent"], rate["label"], rate["amount"]) for rate in doc["payment_plan"]]


def _pdf(client, doc_id: int) -> list[str]:
    response = client.get(f"/api/invoices/{doc_id}/download")
    assert response.status_code == 200, response.text
    return pdf_strings(response.content)


def test_quote_keeps_its_installments_in_order_with_amounts_from_the_gross_total(artist_api):
    client, company, payload, _ = artist_api
    company.is_small_business = False

    quote = _create(client, _quote(payload, vat_rate=19, payment_plan=PLAN))

    assert quote["total_brutto"] == 357
    assert _plan(quote) == [(50, "bei Auftrag", 178.5), (50, "nach Livegang", 178.5)]
    assert _plan(client.get(f"/api/invoices/{quote['id']}").json()) == _plan(quote)


def test_installments_can_be_changed_reordered_and_removed(artist_api):
    client, _, payload, _ = artist_api
    quote = _create(client, _quote(payload, payment_plan=PLAN))

    reordered = client.put(f"/api/invoices/{quote['id']}", json={"payment_plan": [
        {"percent": 70, "label": "nach Livegang"},
        {"percent": 30, "label": "bei Auftrag"},
    ]})
    assert reordered.status_code == 200, reordered.text
    assert _plan(reordered.json()) == [(70, "nach Livegang", 210.0), (30, "bei Auftrag", 90.0)]

    removed = client.put(f"/api/invoices/{quote['id']}", json={"payment_plan": []})
    assert removed.status_code == 200, removed.text
    assert removed.json()["payment_plan"] == []


def test_a_plan_not_adding_up_to_100_percent_is_saved_anyway(artist_api):
    client, _, payload, _ = artist_api

    quote = _create(client, _quote(payload, payment_plan=[{"percent": 30, "label": "bei Auftrag"}]))

    assert _plan(quote) == [(30, "bei Auftrag", 90.0)]


def test_amounts_of_a_100_percent_plan_add_up_to_the_gross_total(artist_api):
    client, company, payload, _ = artist_api
    company.is_small_business = False
    thirds = [{"percent": 33.33, "label": "Start"}, {"percent": 33.33, "label": "Mitte"},
              {"percent": 33.34, "label": "Ende"}]
    body = _quote(payload, vat_rate=19, payment_plan=thirds,
                  items=[{"description": "Website", "quantity": 1, "unit_price": 1000}])

    quote = _create(client, body)

    amounts = [rate["amount"] for rate in quote["payment_plan"]]
    assert quote["total_brutto"] == 1190
    assert amounts == [396.63, 396.63, 396.74]
    assert round(sum(amounts), 2) == 1190


def test_installment_amounts_follow_position_changes(artist_api):
    client, _, payload, _ = artist_api
    quote = _create(client, _quote(payload, payment_plan=PLAN))

    added = client.post(f"/api/invoices/{quote['id']}/items",
                        json={"description": "Anfahrt", "quantity": 1, "unit_price": 100})

    assert _plan(added.json()) == [(50, "bei Auftrag", 200.0), (50, "nach Livegang", 200.0)]


def test_installment_needs_a_positive_percentage(artist_api):
    client, _, payload, _ = artist_api

    response = client.post("/api/invoices", json=_quote(payload, payment_plan=[{"percent": 0, "label": "x"}]))

    assert response.status_code == 422


def test_invoices_have_no_payment_plan(artist_api):
    client, _, payload, _ = artist_api

    invoice = _create(client, payload | {"payment_plan": PLAN})

    assert invoice["payment_plan"] == []
    rejected = client.put(f"/api/invoices/{invoice['id']}", json={"payment_plan": PLAN})
    assert rejected.status_code == 400


def test_quote_pdf_lists_each_installment_with_percent_occasion_and_amount(artist_api):
    client, company, payload, _ = artist_api
    company.is_small_business = False
    quote = _create(client, _quote(payload, vat_rate=19, payment_plan=PLAN))

    strings = _pdf(client, quote["id"])

    start = strings.index("ZAHLUNGSPLAN")
    assert strings[start + 1:start + 7] == [
        "50 %", "bei Auftrag", "178,50 €",
        "50 %", "nach Livegang", "178,50 €",
    ]


def test_quote_pdf_shows_the_edited_plan(artist_api):
    client, _, payload, _ = artist_api
    quote = _create(client, _quote(payload, payment_plan=PLAN))

    client.put(f"/api/invoices/{quote['id']}", json={"payment_plan": [{"percent": 100, "label": "nach Livegang"}]})

    strings = _pdf(client, quote["id"])
    start = strings.index("ZAHLUNGSPLAN")
    assert strings[start + 1:start + 4] == ["100 %", "nach Livegang", "300,00 €"]
    assert "bei Auftrag" not in strings


def test_draft_preview_shows_the_plan(artist_api):
    client, _, payload, _ = artist_api

    response = client.post("/api/invoices/preview-pdf", json=_quote(payload, payment_plan=PLAN))

    assert response.status_code == 200, response.text
    assert "ZAHLUNGSPLAN" in pdf_strings(response.content)


def test_quote_without_installments_has_no_plan_section(artist_api):
    client, _, payload, _ = artist_api
    quote = _create(client, _quote(payload))

    assert "ZAHLUNGSPLAN" not in _pdf(client, quote["id"])


def test_invoice_pdf_never_shows_a_plan(artist_api):
    client, _, payload, _ = artist_api
    invoice = _create(client, payload | {"payment_plan": PLAN})

    assert "ZAHLUNGSPLAN" not in _pdf(client, invoice["id"])


def test_startup_adds_payment_plan_and_vat_rate_columns(tmp_path):
    from sqlmodel import create_engine

    importlib.import_module("app.api")
    db = importlib.import_module("db")
    engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE invoice (id INTEGER PRIMARY KEY, customer_id INTEGER, date TEXT)")
        conn.exec_driver_sql("INSERT INTO invoice (customer_id, date) VALUES (1, '2025-01-01')")

    db.ensure_invoice_vat_rate_field(engine)
    db.ensure_invoice_payment_plan_field(engine)

    with engine.begin() as conn:
        row = conn.exec_driver_sql("SELECT vat_rate, payment_plan FROM invoice").fetchone()
    assert tuple(row) == (None, "[]")
