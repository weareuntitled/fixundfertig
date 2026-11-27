"""PDF und E-Mail zeigen dieselben Belegsummen wie der gespeicherte Betrag (#508)."""
from __future__ import annotations

import importlib

from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)
from test_api_quote_documents import (
    _create_quote, _flat, _mail_for, _pdf, _post, _send, _standard_company,
)

invoices = importlib.import_module("invoices")

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
