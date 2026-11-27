"""PDF und E-Mail zeigen dieselben Belegsummen wie der gespeicherte Betrag (#508)."""
from __future__ import annotations

import importlib

from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)
from test_api_quote_documents import (
    _create_quote, _flat, _mail_for, _pdf, _post, _send, _standard_company,
)

invoices = importlib.import_module("invoices")
InvoiceItemModel = importlib.import_module("data").InvoiceItem

ITEMS = [{"description": "Website", "quantity": 1, "unit_price": 1000}]


def _create(client, payload: dict, **overrides) -> dict:
    response = client.post("/api/invoices", json=payload | {"items": ITEMS} | overrides)
    assert response.status_code == 201, response.text
    return response.json()


def _stored(client, invoice_id: int) -> float:
    return client.get(f"/api/invoices/{invoice_id}").json()["total_brutto"]


def test_invoice_with_19_percent_shows_one_amount_and_rate_everywhere(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    invoice = _create(client, payload, vat_rate=19)

    assert _stored(client, invoice["id"]) == 1190.0
    pdf = _flat(_pdf(client, invoice["id"]))
    assert "Zwischensumme 1.000,00 €" in pdf
    assert "Umsatzsteuer 19 % 190,00 €" in pdf
    assert "GESAMTBETRAG 1.190,00 €" in pdf
    mail = _mail_for(client, session, monkeypatch, payload, invoice["id"])
    assert "Zwischensumme: 1.000,00 €" in mail["text"]
    assert "MwSt. 19 %: 190,00 €" in mail["text"]
    assert "Gesamtbetrag: 1.190,00 €" in mail["text"]


def test_invoice_with_7_percent_names_7_percent_in_pdf_and_mail(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    invoice = _create(client, payload, vat_rate=7)

    assert _stored(client, invoice["id"]) == 1070.0
    pdf = _flat(_pdf(client, invoice["id"]))
    assert "Umsatzsteuer 7 % 70,00 €" in pdf
    assert "GESAMTBETRAG 1.070,00 €" in pdf
    mail = _mail_for(client, session, monkeypatch, payload, invoice["id"])
    assert "MwSt. 7 %: 70,00 €" in mail["text"]
    assert "Gesamtbetrag: 1.070,00 €" in mail["text"]
    assert mail["subject"].endswith("1.070,00 €")


def test_small_business_invoice_shows_no_tax_anywhere(artist_api, monkeypatch):
    client, _company, payload, session = artist_api  # Fixture-Firma ist Kleinunternehmer
    invoice = _create(client, payload, vat_rate=19)

    assert _stored(client, invoice["id"]) == 1000.0
    pdf = _flat(_pdf(client, invoice["id"]))
    assert "Umsatzsteuer nicht erhoben" in pdf
    assert "GESAMTBETRAG 1.000,00 €" in pdf
    mail = _mail_for(client, session, monkeypatch, payload, invoice["id"])["text"]
    assert "MwSt." not in mail
    assert "Gesamtbetrag: 1.000,00 €" in mail
    assert "§ 19 Abs. 1 UStG" in mail


def test_quote_shows_its_sum_in_pdf_and_mail(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)

    assert _stored(client, quote["id"]) == 4760.0
    pdf = _flat(_pdf(client, quote["id"]))
    assert "Umsatzsteuer 19 % 760,00 €" in pdf
    assert "GESAMTBETRAG 4.760,00 €" in pdf
    mail = _mail_for(client, session, monkeypatch, payload, quote["id"])["text"]
    assert "MwSt. 19 %: 760,00 €" in mail
    assert "Gesamtbetrag: 4.760,00 €" in mail


def test_down_payment_shows_net_and_tax_of_its_rate(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    down = _post(client, f"/api/invoices/{quote['id']}/down-payment", {"installment_index": 0})

    assert _stored(client, down["id"]) == 2380.0
    pdf = _flat(_pdf(client, down["id"]))
    assert "Zwischensumme 2.000,00 €" in pdf
    assert "Umsatzsteuer 19 % 380,00 €" in pdf
    assert "GESAMTBETRAG 2.380,00 €" in pdf
    mail = _mail_for(client, session, monkeypatch, payload, down["id"])["text"]
    assert "Zwischensumme: 2.000,00 €" in mail
    assert "MwSt. 19 %: 380,00 €" in mail
    assert "Gesamtbetrag: 2.380,00 €" in mail


def test_after_a_position_change_pdf_and_mail_show_the_new_amount(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    item_id = client.get(f"/api/invoices/{quote['id']}").json()["items"][0]["id"]

    changed = client.put(f"/api/invoices/{quote['id']}/items/{item_id}",
                         json={"description": "Website", "quantity": 2, "unit_price": 1500})
    assert changed.status_code == 200, changed.text

    assert _stored(client, quote["id"]) == 3570.0
    pdf = _flat(_pdf(client, quote["id"]))
    assert "Umsatzsteuer 19 % 570,00 €" in pdf
    assert "GESAMTBETRAG 3.570,00 €" in pdf
    mail = _mail_for(client, session, monkeypatch, payload, quote["id"])["text"]
    assert "Website (2 x 1.500,00 €): 3.000,00 €" in mail
    assert "Gesamtbetrag: 3.570,00 €" in mail


def test_position_with_quantity_zero_counts_zero_in_mail_and_pdf(artist_api, monkeypatch):
    """Altbelege können Platzhalter mit Menge 0 tragen (die API lässt keine neuen zu)."""
    client, company, payload, session = artist_api
    _standard_company(company, session)
    invoice = _create(client, payload, vat_rate=19)
    session.add(InvoiceItemModel(invoice_id=invoice["id"], description="Platzhalter", quantity=0, unit_price=50))
    session.commit()
    regenerated = client.post(f"/api/invoices/{invoice['id']}/regenerate-pdf")
    assert regenerated.status_code == 200, regenerated.text

    pdf = _flat(_pdf(client, invoice["id"]))
    assert "GESAMTBETRAG 1.190,00 €" in pdf
    mail = _mail_for(client, session, monkeypatch, payload, invoice["id"])["text"]
    assert "Platzhalter (0 x 50,00 €): 0,00 €" in mail
    assert "MwSt. 19 %: 190,00 €" in mail
    assert "Gesamtbetrag: 1.190,00 €" in mail


def test_legacy_invoice_without_stored_rate_names_the_derived_rate(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    invoice = _create(client, payload, vat_rate=7)
    stored = session.get(invoices.Invoice, invoice["id"])
    stored.vat_rate = None  # Altbeleg: nur Brutto gespeichert
    stored.pdf_bytes = None
    session.add(stored)
    session.commit()

    pdf = _flat(_pdf(client, invoice["id"]))
    assert "Umsatzsteuer 7 % 70,00 €" in pdf
    mail = _mail_for(client, session, monkeypatch, payload, invoice["id"])["text"]
    assert "MwSt. 7 %: 70,00 €" in mail
    assert "Gesamtbetrag: 1.070,00 €" in mail


def _final_with_two_down_payments(client, company, payload, session) -> dict:
    """Angebot 4.000 € netto, zwei gestellte Abschläge je 2.000 € netto, dann 1.000 € Zusatz."""
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    for index in (0, 1):
        down = _post(client, f"/api/invoices/{quote['id']}/down-payment", {"installment_index": index})
        _send(client, down["id"])
    final = _post(client, f"/api/invoices/{quote['id']}/final-invoice")
    added = client.post(f"/api/invoices/{final['id']}/items",
                        json={"description": "Zusatz", "quantity": 1, "unit_price": 1000})
    assert added.status_code == 201, added.text
    return added.json()


def test_final_invoice_mail_names_rest_net_and_tax_like_the_pdf(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    final = _final_with_two_down_payments(client, company, payload, session)

    # Gesamtleistung 5.000 + 950 = 5.950; Abzüge 4.760; Rest 1.000 netto + 190 Steuer.
    assert _stored(client, final["id"]) == 1190.0
    pdf = _flat(_pdf(client, final["id"]))
    assert "Gesamtleistung 5.000,00 € 950,00 € 5.950,00 €" in pdf
    assert "Restbetrag 1.000,00 € 190,00 € 1.190,00 €" in pdf
    mail = _mail_for(client, session, monkeypatch, payload, final["id"])["text"]
    assert "Gesamtleistung: 5.950,00 €" in mail
    assert "Restbetrag netto: 1.000,00 €" in mail
    assert "MwSt. 19 %: 190,00 €" in mail
    assert "Restbetrag: 1.190,00 €" in mail
    assert mail.index("abzüglich") < mail.index("Restbetrag netto") < mail.index("Restbetrag: ")


def test_draft_preview_reads_a_rate_of_one_as_one_percent(artist_api):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    response = client.post("/api/invoices/preview-pdf", json=payload | {"items": ITEMS, "vat_rate": 1})
    assert response.status_code == 200, response.text

    pdf = _flat(response.content)
    assert "Umsatzsteuer 1 % 10,00 €" in pdf
    assert "GESAMTBETRAG 1.010,00 €" in pdf
