"""The shared invoice template, observed through the invoice API with real PDFs."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from pdf_text import pdf_pages, pdf_strings, pdf_text
from services.invoice_pdf import render_invoice_to_pdf_bytes
from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)
from test_invoice_pdf_buergerlicher_name import _make_company, _make_invoice


def _preview(client, payload):
    response = client.post("/api/invoices/preview-pdf", json=payload)
    assert response.status_code == 200, response.text
    return response.content


def test_invoice_is_set_in_helvetica_like_the_website(artist_api):
    client, _, payload, _ = artist_api
    pdf = _preview(client, payload)
    assert b"Helvetica" in pdf
    assert b"IBMPlex" not in pdf
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


def test_issuer_and_tax_details_appear_once_in_the_footer(artist_api):
    client, company, payload, _ = artist_api
    company.vat_id = "DE123456789"
    text = pdf_text(_preview(client, payload))
    assert text.count("Musterstraße 1") == 1
    assert text.count("123/456/78901") == 1
    assert text.count("DE123456789") == 1
    assert text.count("Künstlername") == 1
    assert text.count("RECHNUNGSAUSSTELLER") == 1


def test_every_page_of_a_long_invoice_has_footer_and_page_number(artist_api):
    client, _, payload, _ = artist_api
    payload["items"] = [
        {"description": f"Position {number}", "quantity": 1, "unit_price": 10}
        for number in range(1, 61)
    ]
    pages = pdf_pages(_preview(client, payload))
    assert len(pages) >= 2
    for number, page in enumerate(pages, start=1):
        assert "RECHNUNGSAUSSTELLER" in page
        assert f"Seite {number} / {len(pages)}" in page


def test_footer_leaves_out_columns_without_data(artist_api):
    client, company, payload, _ = artist_api
    company.email = ""
    company.phone = ""
    company.tax_id = ""
    company.vat_id = ""
    text = pdf_text(_preview(client, payload))
    assert "KONTAKT" not in text
    assert "STEUER" not in text
    assert "RECHNUNGSAUSSTELLER" in text


def test_top_of_the_invoice_reads_in_order(artist_api):
    client, _, payload, _ = artist_api
    payload["subject"] = "DJ-Set Hammahalle"
    strings = pdf_strings(_preview(client, payload))
    order = ["DANIEL S.", "DJ / PRODUCER", "RECHNUNG AN", "Club Beispiel", "RECHNUNG", "DJ-Set Hammahalle"]
    positions = [strings.index(entry) for entry in order]
    assert positions == sorted(positions)
    intro = next(line for line in strings if line.startswith("Vielen Dank"))
    assert positions[-1] < strings.index(intro)


def test_invoice_number_stands_between_the_label_and_the_subject(artist_api):
    client, _, payload, _ = artist_api
    created = client.post("/api/invoices", json=payload)
    assert created.status_code == 201, created.text
    invoice = created.json()
    strings = pdf_strings(client.get(f"/api/invoices/{invoice['id']}/download").content)
    number_index = next(i for i, line in enumerate(strings) if line.startswith("Nr. "))
    assert strings[number_index - 1] == "RECHNUNG"
    assert strings[number_index] == f"Nr. {invoice['nr']}"


def test_profession_is_named_once_in_the_header(artist_api):
    client, _, payload, _ = artist_api
    text = pdf_text(_preview(client, payload))
    assert text.lower().count("dj / producer") == 1


def test_dates_are_plain_label_and_value_lines(artist_api):
    client, _, payload, _ = artist_api
    payload["date"] = "2026-10-23"
    payload["delivery_date"] = "2026-09-19"
    strings = pdf_strings(_preview(client, payload))
    for label, value in (("Leistungsdatum:", "19.09.2026"), ("Rechnungsdatum:", "23.10.2026")):
        assert label in strings
        assert value in strings


def test_company_without_wordmark_keeps_its_name_in_the_header(artist_api):
    client, company, payload, _ = artist_api
    company.name = "Muster GmbH"
    company.business_type = "GmbH"
    strings = pdf_strings(_preview(client, payload))
    assert strings[0] == "Muster GmbH"


def test_table_shows_position_quantity_price_and_amount(artist_api):
    client, _, payload, _ = artist_api
    payload["items"] = [
        {"description": "DJ-Set", "quantity": 2, "unit_price": 150},
        {"description": "Technik", "quantity": 1, "unit_price": 49.9},
    ]
    strings = pdf_strings(_preview(client, payload))
    headers = ["POS.", "BESCHREIBUNG", "MENGE", "EINZELPREIS", "BETRAG"]
    header_positions = [strings.index(header) for header in headers]
    assert header_positions == sorted(header_positions)
    start = header_positions[-1] + 1
    assert strings[start:start + 5] == ["1", "DJ-Set", "2,00", "150,00 €", "300,00 €"]
    assert strings[start + 5:start + 10] == ["2", "Technik", "1,00", "49,90 €", "49,90 €"]


def test_long_description_is_wrapped_and_complete(artist_api):
    client, _, payload, _ = artist_api
    words = " ".join(f"Leistung{number}" for number in range(1, 40))
    payload["items"] = [{"description": words, "quantity": 1, "unit_price": 100}]
    strings = pdf_strings(_preview(client, payload))
    start = strings.index("1", strings.index("BETRAG")) + 1
    end = strings.index("1,00", start)
    assert end - start >= 2
    assert " ".join(strings[start:end]) == words


def test_following_pages_repeat_the_table_header(artist_api):
    client, _, payload, _ = artist_api
    payload["items"] = [
        {"description": f"Position {number}", "quantity": 1, "unit_price": 10}
        for number in range(1, 61)
    ]
    pages = pdf_pages(_preview(client, payload))
    assert len(pages) >= 2
    for page in pages:
        assert "BESCHREIBUNG" in page
        assert "BETRAG" in page


def test_small_business_totals_say_vat_is_not_charged(artist_api):
    client, _, payload, _ = artist_api
    strings = pdf_strings(_preview(client, payload))
    text = " ".join(strings)
    labels = ["Zwischensumme", "300,00 €", "Umsatzsteuer", "nicht erhoben", "GESAMTBETRAG", "300,00 €"]
    start = strings.index("Zwischensumme")
    assert strings[start:start + 6] == labels
    assert "Als Kleinunternehmer im Sinne von § 19 Abs. 1 UStG wird keine Umsatzsteuer berechnet." in text


def test_totals_with_vat_show_rate_and_amount():
    # The API does not hand a VAT rate to the renderer yet, so this uses the renderer directly.
    company = _make_company({"is_small_business": False})
    invoice = _make_invoice({"tax_rate": 19, "line_items": [
        SimpleNamespace(description="DJ-Set", quantity=2.0, unit_price=150.0),
    ]})
    strings = pdf_strings(render_invoice_to_pdf_bytes(invoice, company=company))
    text = " ".join(strings)
    start = strings.index("Zwischensumme")
    assert strings[start:start + 6] == [
        "Zwischensumme", "300,00 €", "Umsatzsteuer 19 %", "57,00 €", "GESAMTBETRAG", "357,00 €",
    ]
    assert "Kleinunternehmer" not in text
    assert "nicht erhoben" not in text


def test_payment_deadline_is_a_sentence_under_the_totals(artist_api):
    client, _, payload, _ = artist_api
    payload["date"] = "2026-10-23"
    strings = pdf_strings(_preview(client, payload))
    text = " ".join(strings)
    assert text.count("Zahlbar bis") == 1
    assert "Zahlbar bis 28.10.2026." in text
    assert strings.index("GESAMTBETRAG") < strings.index("Zahlbar bis")
    assert "Zahlbar bis:" not in strings


def test_payment_box_lists_account_details(artist_api):
    client, company, payload, _ = artist_api
    company.bank_name = "N26"
    created = client.post("/api/invoices", json=payload)
    assert created.status_code == 201, created.text
    invoice = created.json()
    strings = pdf_strings(client.get(f"/api/invoices/{invoice['id']}/download").content)
    start = strings.index("ZAHLUNGSINFORMATIONEN")
    box = strings[start:]
    assert "Ich bitte um Überweisung des Betrags auf das folgende Konto." in " ".join(box)
    rows = box[box.index("Kontoinhaber"):box.index("Verwendungszweck") + 2]
    assert rows == [
        "Kontoinhaber", "Anderer Kontoinhaber", "Bank", "N26",
        "IBAN", "DE89 3704 0044 0532 0130 00",
        "Verwendungszweck", invoice["nr"],
    ]


def test_account_holder_falls_back_to_the_legal_name(artist_api):
    client, company, payload, _ = artist_api
    company.account_holder = ""
    strings = pdf_strings(_preview(client, payload))
    assert strings[strings.index("Kontoinhaber") + 1] == "Daniel Beispiel"


def test_iban_is_written_once_in_groups_of_four(artist_api):
    client, _, payload, _ = artist_api
    text = pdf_text(_preview(client, payload))
    assert text.count("DE89 3704 0044 0532 0130 00") == 1
    assert "DE89370400440532013000" not in text


def test_payment_sentence_is_neutral_for_companies_without_artist_wordmark(artist_api):
    client, company, payload, _ = artist_api
    company.name = "Muster GmbH"
    company.business_type = "GmbH"
    text = " ".join(pdf_strings(_preview(client, payload)))
    assert "Bitte überweisen Sie den Betrag auf das folgende Konto." in text
    assert "Ich bitte um" not in text


def test_no_payment_box_without_bank_details(artist_api):
    client, company, payload, _ = artist_api
    company.iban = ""
    company.bank_name = ""
    text = pdf_text(_preview(client, payload))
    assert "ZAHLUNGSINFORMATIONEN" not in text
    assert "Kontoinhaber" not in text


def test_service_date_line_is_always_there(artist_api):
    client, _, payload, _ = artist_api
    payload["date"] = "2026-10-23"
    strings = pdf_strings(_preview(client, payload))
    assert strings[strings.index("Leistungsdatum:") + 1] == "wie Rechnungsdatum"
    assert strings[strings.index("Rechnungsdatum:") + 1] == "23.10.2026"



def _vat_rows(strings):
    start = strings.index("Zwischensumme")
    return strings[start:start + 6]


def test_preview_shows_the_vat_of_the_draft(artist_api):
    client, company, payload, _ = artist_api
    company.is_small_business = False
    payload["vat_rate"] = 19
    strings = pdf_strings(_preview(client, payload))
    assert _vat_rows(strings) == [
        "Zwischensumme", "300,00 €", "Umsatzsteuer 19 %", "57,00 €", "GESAMTBETRAG", "357,00 €",
    ]
    assert "Kleinunternehmer" not in " ".join(strings)


def test_stored_invoice_pdf_shows_the_same_vat(artist_api):
    client, company, payload, _ = artist_api
    company.is_small_business = False
    payload["vat_rate"] = 19
    created = client.post("/api/invoices", json=payload)
    assert created.status_code == 201, created.text
    invoice = created.json()
    assert invoice["total_brutto"] == 357
    strings = pdf_strings(client.get(f"/api/invoices/{invoice['id']}/download").content)
    assert _vat_rows(strings) == [
        "Zwischensumme", "300,00 €", "Umsatzsteuer 19 %", "57,00 €", "GESAMTBETRAG", "357,00 €",
    ]


def test_small_business_ignores_the_vat_rate_of_the_draft(artist_api):
    client, _, payload, _ = artist_api
    payload["vat_rate"] = 19
    strings = pdf_strings(_preview(client, payload))
    assert _vat_rows(strings)[2:4] == ["Umsatzsteuer", "nicht erhoben"]
    assert "GESAMTBETRAG" in strings and strings[strings.index("GESAMTBETRAG") + 1] == "300,00 €"


def test_vat_can_be_switched_off_per_invoice(artist_api):
    client, company, payload, _ = artist_api
    company.is_small_business = False
    payload["vat_rate"] = 19
    payload["ust_enabled"] = False
    strings = pdf_strings(_preview(client, payload))
    assert strings[strings.index("GESAMTBETRAG") + 1] == "300,00 €"
    assert not any(text.startswith("Umsatzsteuer 19") for text in strings)
