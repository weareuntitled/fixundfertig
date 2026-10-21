"""Invoice PDF names the legal person behind the artist name."""
import re
import zlib
from base64 import a85decode
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.invoice_pdf import render_invoice_to_pdf_bytes


def _make_company(fields: dict | None = None) -> SimpleNamespace:
    defaults = {
        "id": 1,
        "name": "DanEP",
        "first_name": "Daniel",
        "last_name": "Peters",
        "street": "Musterstraße 1",
        "postal_code": "12345",
        "city": "Berlin",
        "is_small_business": False,
        "email": "info@fixundfertig.de",
        "phone": "030 1234567",
        "bank_name": "Musterbank",
        "iban": "DE89370400440532013000",
        "bic": "COBADEFFXXX",
        "account_holder": "Daniel Peters",
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
        "subject": "DJ-Set",
        "intro_text": "Vielen Dank für den Auftrag.",
        "line_items": [SimpleNamespace(description="Webdesign", quantity=1.0, unit_price=1500.0)],
        "tax_rate": 0.0,
        "date": "2026-06-10",
    }
    if overrides:
        defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_pdf_appends_legal_name_after_artist_name_in_line_description() -> None:
    """DJ-Set DanEP, 19.10. becomes DJ-Set DanEP (Daniel Peters), 19.10."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DJ-Set DanEP, 19.10.", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DJ-Set DanEP (Daniel Peters), 19.10." in text


def test_pdf_leaves_existing_legal_name_parentheses_once() -> None:
    """DanEP (Daniel Peters) stays as it is."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DanEP (Daniel Peters)", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DanEP (Daniel Peters) (Daniel Peters)" not in text
    assert "DanEP (Daniel Peters)" in text


def test_pdf_leaves_longer_word_that_starts_with_artist_name() -> None:
    """A longer word that starts with the artist name stays untouched."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DanEPSet am 19.10.", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DanEPSet am 19.10." in text


def test_pdf_appends_legal_name_after_every_artist_name_in_one_line() -> None:
    """Every standalone occurrence in the same line is annotated."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DanEP und DanEP", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DanEP (Daniel Peters) und DanEP (Daniel Peters)" in text


def test_pdf_leaves_artist_name_when_a_digit_continues_the_word() -> None:
    """A digit glued to the artist name keeps the longer token intact."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="Code DanEP2 bleibt", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "Code DanEP2 bleibt" in text


def test_pdf_leaves_artist_name_inside_a_longer_preceding_word() -> None:
    """A letter immediately before the artist name means it is not its own word."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="Mix xDanEP bleibt", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "Mix xDanEP bleibt" in text


def _extract_text(pdf_bytes: bytes) -> str:
    return "\n".join(_extract_strings(pdf_bytes))


def _extract_strings(pdf_bytes: bytes) -> list[str]:
    strings: list[str] = []
    for stream in _content_streams(pdf_bytes):
        strings.extend(_pdf_literal_strings(stream))
    return strings


def _content_streams(pdf_bytes: bytes) -> list[str]:
    streams: list[str] = []
    for match in re.finditer(
        rb"/Filter\s*\[\s*/ASCII85Decode\s+/FlateDecode\s*\].*?/Length\s+(\d+).*?>>\s*\nstream\n(.*?)endstream",
        pdf_bytes,
        re.DOTALL,
    ):
        stream_data = match.group(2).rstrip(b"\r\n")
        try:
            decoded = a85decode(stream_data, adobe=True)
            streams.append(zlib.decompress(decoded).decode("latin-1", errors="replace"))
        except Exception:
            pass
    return streams


def _pdf_literal_strings(stream: str) -> list[str]:
    found: list[str] = []
    i = 0
    while i < len(stream):
        if stream[i] != "(":
            i += 1
            continue
        i += 1
        chars: list[str] = []
        while i < len(stream):
            char = stream[i]
            if char == "\\":
                chars.append(_unescape_pdf_char(stream, i))
                i += _escape_length(stream, i)
                continue
            if char == ")":
                i += 1
                break
            chars.append(char)
            i += 1
        found.append("".join(chars))
    return found


def _unescape_pdf_char(stream: str, slash: int) -> str:
    if slash + 1 >= len(stream):
        return ""
    char = stream[slash + 1]
    named = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "(": "(", ")": ")", "\\": "\\"}
    if char in named:
        return named[char]
    if char.isdigit():
        octal = char
        for offset in (2, 3):
            if slash + offset < len(stream) and stream[slash + offset].isdigit():
                octal += stream[slash + offset]
            else:
                break
        return chr(int(octal, 8))
    return char


def _escape_length(stream: str, slash: int) -> int:
    if slash + 1 >= len(stream):
        return 1
    char = stream[slash + 1]
    if not char.isdigit():
        return 2
    length = 2
    for offset in (2, 3):
        if slash + offset < len(stream) and stream[slash + offset].isdigit():
            length += 1
        else:
            break
    return length
