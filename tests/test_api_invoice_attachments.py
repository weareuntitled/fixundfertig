"""Invoice attachments: link existing documents and send them with the email."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)

invoices = importlib.import_module("invoices")
data = importlib.import_module("data")


def _add_document(session, company, *, title: str = "Wix-Beleg", filename: str = "wix.pdf"):
    document = data.Document(
        company_id=int(company.id),
        original_filename=filename,
        filename=filename,
        title=title,
        mime="application/pdf",
        mime_type="application/pdf",
        size_bytes=321,
        size=321,
        storage_key=f"companies/{company.id}/documents/1/{filename}",
        storage_path=f"companies/{company.id}/documents/1/{filename}",
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def _create_invoice(client, payload, session):
    customer = session.get(data.Customer, payload["customer_id"])
    customer.email = "buchhaltung@club.example"
    session.add(customer)
    session.commit()
    created = client.post("/api/invoices", json=payload)
    assert created.status_code == 201, created.text
    return created.json()


def test_attachment_is_returned_with_the_invoice(artist_api):
    client, company, payload, session = artist_api
    invoice = _create_invoice(client, payload, session)
    document = _add_document(session, company)

    response = client.post(
        f"/api/invoices/{invoice['id']}/attachments",
        json={"document_id": document.id},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["attachments"][0]["document_id"] == document.id
    assert body["attachments"][0]["filename"] == "wix.pdf"

    fetched = client.get(f"/api/invoices/{invoice['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["attachments"][0]["title"] == "Wix-Beleg"


def test_same_document_cannot_be_attached_twice(artist_api):
    client, company, payload, session = artist_api
    invoice = _create_invoice(client, payload, session)
    document = _add_document(session, company)

    url = f"/api/invoices/{invoice['id']}/attachments"
    assert client.post(url, json={"document_id": document.id}).status_code == 201
    duplicate = client.post(url, json={"document_id": document.id})
    assert duplicate.status_code == 409


def test_attachment_can_be_removed(artist_api):
    client, company, payload, session = artist_api
    invoice = _create_invoice(client, payload, session)
    document = _add_document(session, company)
    added = client.post(
        f"/api/invoices/{invoice['id']}/attachments",
        json={"document_id": document.id},
    ).json()
    attachment_id = added["attachments"][0]["id"]

    removed = client.delete(
        f"/api/invoices/{invoice['id']}/attachments/{attachment_id}"
    )
    assert removed.status_code == 200
    assert removed.json()["attachments"] == []
    assert session.get(data.Document, document.id) is not None


def _attach(client, invoice, document):
    response = client.post(
        f"/api/invoices/{invoice['id']}/attachments",
        json={"document_id": document.id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _capture_mails(monkeypatch, content: bytes | None = b"%PDF-1.4 beleg") -> list[dict]:
    mails: list[dict] = []
    monkeypatch.setattr(invoices, "send_email", lambda **kwargs: mails.append(kwargs) or True)
    monkeypatch.setattr(invoices, "read_document_bytes", lambda _document: content)
    return mails


def test_send_includes_selected_attachments(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    invoice = _create_invoice(client, payload, session)
    _attach(client, invoice, _add_document(session, company))
    mails = _capture_mails(monkeypatch)

    response = client.post(
        f"/api/invoices/{invoice['id']}/send",
        json={"include_attachments": True},
    )
    assert response.status_code == 200, response.text
    attachments = mails[-1]["attachments"]
    assert len(attachments) == 2
    assert attachments[1]["content"] == b"%PDF-1.4 beleg"
    assert attachments[1]["mime_type"] == "application/pdf"


def test_send_without_checkbox_keeps_only_the_invoice(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    invoice = _create_invoice(client, payload, session)
    _attach(client, invoice, _add_document(session, company))
    mails = _capture_mails(monkeypatch)

    response = client.post(
        f"/api/invoices/{invoice['id']}/send",
        json={"include_attachments": False},
    )
    assert response.status_code == 200, response.text
    assert len(mails[-1]["attachments"]) == 1


def test_invoice_pdf_stays_clean_with_attachments(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    invoice = _create_invoice(client, payload, session)
    mails = _capture_mails(monkeypatch)
    client.post(f"/api/invoices/{invoice['id']}/send", json={})
    plain_pdf = mails[-1]["attachments"][0]["content"]

    _attach(client, invoice, _add_document(session, company))
    client.post(f"/api/invoices/{invoice['id']}/send", json={"include_attachments": True})
    assert mails[-1]["attachments"][0]["content"] == plain_pdf


def test_send_fails_when_a_receipt_file_is_missing(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    invoice = _create_invoice(client, payload, session)
    _attach(client, invoice, _add_document(session, company))
    mails = _capture_mails(monkeypatch, content=None)

    response = client.post(
        f"/api/invoices/{invoice['id']}/send",
        json={"include_attachments": True},
    )
    assert response.status_code == 409
    assert mails == []


def test_one_document_can_be_linked_to_several_invoices(artist_api):
    client, company, payload, session = artist_api
    first = _create_invoice(client, payload, session)
    second = client.post("/api/invoices", json=payload).json()
    document = _add_document(session, company)

    _attach(client, first, document)
    _attach(client, second, document)

    listed = {inv["id"]: inv["attachments"] for inv in client.get("/api/invoices").json()}
    assert listed[first["id"]][0]["document_id"] == document.id
    assert listed[second["id"]][0]["document_id"] == document.id


def test_attachments_from_another_company_are_rejected(artist_api):
    client, company, payload, session = artist_api
    invoice = _create_invoice(client, payload, session)
    other = data.Company(name="Andere Firma")
    session.add(other)
    session.commit()
    foreign = _add_document(session, other)

    response = client.post(
        f"/api/invoices/{invoice['id']}/attachments",
        json={"document_id": foreign.id},
    )
    assert response.status_code == 404


def test_non_pdf_receipt_keeps_its_extension_and_names_are_unique(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    invoice = _create_invoice(client, payload, session)
    image = _add_document(session, company, title="Beleg", filename="scan.png")
    image.mime = image.mime_type = "image/png"
    session.add(image)
    session.commit()
    _attach(client, invoice, image)
    _attach(client, invoice, _add_document(session, company, title="Beleg", filename="a.pdf"))
    _attach(client, invoice, _add_document(session, company, title="Beleg", filename="b.pdf"))
    mails = _capture_mails(monkeypatch)

    client.post(f"/api/invoices/{invoice['id']}/send", json={"include_attachments": True})
    names = [a["filename"] for a in mails[-1]["attachments"][1:]]
    assert names == ["Beleg.png", "Beleg.pdf", "Beleg (2).pdf"]


def test_send_rejects_oversized_receipts(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    invoice = _create_invoice(client, payload, session)
    _attach(client, invoice, _add_document(session, company))
    mails = _capture_mails(monkeypatch, content=b"x" * (invoices.MAX_ATTACHMENT_BYTES + 1))

    response = client.post(f"/api/invoices/{invoice['id']}/send", json={"include_attachments": True})
    assert response.status_code == 413
    assert mails == []


def test_attachments_of_another_companys_invoice_are_not_reachable(artist_api):
    client, company, payload, session = artist_api
    other = data.Company(name="Andere Firma")
    session.add(other)
    session.commit()
    session.refresh(other)
    customer = data.Customer(company_id=int(other.id), kdnr=1, name="X", email="x@example.com")
    session.add(customer)
    session.commit()
    session.refresh(customer)
    foreign_invoice = data.Invoice(company_id=int(other.id), customer_id=int(customer.id), nr=1, date="2026-01-01", total_brutto=0.0)
    session.add(foreign_invoice)
    session.commit()
    session.refresh(foreign_invoice)
    document = _add_document(session, company)

    assert client.post(
        f"/api/invoices/{foreign_invoice.id}/attachments", json={"document_id": document.id}
    ).status_code == 404
    assert client.delete(f"/api/invoices/{foreign_invoice.id}/attachments/1").status_code == 404
