"""Was der Kunde sieht: PDFs und Mails zu Angeboten und ihren Rechnungen (#496)."""
from __future__ import annotations

import importlib
import pytest
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
    quote = response.json()
    # Abrechnen geht nur aus „Gesendet“ oder „Angenommen“ (#495).
    sent = client.put(f"/api/invoices/{quote['id']}/status", json={"status": "SENT"})
    assert sent.status_code == 200, sent.text
    return quote


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


# ---- Mails


def _mail_for(client, session, monkeypatch, payload, invoice_id: int) -> dict:
    customer = session.get(invoices.Customer, payload["customer_id"])
    customer.email = "buchhaltung@club.example"
    session.add(customer)
    session.commit()
    mails: list[dict] = []
    monkeypatch.setattr(invoices, "send_email", lambda **kwargs: mails.append(kwargs) or True)
    response = client.post(f"/api/invoices/{invoice_id}/send")
    assert response.status_code == 200, response.text
    return mails[-1]


def test_down_payment_mail_names_kind_and_number(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    _standard_company(company, session)
    quote = _create_quote(client, payload, vat_rate=19)
    down_payment = _post(client, f"/api/invoices/{quote['id']}/down-payment", {"installment_index": 0})

    mail = _mail_for(client, session, monkeypatch, payload, down_payment["id"])

    assert mail["subject"] == f"Abschlagsrechnung {down_payment['nr']} — Relaunch Website"
    for body in (mail["text"], mail["html"]):
        assert f"Abschlagsrechnung {down_payment['nr']}" in body
        assert f"Rechnung {down_payment['nr']}" not in body.replace("Abschlagsrechnung", "")
        assert "2.380,00 €" in body


def test_final_invoice_mail_shows_total_deductions_and_rest(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    _quote, down_payment, final = _final_invoice_with_one_down_payment(client, company, payload, session)

    mail = _mail_for(client, session, monkeypatch, payload, final["id"])

    assert mail["subject"] == f"Schlussrechnung {final['nr']} — Relaunch Website"
    text = mail["text"]
    total = text.index("Gesamtleistung: 4.760,00 €")
    deduction = text.index(f"abzüglich Abschlagsrechnung {down_payment['nr']} vom {TODAY}: 2.380,00 €")
    rest = text.index("Restbetrag: 2.380,00 €")
    assert total < deduction < rest
    html = mail["html"]
    assert "Gesamtleistung" in html
    assert f"abzüglich Abschlagsrechnung {down_payment['nr']} vom {TODAY}" in html
    assert "Restbetrag" in html
    assert "4.760,00 €" in html


def test_customer_mails_address_the_customer_formally(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    _quote, _down_payment, final = _final_invoice_with_one_down_payment(client, company, payload, session)
    quote_mail = _mail_for(client, session, monkeypatch, payload, _quote["id"])
    final_mail = _mail_for(client, session, monkeypatch, payload, final["id"])

    for mail in (quote_mail, final_mail):
        for body in (mail["text"], mail["html"]):
            assert "Ihre" in body
            assert "danke für" not in body
            assert "Das macht" not in body
            for informal in (" du ", " dein", " dir ", " dich "):
                assert informal not in body.lower()


# ---- Rechnungsseite


def test_final_invoice_read_carries_total_deductions_and_rest(artist_api):
    client, company, payload, session = artist_api
    _quote, down_payment, final = _final_invoice_with_one_down_payment(client, company, payload, session)

    totals = client.get(f"/api/invoices/{final['id']}").json()["totals"]

    assert totals == {
        "net": 4000.0, "vat_rate": 19.0, "tax": 760.0, "gross": 4760.0,
        "deductions": [{
            "id": down_payment["id"], "nr": down_payment["nr"], "date": date.today().isoformat(),
            "net": 2000.0, "tax": 380.0, "gross": 2380.0,
        }],
        "rest_net": 2000.0, "rest_tax": 380.0, "payable": 2380.0,
    }


def test_other_documents_have_no_deductions(artist_api):
    client, _company, payload, _session = artist_api
    created = _post(client, "/api/invoices", payload)

    assert client.get(f"/api/invoices/{created['id']}").json()["totals"]["deductions"] == []


def test_final_invoice_keeps_original_deductions_after_cancellation(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    _quote, down_payment, final = _final_invoice_with_one_down_payment(client, company, payload, session)
    before = client.get(f"/api/invoices/{final['id']}").json()
    result = client.put(f"/api/invoices/{down_payment['id']}/status", json={"status": "CANCELLED"})
    assert result.status_code == 200, result.text
    session.expire_all()
    after = client.get(f"/api/invoices/{final['id']}").json()
    assert after["total_brutto"] == 2380.0
    assert after["totals"] == before["totals"]
    assert client.post(f"/api/invoices/{final['id']}/regenerate-pdf").status_code == 200
    text = _flat(_pdf(client, final["id"]))
    assert f"abzüglich Abschlagsrechnung {down_payment['nr']}" in text
    assert "2.380,00" in text
    mail = _mail_for(client, session, monkeypatch, payload, final["id"])
    assert f"abzüglich Abschlagsrechnung {down_payment['nr']}" in mail["text"]
    assert "Restbetrag: 2.380,00 €" in mail["text"]


def test_detached_final_email_uses_snapshot_and_rejects_unknown_history(artist_api):
    from services.invoice_email import build_invoice_email

    client, company, payload, session = artist_api
    _quote, down_payment, final = _final_invoice_with_one_down_payment(client, company, payload, session)
    invoice = session.get(invoices.Invoice, final["id"])
    customer = session.get(invoices.Customer, payload["customer_id"])
    # Public renderer must work without a caller looking up today's linked invoices.
    list(invoice.items)
    session.expunge(invoice)
    mail = build_invoice_email(company=company, customer=customer, invoice=invoice)
    assert f"abzüglich Abschlagsrechnung {down_payment['nr']}" in mail.text
    assert "Restbetrag: 2.380,00 €" in mail.text
    invoice.final_deductions_json = None
    with pytest.raises(ValueError, match="prüfen"):
        build_invoice_email(company=company, customer=customer, invoice=invoice)


def test_final_header_edit_keeps_saved_tax_and_deductions_after_company_change(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    _quote, down, final = _final_invoice_with_one_down_payment(client, company, payload, session)
    company.is_small_business = True
    session.add(company)
    session.commit()
    assert client.put(f"/api/invoices/{down['id']}/status", json={"status": "CANCELLED"}).status_code == 200
    updated = client.put(f"/api/invoices/{final['id']}", json={"subject": "Relaunch"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["totals"]["payable"] == 2380
    text = _flat(_pdf(client, final["id"]))
    assert "4.760,00" in text
    assert "2.380,00" in text
    mail = _mail_for(client, session, monkeypatch, payload, final["id"])
    assert "Gesamtleistung: 4.760,00 €" in mail["text"]
    assert "Kleinunternehmer" not in mail["text"]


def test_public_renderers_read_the_snapshot_without_caller_help(artist_api):
    from renderer import render_invoice_to_pdf_bytes
    from services.invoice_email import build_invoice_email

    client, company, payload, session = artist_api
    _quote, down, final = _final_invoice_with_one_down_payment(client, company, payload, session)
    invoice = session.get(invoices.Invoice, final["id"])
    customer = session.get(invoices.Customer, payload["customer_id"])
    document = invoice.model_dump() | {"items": [item.model_dump() for item in invoice.items]}
    text = _flat(render_invoice_to_pdf_bytes(document, company=company, customer=customer))
    assert f"abzüglich Abschlagsrechnung {down['nr']}" in text
    assert "2.380,00" in text
    mail = build_invoice_email(invoice=document, company=company, customer=customer)
    assert f"abzüglich Abschlagsrechnung {down['nr']}" in mail.text
    document["final_deductions_json"] = None
    with pytest.raises(ValueError, match="prüfen"):
        render_invoice_to_pdf_bytes(document, company=company)
    with pytest.raises(ValueError, match="prüfen"):
        build_invoice_email(invoice=document, company=company, customer=customer)


def test_historical_final_download_keeps_file_backed_pdf(artist_api, tmp_path):
    client, company, payload, session = artist_api
    _quote, _down_payment, final = _final_invoice_with_one_down_payment(client, company, payload, session)
    stored = _pdf(client, final["id"])
    path = tmp_path / "historical-final.pdf"
    path.write_bytes(stored)
    invoice = session.get(invoices.Invoice, final["id"])
    invoice.pdf_bytes = None
    invoice.pdf_filename = str(path)
    invoice.final_deductions_json = None
    session.add(invoice)
    session.commit()
    assert _pdf(client, final["id"]) == stored
    assert client.get(f"/api/invoices/{final['id']}/preview-pdf").content == stored
    assert path.read_bytes() == stored


def test_legacy_pdf_api_preserves_saved_final_and_blocks_unknown_history(artist_api, monkeypatch, tmp_path):
    from contextlib import contextmanager
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import viewer

    client, company, payload, session = artist_api
    _quote, _down_payment, final = _final_invoice_with_one_down_payment(client, company, payload, session)
    stored = _pdf(client, final["id"])
    invoice = session.get(invoices.Invoice, final["id"])
    invoice.final_deductions_json = None
    company.user_id = 1
    session.add(invoice)
    session.add(company)
    session.commit()

    @contextmanager
    def get_session():
        yield session

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(viewer, "get_session", get_session)
    monkeypatch.setattr(viewer, "require_auth", lambda: True)
    monkeypatch.setattr(viewer, "get_current_user_id", lambda _session: 1)
    viewer._invoice_pdf_cache.clear()
    app = FastAPI()
    app.add_api_route("/api/invoices/{invoice_id}/pdf", viewer.invoice_pdf)
    with TestClient(app) as legacy:
        assert legacy.get(f"/api/invoices/{final['id']}/pdf").content == stored
        assert not (tmp_path / "storage").exists()
        invoice.pdf_bytes = None
        session.add(invoice)
        session.commit()
        viewer._invoice_pdf_cache.clear()
        blocked = legacy.get(f"/api/invoices/{final['id']}/pdf")
        assert blocked.status_code == 409, blocked.text
        assert "prüfen" in blocked.json()["detail"]
        assert not (tmp_path / "storage").exists()


def test_final_pdf_export_never_falls_back_to_an_ordinary_invoice(artist_api):
    from logic.exports import export_invoices_pdf_zip
    from zipfile import ZipFile

    client, company, payload, session = artist_api
    _quote, down_payment, final = _final_invoice_with_one_down_payment(client, company, payload, session)
    invoice = session.get(invoices.Invoice, final["id"])
    snapshot = invoice.final_deductions_json
    stored = _pdf(client, final["id"])
    invoice.final_deductions_json = None
    session.add(invoice)
    session.commit()
    archive = export_invoices_pdf_zip(session, company.id, [final["id"]])
    with ZipFile(BytesIO(archive)) as files:
        assert files.read(files.namelist()[0]) == stored
    invoice.pdf_bytes = None
    session.add(invoice)
    session.commit()
    with pytest.raises(ValueError, match="prüfen"):
        export_invoices_pdf_zip(session, company.id, [final["id"]])
    invoice.final_deductions_json = snapshot
    session.add(invoice)
    session.commit()
    archive = export_invoices_pdf_zip(session, company.id, [final["id"]])
    with ZipFile(BytesIO(archive)) as files:
        text = _flat(files.read(files.namelist()[0]))
        assert f"abzüglich Abschlagsrechnung {down_payment['nr']}" in text
        assert "2.380,00" in text


def test_historical_final_invoice_preserves_pdf_and_blocks_changes(artist_api, monkeypatch):
    client, company, payload, session = artist_api
    _quote, down_payment, final = _final_invoice_with_one_down_payment(client, company, payload, session)
    stored = _pdf(client, final["id"])
    invoice = session.get(invoices.Invoice, final["id"])
    invoice.final_deductions_json = None
    session.add(invoice)
    session.commit()
    assert client.get(f"/api/invoices/{final['id']}").json()["totals"] is None
    assert _pdf(client, final["id"]) == stored
    assert client.get(f"/api/invoices/{final['id']}/preview-pdf").content == stored
    for response in (
        client.post(f"/api/invoices/{final['id']}/regenerate-pdf"),
        client.put(f"/api/invoices/{final['id']}", json={"subject": "Changed"}),
        client.put(f"/api/invoices/{final['id']}/items/{final['items'][0]['id']}",
                   json={"description": "Website", "quantity": 1, "unit_price": 5000}),
    ):
        assert response.status_code == 409, response.text
        assert "prüfen" in response.json()["detail"]
    customer = session.get(invoices.Customer, payload["customer_id"])
    customer.email = "kunde@example.com"
    session.add(customer)
    session.commit()
    sent = []
    monkeypatch.setattr(invoices, "send_email", lambda **kwargs: sent.append(kwargs) or True)
    response = client.post(f"/api/invoices/{final['id']}/send")
    assert response.status_code == 409, response.text
    assert sent == []
    assert client.put(f"/api/invoices/{down_payment['id']}/status", json={"status": "CANCELLED"}).status_code == 200
    assert _pdf(client, final["id"]) == stored
    assert client.get(f"/api/invoices/{final['id']}").json()["total_brutto"] == 2380
    invoice = session.get(invoices.Invoice, final["id"])
    invoice.pdf_bytes = None
    session.add(invoice)
    session.commit()
    assert client.get(f"/api/invoices/{final['id']}/download").status_code == 409


@pytest.mark.parametrize("mutation", ["header", "add", "edit", "remove", "cancel", "bulk_cancel", "delete"])
@pytest.mark.parametrize("historical", [False, True])
def test_linked_mutations_preserve_final_history_after_reload(artist_api, mutation, historical):
    client, company, payload, session = artist_api
    _quote, down, final = _final_invoice_with_one_down_payment(client, company, payload, session)
    invoice = session.get(invoices.Invoice, final["id"])
    if historical:
        invoice.final_deductions_json = None
        session.add(invoice)
        session.commit()
    before = client.get(f"/api/invoices/{final['id']}").json()
    stored = _pdf(client, final["id"])
    base = f"/api/invoices/{down['id']}"
    item = {"description": "Geändert", "quantity": 1, "unit_price": 1000}
    if mutation == "header":
        response = client.put(base, json={"date": "2026-01-01", "subject": "Geändert"})
    elif mutation == "add":
        response = client.post(base + "/items", json=item)
    elif mutation == "edit":
        response = client.put(base + f"/items/{down['items'][0]['id']}", json=item)
    elif mutation == "remove":
        response = client.delete(base + f"/items/{down['items'][0]['id']}")
    elif mutation == "cancel":
        response = client.put(base + "/status", json={"status": "CANCELLED"})
    elif mutation == "bulk_cancel":
        response = client.post("/api/invoices/bulk-status", json={"invoice_ids": [down["id"]], "status": "CANCELLED"})
    else:
        response = client.delete(base)
    assert response.status_code in (200, 201), response.text
    session.expunge_all()
    after = client.get(f"/api/invoices/{final['id']}").json()
    assert after["total_brutto"] == 2380
    assert after["totals"] == before["totals"]
    assert after["revision_nr"] == before["revision_nr"]
    assert _pdf(client, final["id"]) == stored
    invoice = session.get(invoices.Invoice, final["id"])
    list(invoice.items)
    session.expunge(invoice)
    if historical:
        with pytest.raises(ValueError, match="prüfen"):
            invoices.recompute_total_brutto(invoice, 19)
    else:
        invoices.recompute_total_brutto(invoice, 19)
        assert invoice.total_brutto == 2380
        assert before["totals"]["deductions"][0]["nr"] == down["nr"]


@pytest.mark.parametrize("snapshot", [None, "broken", "{}", "null", '[{"id":1}]',
    '[{"id":1,"nr":"10000","date":"2026-01-01","net":2000,"tax":380,"total":NaN}]',
    '[{"id":1,"nr":"10000","date":"2026-01-01","net":2000,"tax":380,"total":2000}]',
    '[{"id":1,"nr":"10000","net":2000,"tax":380,"total":2380}]',
])
def test_unreliable_snapshot_blocks_every_write_without_touching_saved_pdf(artist_api, snapshot, monkeypatch):
    client, company, payload, session = artist_api
    _quote, _down, final = _final_invoice_with_one_down_payment(client, company, payload, session)
    invoice = session.get(invoices.Invoice, final["id"])
    invoice.final_deductions_json = snapshot
    customer = session.get(invoices.Customer, payload["customer_id"])
    customer.email = "kunde@example.com"
    session.add(invoice)
    session.add(customer)
    session.commit()
    stored = _pdf(client, final["id"])
    before = client.get(f"/api/invoices/{final['id']}").json()
    sent = []
    monkeypatch.setattr(invoices, "send_email", lambda **kwargs: sent.append(kwargs) or True)
    base = f"/api/invoices/{final['id']}"
    for method, path, body in [
        ("post", "/regenerate-pdf", None), ("post", "/send", None),
        ("put", "", {"subject": "Geändert"}),
        ("post", "/items", {"description": "Extra", "quantity": 1, "unit_price": 100}),
        ("put", f"/items/{final['items'][0]['id']}", {"description": "Extra", "quantity": 2, "unit_price": 100}),
        ("delete", f"/items/{final['items'][0]['id']}", None),
    ]:
        response = client.request(method, base + path, json=body)
        assert response.status_code == 409, response.text
        assert "prüfen" in response.json()["detail"]
    assert sent == []
    session.expire_all()
    assert client.get(base).json() == before
    assert _pdf(client, final["id"]) == stored


def test_legacy_email_uses_snapshot_and_blocks_unreviewed_history(artist_api, monkeypatch):
    from contextlib import contextmanager
    from pages import _shared as shared

    client, company, payload, session = artist_api
    _quote, down, final = _final_invoice_with_one_down_payment(client, company, payload, session)
    invoice = session.get(invoices.Invoice, final["id"])
    customer = session.get(invoices.Customer, payload["customer_id"])
    customer.email = "kunde@example.com"
    session.add(customer)
    session.commit()
    sent, notices = [], []

    @contextmanager
    def get_session():
        yield session

    monkeypatch.setattr(shared, "get_session", get_session)
    monkeypatch.setattr(shared, "send_email", lambda **kwargs: sent.append(kwargs) or True)
    monkeypatch.setattr(shared.ui, "notify", lambda message, **kwargs: notices.append(message))
    shared.send_invoice_email(company, customer, invoice)
    assert f"abzüglich Abschlagsrechnung {down['nr']}" in sent[0]["text"]
    assert "Restbetrag: 2.380,00 €" in sent[0]["text"]
    invoice.final_deductions_json = None
    shared.send_invoice_email(company, customer, invoice)
    assert len(sent) == 1
    assert "prüfen" in notices[-1]
    with pytest.raises(ValueError, match="prüfen"):
        shared.build_invoice_mailto(company, customer, invoice)


def test_final_snapshot_survives_database_reopen_and_startup(artist_api, tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlmodel import Session, SQLModel, create_engine
    import db
    import dependencies

    _client, template_company, payload, source_session = artist_api
    engine = create_engine(f"sqlite:///{tmp_path / 'snapshot.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    company = invoices.Company(**template_company.model_dump())
    company.is_small_business = False
    customer = invoices.Customer(**source_session.get(invoices.Customer, payload["customer_id"]).model_dump())
    customer.email = "kunde@example.com"
    with Session(engine) as session:
        session.add(company)
        session.add(customer)
        session.commit()

    def db_session():
        with Session(engine) as session:
            yield session

    def current_company():
        with Session(engine) as session:
            return session.get(invoices.Company, template_company.id)

    app = FastAPI()
    app.include_router(invoices.router)
    app.dependency_overrides[dependencies.db_session] = db_session
    app.dependency_overrides[dependencies.get_current_company] = current_company
    app.dependency_overrides[dependencies.require_session_auth] = lambda: 1
    sent = []
    monkeypatch.setattr(invoices, "send_email", lambda **kwargs: sent.append(kwargs) or True)
    with TestClient(app) as client:
        quote = _create_quote(client, payload, vat_rate=19)
        down = _post(client, f"/api/invoices/{quote['id']}/down-payment", {"installment_index": 0})
        _send(client, down["id"])
        final = _post(client, f"/api/invoices/{quote['id']}/final-invoice")
        stored = _pdf(client, final["id"])
        assert client.delete(f"/api/invoices/{down['id']}").status_code == 200
        engine.dispose()
        # Startup must preserve the existing snapshot, rather than backfill from today's links.
        db.ensure_invoice_quote_fields(engine)
        after = client.get(f"/api/invoices/{final['id']}").json()
        assert after["totals"] == final["totals"]
        assert after["total_brutto"] == 2380
        assert _pdf(client, final["id"]) == stored
        assert client.post(f"/api/invoices/{final['id']}/regenerate-pdf").status_code == 200
        text = _flat(_pdf(client, final["id"]))
        assert f"abzüglich Abschlagsrechnung {down['nr']}" in text
        assert "2.380,00" in text
        assert client.post(f"/api/invoices/{final['id']}/send").status_code == 200
        assert f"abzüglich Abschlagsrechnung {down['nr']}" in sent[0]["text"]
    engine.dispose()
