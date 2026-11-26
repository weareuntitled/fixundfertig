"""Was der Kunde sieht: PDFs und Mails zu Angeboten und ihren Rechnungen (#496)."""
from __future__ import annotations

import importlib
from datetime import date
from io import BytesIO

from pypdf import PdfReader
from pypdf.generic import ContentStream

from pdf_text import pdf_text
from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)

invoices = importlib.import_module("invoices")

PLAN = [
    {"percent": 50, "label": "bei Auftrag"},
    {"percent": 50, "label": "bei Abnahme"},
]
NET_4000 = [{"description": "Website", "quantity": 1, "unit_price": 4000}]
TODAY = date.today().strftime("%d.%m.%Y")


def _create_quote(client, payload: dict, **overrides) -> dict:
    body = payload | {
        "document_type": "QUOTE",
        "date": "2026-10-23",
        "subject": "Relaunch Website",
        "items": NET_4000,
        "payment_plan": PLAN,
    } | overrides
    response = client.post("/api/invoices", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _post(client, url: str, body: dict | None = None) -> dict:
    response = client.post(url, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _send(client, invoice_id: int) -> None:
    response = client.put(f"/api/invoices/{invoice_id}/status", json={"status": "SENT"})
    assert response.status_code == 200, response.text


def _standard_company(company, session) -> None:
    company.is_small_business = False
    session.add(company)
    session.commit()


def _pdf(client, invoice_id: int) -> bytes:
    response = client.get(f"/api/invoices/{invoice_id}/download")
    assert response.status_code == 200, response.text
    return response.content


def _flat(pdf_bytes: bytes) -> str:
    return " ".join(pdf_text(pdf_bytes).split())


def _final_invoice_with_one_down_payment(client, company, payload, session) -> tuple[dict, dict, dict]:
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    down_payment = _post(client, f"/api/invoices/{quote['id']}/down-payment", {"installment_index": 0})
    _send(client, down_payment["id"])
    final = _post(client, f"/api/invoices/{quote['id']}/final-invoice")
    return quote, down_payment, final


def _accent_lines(pdf_bytes: bytes) -> list[float]:
    """y of every horizontal stroke drawn with the 1.5 pt accent width on page 1."""
    page = PdfReader(BytesIO(pdf_bytes)).pages[0]
    content = ContentStream(page.get_contents(), page.pdf)
    width = 1.0
    start_y = None
    lines: list[float] = []
    for operands, operator in content.operations:
        if operator == b"w":
            width = float(operands[0])
        elif operator == b"m":
            start_y = float(operands[1])
        elif operator == b"l" and start_y is not None and abs(float(operands[1]) - start_y) < 0.01:
            if abs(width - 1.5) < 0.01:
                lines.append(start_y)
    return lines


def _text_boxes(pdf_bytes: bytes) -> list[tuple[str, float, float]]:
    """(text, baseline y, font size) of every text operation on page 1."""
    boxes: list[tuple[str, float, float]] = []

    def collect(text, cm, tm, _font, size) -> None:
        if text.strip():
            boxes.append((text.strip(), float(tm[5]) * float(cm[3]) + float(cm[5]), float(size)))

    PdfReader(BytesIO(pdf_bytes)).pages[0].extract_text(visitor_text=collect)
    return boxes


# ---- Schlussrechnung


def test_final_invoice_pdf_reads_total_then_deduction_with_date_then_rest(artist_api):
    client, company, payload, session = artist_api
    _quote, down_payment, final = _final_invoice_with_one_down_payment(client, company, payload, session)

    text = _flat(_pdf(client, final["id"]))

    deduction = f"abzüglich Abschlagsrechnung {down_payment['nr']} vom {TODAY}"
    assert deduction in text
    assert text.index("Gesamtleistung") < text.index(deduction) < text.index("Restbetrag")
    assert f"Rechnung {down_payment['nr']} " not in text.replace(deduction, "")


def test_no_accent_line_touches_the_rest_line(artist_api):
    client, company, payload, session = artist_api
    _quote, _down_payment, final = _final_invoice_with_one_down_payment(client, company, payload, session)
    pdf_bytes = _pdf(client, final["id"])

    boxes = _text_boxes(pdf_bytes)
    rest = [(y, size) for text, y, size in boxes if text.startswith("Restbetrag")]
    assert rest, boxes
    rest_y = rest[0][0]
    # The tallest glyph in the rest row is the 12 pt amount; its descenders reach ~0.25 em below.
    row_top = rest_y + 12
    row_bottom = rest_y - 3
    above = [y for _text, y, _size in boxes if y > rest_y + 1]
    previous_baseline = min(above)
    for line_y in _accent_lines(pdf_bytes):
        assert not (row_bottom <= line_y <= row_top), (line_y, rest_y)
    lines_between = [y for y in _accent_lines(pdf_bytes) if row_top < y < previous_baseline - 2]
    assert lines_between, "the rest line is set off by an accent line above it"


# ---- Abschlagsrechnung


def test_down_payment_pdf_says_the_service_is_not_yet_rendered(artist_api):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    down_payment = _post(client, f"/api/invoices/{quote['id']}/down-payment", {"installment_index": 0})

    text = _flat(_pdf(client, down_payment["id"]))

    assert "ABSCHLAGSRECHNUNG" in text
    assert "wie Rechnungsdatum" not in text
    assert "Leistungsdatum" not in text
    assert "folgende Leistungen in Rechnung" not in text
    assert "Vereinbarungsgemäß berechne ich folgende Abschlagszahlung." in text
    assert f"Leistung: noch nicht erbracht – Anzahlung gemäß Angebot {quote['nr']}" in text
    assert f"Rechnungsdatum: {TODAY}" in text


def test_down_payment_pdf_keeps_its_texts_after_an_edit(artist_api):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    down_payment = _post(client, f"/api/invoices/{quote['id']}/down-payment", {"installment_index": 0})
    response = client.put(
        f"/api/invoices/{down_payment['id']}", json={"recipient_name": "Club Beispiel GmbH", "reason": "Test"}
    )
    assert response.status_code == 200, response.text

    text = _flat(_pdf(client, down_payment["id"]))

    assert "wie Rechnungsdatum" not in text
    assert f"Leistung: noch nicht erbracht – Anzahlung gemäß Angebot {quote['nr']}" in text
    assert "Relaunch Website" in text


# ---- Umgewandelte Rechnung


def test_converted_invoice_pdf_carries_the_subject(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)
    invoice = _post(client, f"/api/invoices/{quote['id']}/convert")

    text = _flat(_pdf(client, invoice["id"]))

    assert invoice["subject"] == "Relaunch Website"
    assert "Relaunch Website" in text


def test_edited_invoice_pdf_keeps_the_subject(artist_api):
    client, _company, payload, _session = artist_api
    created = _post(client, "/api/invoices", payload | {"subject": "DJ-Set Hammahalle"})
    response = client.put(f"/api/invoices/{created['id']}", json={"recipient_name": "Club X", "reason": "Test"})
    assert response.status_code == 200, response.text

    assert "DJ-Set Hammahalle" in _flat(_pdf(client, created["id"]))


# ---- Angebot


def test_quote_pdf_names_the_offerer_not_an_invoice_issuer(artist_api):
    client, _company, payload, _session = artist_api
    quote = _create_quote(client, payload)

    text = _flat(_pdf(client, quote["id"]))

    assert "ANBIETER Daniel Beispiel" in text
    assert "RECHNUNGSAUSSTELLER" not in text


def test_invoice_pdf_still_names_the_invoice_issuer(artist_api):
    client, _company, payload, _session = artist_api
    created = _post(client, "/api/invoices", payload)

    text = _flat(_pdf(client, created["id"]))

    assert "RECHNUNGSAUSSTELLER Daniel Beispiel" in text
    assert "ANBIETER" not in text


def _identity_company():
    from types import SimpleNamespace

    return SimpleNamespace(
        id=1, name="untitled ux", first_name="Test", last_name="Inhaber",
        business_type="Agentur", street="Musterstraße 1", postal_code="10115", city="Berlin",
        is_small_business=True, email="", phone="", iban="", bank_name="", tax_id="", vat_id="",
    )


def _identity_document(document_type: str):
    from types import SimpleNamespace

    return SimpleNamespace(
        document_type=document_type, nr="A-10000", date="2026-10-23", valid_until="2026-11-22",
        recipient_name="Kunde GmbH", subject="Relaunch", intro_text="",
        line_items=[SimpleNamespace(description="Webdesign", quantity=1.0, unit_price=1000.0)],
    )


def test_quote_pdf_has_no_stray_name_line_under_the_intro():
    from services.invoice_pdf import render_invoice_to_pdf_bytes

    strings = [s.strip() for s in pdf_text(
        render_invoice_to_pdf_bytes(_identity_document("QUOTE"), company=_identity_company())
    ).split("\n")]

    assert "untitled ux (Test Inhaber)" not in strings
    assert "ANBIETER" in strings


def test_invoice_pdf_still_names_the_legal_person_above_the_services():
    from services.invoice_pdf import render_invoice_to_pdf_bytes

    strings = [s.strip() for s in pdf_text(
        render_invoice_to_pdf_bytes(_identity_document("INVOICE"), company=_identity_company())
    ).split("\n")]

    assert "untitled ux (Test Inhaber)" in strings
