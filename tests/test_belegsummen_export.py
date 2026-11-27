"""Das Export-ZIP enthält PDFs mit denselben Belegsummen wie die API (#511)."""
from __future__ import annotations

import importlib
import io
import zipfile
from contextlib import contextmanager

from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)
from test_api_quote_documents import _flat, _standard_company

exports = importlib.import_module("exports")
Invoice = importlib.import_module("data").Invoice


def _export_zip(client, session, monkeypatch) -> zipfile.ZipFile:
    @contextmanager
    def same_session():
        yield session

    monkeypatch.setattr(exports, "get_session", same_session)
    client.app.include_router(exports.router)
    response = client.get("/api/exports/invoices-pdf?year=2026")
    assert response.status_code == 200, response.text
    return zipfile.ZipFile(io.BytesIO(response.content))


def _forget_stored_pdf(session, invoice_id: int) -> None:
    invoice = session.get(Invoice, invoice_id)
    invoice.pdf_bytes = None
    invoice.pdf_filename = ""
    session.add(invoice)
    session.commit()


def test_export_without_stored_pdf_shows_vat_and_the_api_amount(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    created = client.post("/api/invoices", json=payload | {
        "vat_rate": 19, "items": [{"description": "Website", "quantity": 1, "unit_price": 1000}],
    })
    assert created.status_code == 201, created.text
    invoice_id = created.json()["id"]
    totals = client.get(f"/api/invoices/{invoice_id}").json()["totals"]
    assert totals["payable"] == 1190.0
    _forget_stored_pdf(session, invoice_id)

    archive = _export_zip(client, session, monkeypatch)

    [name] = archive.namelist()
    pdf = _flat(archive.read(name))
    assert "Zwischensumme 1.000,00 €" in pdf
    assert "Umsatzsteuer 19 % 190,00 €" in pdf
    assert "GESAMTBETRAG 1.190,00 €" in pdf
