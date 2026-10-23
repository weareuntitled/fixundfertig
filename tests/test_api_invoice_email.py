"""The invoice email, observed through the send endpoint with the SMTP call replaced."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)

invoices = importlib.import_module("invoices")


@pytest.fixture
def sent(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    mails: list[dict] = []
    monkeypatch.setattr(invoices, "send_email", lambda **kwargs: mails.append(kwargs) or True)

    def send(customer_name: str = "Club Beispiel", payment_link: str = "", message: str | None = None, **invoice_fields):
        customer = session.get(invoices.Customer, payload["customer_id"])
        customer.email = "buchhaltung@club.example"
        customer.name = customer_name
        session.add(customer)
        session.commit()
        created = client.post("/api/invoices", json=payload | invoice_fields)
        assert created.status_code == 201, created.text
        if payment_link:
            stored = session.get(invoices.Invoice, created.json()["id"])
            stored.payment_link_url = payment_link
            session.add(stored)
            session.commit()
        response = client.post(
            f"/api/invoices/{created.json()['id']}/send",
            json=None if message is None else {"message": message},
        )
        assert response.status_code == 200, response.text
        return mails[-1], created.json()

    return send, company


def test_mail_names_invoice_amount_and_the_same_due_date_as_the_pdf(sent):
    send, _ = sent
    mail, invoice = send(date="2026-10-23")
    for body in (mail["text"], mail["html"]):
        assert invoice["nr"] in body
        assert "300,00 €" in body
        assert "28.10.2026" in body
    assert "06.11.2026" not in mail["html"]


def test_mail_carries_the_pdf_and_both_text_versions(sent):
    send, _ = sent
    mail, invoice = send()
    assert mail["to"] == "buchhaltung@club.example"
    assert mail["text"].strip()
    assert mail["html"].startswith("<!DOCTYPE html>")
    assert mail["attachments"][0]["mime_type"] == "application/pdf"
    assert mail["attachments"][0]["content"].startswith(b"%PDF")


def test_mail_is_personal_and_signed_with_the_first_name(sent):
    send, _ = sent
    mail, _ = send()
    assert "Daniel S." in mail["html"]
    assert "DJ / Producer" in mail["html"]
    assert mail["text"].startswith("Hallo Club Beispiel,")
    assert mail["text"].rstrip().endswith("Liebe Grüße\nDaniel")
    assert "Mit freundlichen Grüßen" not in mail["text"] + mail["html"]


def test_mail_says_vat_is_not_charged_for_small_businesses(sent):
    send, _ = sent
    mail, _ = send()
    notice = "Als Kleinunternehmer im Sinne von § 19 Abs. 1 UStG wird keine Umsatzsteuer berechnet."
    assert notice in mail["text"]
    assert notice in mail["html"]


def test_mail_offers_no_online_payment(sent):
    send, _ = sent
    mail, _ = send(payment_link="https://pay.example.com/abc")
    for body in (mail["text"], mail["html"]):
        assert "pay.example.com" not in body
        assert "bezahlen" not in body.lower()


def test_mail_escapes_what_users_typed(sent):
    send, _ = sent
    mail, _ = send(customer_name="<script>alert(1)</script>")
    assert "<script>" not in mail["html"]
    assert "&lt;script&gt;" in mail["html"]


def test_mail_shows_vat_taken_from_the_invoice_total(sent):
    send, company = sent
    company.is_small_business = False
    mail, _ = send(vat_rate=19)
    for body in (mail["text"], mail["html"]):
        assert "MwSt. 19 %" in body
        assert "57,00 €" in body
        assert "357,00 €" in body
    assert "Kleinunternehmer" not in mail["text"]


def test_due_date_is_found_when_the_invoice_date_carries_a_time(sent):
    send, _ = sent
    mail, _ = send(date="2026-10-23T10:00:00")
    assert "28.10.2026" in mail["text"]


def test_personal_message_replaces_the_standard_intro(sent):
    send, _ = sent
    mail, _ = send(message="Danke für die geile Nacht!\n\nBis bald in der Hamma.")
    for body in (mail["text"], mail["html"]):
        assert "Danke für die geile Nacht!" in body
        assert "Bis bald in der Hamma." in body
        assert "danke für den Auftrag" not in body
        assert "hängt als PDF an" in body
    assert mail["text"].startswith("Hallo Club Beispiel,\n\nDanke für die geile Nacht!")
    assert "<br>" in mail["html"]


def test_personal_message_is_escaped(sent):
    send, _ = sent
    mail, _ = send(message="<b>fett</b> & <script>x</script>")
    assert "<script>" not in mail["html"]
    assert "&lt;b&gt;fett&lt;/b&gt; &amp;" in mail["html"]


@pytest.mark.parametrize("message", [None, "", "   \n "])
def test_without_a_message_the_standard_intro_stays(sent, message):
    send, _ = sent
    mail, _ = send(message=message)
    assert "danke für den Auftrag" in mail["text"]


def test_message_is_limited_to_two_thousand_characters(artist_api, sent):
    client, _, payload, _ = artist_api
    send, _ = sent
    send()
    created = client.post("/api/invoices", json=payload)
    response = client.post(f"/api/invoices/{created.json()['id']}/send", json={"message": "x" * 2001})
    assert response.status_code == 422
