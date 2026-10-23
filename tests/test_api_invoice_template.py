"""The shared invoice template, observed through the invoice API with real PDFs."""
from __future__ import annotations

import importlib

from pdf_text import pdf_text
from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)

layout = importlib.import_module("services.invoice_pdf_layout")


def _preview(client, payload):
    response = client.post("/api/invoices/preview-pdf", json=payload)
    assert response.status_code == 200, response.text
    return response.content


def test_preview_embeds_the_bundled_fonts(artist_api):
    client, _, payload, _ = artist_api
    pdf = _preview(client, payload)
    assert b"IBMPlexSans" in pdf
    text = pdf_text(pdf)
    assert "Musterstraße" in text
    assert "300,00 €" in text


def test_invoice_is_still_created_without_the_font_files(artist_api, monkeypatch, tmp_path):
    client, _, payload, _ = artist_api
    monkeypatch.setattr(layout, "FONT_DIR", tmp_path)
    pdf = _preview(client, payload)
    assert b"IBMPlex" not in pdf
    assert b"Helvetica" in pdf
    text = pdf_text(pdf)
    assert "Musterstraße" in text
    assert "300,00 €" in text


def test_service_date_is_written_day_month_year(artist_api):
    client, _, payload, _ = artist_api
    payload["delivery_date"] = "2026-09-19"
    text = pdf_text(_preview(client, payload))
    assert "19.09.2026" in text
    assert "2026-09-19" not in text


def test_service_period_is_written_day_month_year(artist_api):
    client, _, payload, _ = artist_api
    payload["service_from"] = "2026-09-19"
    payload["service_to"] = "2026-09-20"
    text = pdf_text(_preview(client, payload))
    assert "19.09.2026 bis 20.09.2026" in text
    assert "2026-09" not in text
