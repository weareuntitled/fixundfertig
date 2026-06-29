"""Verify PDF footer content: Kontakt, Bankverbindung, Rechtliches."""
import re
import zlib
from pathlib import Path
from types import SimpleNamespace
import sys
from base64 import a85decode

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.invoice_pdf import render_invoice_to_pdf_bytes


def _make_company(fields: dict | None = None) -> SimpleNamespace:
    defaults = {
        "id": 1,
        "name": "FixundFertig GmbH",
        "street": "Musterstra\u00dfe 1",
        "postal_code": "12345",
        "city": "Berlin",
        "is_small_business": False,
        "email": "info@fixundfertig.de",
        "phone": "030 1234567",
        "bank_name": "Musterbank",
        "iban": "DE89370400440532013000",
        "bic": "COBADEFFXXX",
        "business_type": "Freiberufler",
        "tax_id": "123/456/78901",
        "vat_id": "",
    }
    if fields:
        defaults.update(fields)
    return SimpleNamespace(**defaults)


def _make_invoice(overrides: dict | None = None) -> SimpleNamespace:
    defaults = {
        "title": "Rechnung",
        "nr": "2026-0001",
        "recipient_name": "Max Mustermann",
        "recipient_street": "Hauptstraße 42",
        "recipient_postal_code": "10115",
        "recipient_city": "Berlin",
        "recipient_country": "Deutschland",
        "line_items": [SimpleNamespace(description="Webdesign", quantity=1.0, unit_price=1500.0)],
        "tax_rate": 0.0,
        "date": "2026-06-10",
    }
    if overrides:
        defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_pdf_footer_contains_kontakt() -> None:
    """Footer must include company name and email."""
    company = _make_company()
    invoice = _make_invoice()
    pdf = render_invoice_to_pdf_bytes(invoice, company=company)
    text = _extract_text(pdf)
    assert "FixundFertig" in text, f"Company name missing. Got: {text[:500]}"
    assert "info@fixundfertig.de" in text, "Email missing"


def test_pdf_footer_contains_bank() -> None:
    """Footer must include IBAN and BIC."""
    company = _make_company()
    invoice = _make_invoice()
    pdf = render_invoice_to_pdf_bytes(invoice, company=company)
    text = _extract_text(pdf)
    assert "DE89370400440532013000" in text, "IBAN missing"
    assert "COBADEFFXXX" in text, "BIC missing"


def test_pdf_footer_contains_legal() -> None:
    """Footer must include tax ID or VAT ID and business type."""
    company = _make_company({"vat_id": "DE999999999"})
    invoice = _make_invoice()
    pdf = render_invoice_to_pdf_bytes(invoice, company=company)
    text = _extract_text(pdf)
    assert "DE999999999" in text or "123/456/78901" in text, "No tax/VAT ID"
    assert "Freiberufler" in text, "Business type missing"


def test_pdf_footer_small_business_shows_notice() -> None:
    """Small business invoices show the Kleinunternehmer notice text."""
    company = _make_company({"is_small_business": True})
    invoice = _make_invoice()
    pdf = render_invoice_to_pdf_bytes(invoice, company=company)
    text = _extract_text(pdf)
    assert "Kleinunternehmer" in text, "Kleinunternehmer notice missing"
    assert "Umsatzsteuer" in text, "Kleinunternehmer notice missing"


def test_pdf_footer_section_headers_present() -> None:
    """Footer section headers: Kontakt, Bankverbindung, Rechtliches."""
    company = _make_company()
    invoice = _make_invoice()
    pdf = render_invoice_to_pdf_bytes(invoice, company=company)
    text = _extract_text(pdf)
    for header in ("Kontakt", "Bankverbindung", "Rechtliches"):
        assert header in text, f"Footer header '{header}' missing"


def _extract_text(pdf_bytes: bytes) -> str:
    """Decompress PDF content streams and return readable text."""
    text_parts: list[str] = []
    for match in re.finditer(
        rb"/Filter\s*\[\s*/ASCII85Decode\s+/FlateDecode\s*\].*?/Length\s+(\d+).*?>>\s*\nstream\n(.*?)endstream",
        pdf_bytes, re.DOTALL,
    ):
        length = int(match.group(1))
        stream_data = match.group(2).rstrip(b"\r\n")
        try:
            decoded = a85decode(stream_data, adobe=True)
            decompressed = zlib.decompress(decoded)
            text_parts.append(decompressed.decode("latin-1", errors="replace"))
        except Exception:
            pass
    return "\n".join(text_parts)
