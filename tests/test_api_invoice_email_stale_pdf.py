"""The mailed PDF always shows what the mail says, even when positions changed after the PDF was stored."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from sqlmodel import select

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from pdf_text import pdf_text
from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)

invoices = importlib.import_module("invoices")


@pytest.fixture
def stored_invoice(artist_api, monkeypatch):
    """An invoice whose PDF is stored, plus the mails the send endpoint hands to SMTP."""
    client, _company, payload, session = artist_api
    mails: list[dict] = []
    monkeypatch.setattr(invoices, "send_email", lambda **kwargs: mails.append(kwargs) or True)
    customer = session.get(invoices.Customer, payload["customer_id"])
    customer.email = "buchhaltung@club.example"
    session.add(customer)
    session.commit()
    created = client.post("/api/invoices", json=payload)
    assert created.status_code == 201, created.text
    invoice_id = created.json()["id"]
    assert client.post(f"/api/invoices/{invoice_id}/regenerate-pdf").status_code == 200
    invoice = session.get(invoices.Invoice, invoice_id)
    assert "300,00 €" in pdf_text(invoice.pdf_bytes)
    return client, session, invoice, mails


def _add_position_behind_the_apps_back(session, invoice, total: float) -> None:
    """Like a direct database edit: a new position and total, but the stored PDF stays as it was."""
    session.add(invoices.InvoiceItemModel(
        invoice_id=invoice.id, description="Betreuung der Website", quantity=0.5, unit_price=60.0,
    ))
    invoice.total_brutto = total
    session.add(invoice)
    session.commit()
    session.refresh(invoice)


def _revisions(session, invoice) -> list:
    return session.exec(
        select(invoices.InvoiceRevision).where(invoices.InvoiceRevision.invoice_id == invoice.id)
    ).all()


def test_unchanged_invoice_is_sent_with_its_stored_pdf(stored_invoice):
    client, session, invoice, mails = stored_invoice
    stored = bytes(invoice.pdf_bytes)
    revisions_before = len(_revisions(session, invoice))

    assert client.post(f"/api/invoices/{invoice.id}/send").status_code == 200

    assert mails[-1]["attachments"][0]["content"] == stored
    assert len(_revisions(session, invoice)) == revisions_before


def test_pdf_older_than_the_positions_is_renewed_before_sending(stored_invoice):
    client, session, invoice, mails = stored_invoice
    _add_position_behind_the_apps_back(session, invoice, total=330.0)
    revisions_before = len(_revisions(session, invoice))

    response = client.post(f"/api/invoices/{invoice.id}/send")

    assert response.status_code == 200, response.text
    attached = pdf_text(mails[-1]["attachments"][0]["content"])
    assert "Betreuung der Website" in attached
    assert "330,00 €" in attached
    assert "330,00 €" in mails[-1]["text"]
    session.refresh(invoice)
    assert bytes(invoice.pdf_bytes) == mails[-1]["attachments"][0]["content"]
    assert len(_revisions(session, invoice)) == revisions_before + 1


def test_pdf_without_a_stamp_is_renewed_before_sending(stored_invoice):
    """PDFs stored before the stamp existed cannot vouch for their amount."""
    client, session, invoice, mails = stored_invoice
    invoice.pdf_bytes = invoices.render_invoice_to_pdf_bytes(invoice=invoice).replace(b"ff-stamp:", b"xx-stamp:")
    session.add(invoice)
    session.commit()

    assert client.post(f"/api/invoices/{invoice.id}/send").status_code == 200

    session.refresh(invoice)
    assert b"ff-stamp:" in bytes(invoice.pdf_bytes)
    assert bytes(invoice.pdf_bytes) == mails[-1]["attachments"][0]["content"]


def test_total_that_disagrees_with_the_positions_stops_the_mail(stored_invoice):
    """A renewed PDF computes 330 € from the positions; a mail saying 999 € must not go out."""
    client, session, invoice, mails = stored_invoice
    _add_position_behind_the_apps_back(session, invoice, total=999.0)

    response = client.post(f"/api/invoices/{invoice.id}/send")

    assert response.status_code == 409
    assert "999,00 €" in response.json()["detail"]
    assert "330,00 €" in response.json()["detail"]
    assert mails == []
