"""Sending an Angebot by mail, observed through the send endpoint with the SMTP call replaced (#488)."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from pdf_text import pdf_strings
from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)
from test_api_invoice_attachments import _add_document, _attach

invoices = importlib.import_module("invoices")


@pytest.fixture
def quote_api(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    customer = session.get(invoices.Customer, payload["customer_id"])
    customer.email = "booking@club.example"
    session.add(customer)
    session.commit()
    mails: list[dict] = []
    monkeypatch.setattr(invoices, "send_email", lambda **kwargs: mails.append(kwargs) or True)
    monkeypatch.setattr(invoices, "read_document_bytes", lambda _document: b"%PDF-1.4 rider")

    def create(**overrides) -> dict:
        body = payload | {"document_type": "QUOTE", "status": "DRAFT", "date": "2026-10-23",
                          "valid_until": "2026-11-22"} | overrides
        response = client.post("/api/invoices", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    def send(quote: dict, **body) -> dict:
        response = client.post(f"/api/invoices/{quote['id']}/send", json=body or None)
        assert response.status_code == 200, response.text
        return response.json()

    return client, company, session, mails, create, send


def test_quote_mail_speaks_of_an_angebot_with_number_and_valid_until(quote_api):
    _, _, _, mails, create, send = quote_api
    quote = create()

    send(quote)
    mail = mails[-1]

    assert mail["subject"] == f"Angebot {quote['nr']} von Daniel S. — 300,00 €"
    for body in (mail["text"], mail["html"]):
        assert f"Angebot {quote['nr']}" in body
        assert "gültig bis 22.11.2026" in body
        assert "300,00 €" in body
        assert "Rechnung" not in body
        assert "überweisen" not in body
        assert "28.10.2026" not in body  # no payment due date


def test_quote_mail_with_a_personal_message_still_names_the_angebot_pdf(quote_api):
    _, _, _, mails, create, send = quote_api
    send(create(), message="Hier das Angebot für den 12.12.")
    for body in (mail := mails[-1])["text"], mail["html"]:
        assert "Hier das Angebot für den 12.12." in body
        assert "Das Angebot hängt als PDF an." in body


def test_quote_mail_with_its_own_subject_still_names_the_angebot(quote_api):
    """Auch mit eigenem Betreff spricht die Mail vom Angebot und nennt die Nummer."""
    _, _, _, mails, create, send = quote_api
    quote = create(subject="Hochzeit im Alten Land")

    send(quote)
    mail = mails[-1]

    assert mail["subject"] == f"Angebot {quote['nr']} — Hochzeit im Alten Land"
    assert quote["nr"] in mail["subject"]
    assert "Angebot" in mail["subject"]


def test_quote_mail_carries_the_quote_pdf_and_chosen_attachments(quote_api):
    client, company, session, mails, create, send = quote_api
    quote = create()
    _attach(client, quote, _add_document(session, company, title="Technik-Rider", filename="rider.pdf"))

    send(quote, include_attachments=True)
    attachments = mails[-1]["attachments"]

    assert [a["filename"] for a in attachments] == [f"angebot_{quote['nr']}.pdf", "Technik-Rider.pdf"]
    strings = pdf_strings(attachments[0]["content"])
    assert "ANGEBOT" in strings and "RECHNUNG" not in strings
    assert attachments[1]["content"] == b"%PDF-1.4 rider"


def test_sent_quote_shows_gesendet_in_detail_and_list(quote_api):
    client, _, _, _, create, send = quote_api
    quote = create()
    assert quote["status"] == "DRAFT"

    response = send(quote)

    assert response["message"] == "Angebot an booking@club.example gesendet"
    assert client.get(f"/api/invoices/{quote['id']}").json()["status"] == "SENT"
    listed = client.get("/api/invoices", params={"document_type": "QUOTE"}).json()
    assert [q["status"] for q in listed if q["id"] == quote["id"]] == ["SENT"]


def test_resending_an_edited_quote_attaches_the_new_pdf(quote_api):
    client, _, _, mails, create, send = quote_api
    quote = create()
    send(quote)

    edited = client.put(f"/api/invoices/{quote['id']}", json={"valid_until": "2026-12-01"})
    assert edited.status_code == 200, edited.text
    added = client.post(f"/api/invoices/{quote['id']}/items",
                        json={"description": "Anfahrt", "quantity": 1, "unit_price": 40})
    assert added.status_code == 201, added.text
    send(quote)

    strings = pdf_strings(mails[-1]["attachments"][0]["content"])
    assert "Anfahrt" in strings
    assert strings[strings.index("Gültig bis:") + 1] == "01.12.2026"
    assert "gültig bis 01.12.2026" in mails[-1]["text"]
    assert "Anfahrt" in pdf_strings(client.get(f"/api/invoices/{quote['id']}/download").content)


def test_failed_send_leaves_the_quote_a_draft(quote_api, monkeypatch):
    client, _, _, _, create, _ = quote_api
    quote = create()
    monkeypatch.setattr(invoices, "send_email", lambda **kwargs: False)

    response = client.post(f"/api/invoices/{quote['id']}/send")

    assert response.status_code == 502
    assert client.get(f"/api/invoices/{quote['id']}").json()["status"] == "DRAFT"


def test_quote_mail_carries_a_pdf_rendered_at_send_time(quote_api):
    _, company, session, mails, create, send = quote_api
    quote = create()
    company.email = "neu@daniel-s.example"
    session.add(company)
    session.commit()

    send(quote)

    assert "neu@daniel-s.example" in " ".join(pdf_strings(mails[-1]["attachments"][0]["content"]))
