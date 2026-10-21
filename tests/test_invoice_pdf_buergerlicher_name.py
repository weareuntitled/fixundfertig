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


def test_pdf_leaves_artist_name_when_a_digit_precedes_it() -> None:
    """A digit immediately before the artist name keeps the longer token intact."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="Slot 2DanEP bleibt", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "Slot 2DanEP bleibt" in text


def test_pdf_matches_artist_name_case_sensitively() -> None:
    """danep is not treated as DanEP."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="danep am 19.10.", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "danep am 19.10." in text
    assert "danep (Daniel Peters)" not in text


def test_pdf_matches_artist_name_with_special_characters_literally() -> None:
    """A dot in the artist name is that character, not a pattern."""
    company = _make_company({"name": "Dan.EP"})
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DanXEP bleibt", quantity=1.0, unit_price=80.0),
            SimpleNamespace(description="Show Dan.EP!", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DanXEP bleibt" in text
    assert "Show Dan.EP (Daniel Peters)!" in text


def test_pdf_matches_artist_name_with_parentheses_literally() -> None:
    """Parentheses in the artist name are characters, not a pattern."""
    company = _make_company({"name": "Dan(EP)"})
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="Live Dan(EP).", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "Live Dan(EP) (Daniel Peters)." in text


def test_pdf_appends_legal_name_when_parentheses_lack_the_leading_space() -> None:
    """DanEP(Daniel Peters) is not the required form and gets the parenthesis too."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DanEP(Daniel Peters)", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DanEP (Daniel Peters)(Daniel Peters)" in text


def test_pdf_appends_legal_name_when_a_comma_precedes_existing_parentheses() -> None:
    """DanEP, (Daniel Peters) is not the required form and gets the parenthesis too."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DanEP, (Daniel Peters)", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DanEP (Daniel Peters), (Daniel Peters)" in text


def test_pdf_shows_identity_line_when_no_line_contains_the_artist_name() -> None:
    """DanEP (Daniel Peters) appears once between the intro and the table."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="Webdesign", quantity=1.0, unit_price=250.0),
        ],
    })
    strings = _extract_strings(render_invoice_to_pdf_bytes(invoice, company=company))
    assert strings.count("DanEP (Daniel Peters)") == 1
    assert strings.index("Vielen Dank für den Auftrag.") < strings.index("DanEP (Daniel Peters)") < strings.index("Beschreibung")


def test_pdf_shows_identity_line_when_artist_name_is_only_part_of_a_longer_word() -> None:
    """DanEPSet is not a hit, so the identity line still appears."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DanEPSet am 19.10.", quantity=1.0, unit_price=250.0),
        ],
    })
    strings = _extract_strings(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DanEPSet am 19.10." in strings
    assert strings.count("DanEP (Daniel Peters)") == 1


def test_pdf_hides_identity_line_when_a_line_contains_the_artist_name() -> None:
    """The identity line is absent once a line item names the artist."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DJ-Set DanEP, 19.10.", quantity=1.0, unit_price=250.0),
        ],
    })
    strings = _extract_strings(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DJ-Set DanEP (Daniel Peters), 19.10." in strings
    assert "DanEP (Daniel Peters)" not in strings


def test_pdf_annotates_artist_name_that_stands_alone_inside_a_longer_candidate() -> None:
    """xA.A.A holds A.A after the dot, so that hit is annotated and the identity line stays off."""
    company = _make_company({"name": "A.A"})
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="xA.A.A", quantity=1.0, unit_price=250.0),
        ],
    })
    strings = _extract_strings(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "xA.A.A (Daniel Peters)" in strings
    assert "A.A (Daniel Peters)" not in strings


def test_pdf_shows_identity_line_without_quantity_or_price_when_there_are_no_lines() -> None:
    """An empty service list still names the person once, without a fake line item."""
    company = _make_company()
    invoice = _make_invoice({"line_items": []})
    strings = _extract_strings(render_invoice_to_pdf_bytes(invoice, company=company))
    assert strings.count("DanEP (Daniel Peters)") == 1
    assert strings.index("Vielen Dank für den Auftrag.") < strings.index("DanEP (Daniel Peters)") < strings.index("Beschreibung")
    assert "1,00" not in strings
    assert strings.count("0,00 €") == 2


def test_pdf_omits_parentheses_when_no_legal_name_is_set() -> None:
    """Without first and last name the description stays free of parentheses."""
    company = _make_company({"first_name": "", "last_name": ""})
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DJ-Set DanEP, 19.10.", quantity=1.0, unit_price=250.0),
        ],
    })
    strings = _extract_strings(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DJ-Set DanEP, 19.10." in strings
    assert "()" not in "".join(strings)


def test_pdf_omits_identity_line_when_legal_name_is_blank() -> None:
    """Whitespace-only first and last name leave no identity line."""
    company = _make_company({"first_name": "   ", "last_name": "   "})
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="Webdesign", quantity=1.0, unit_price=250.0),
        ],
    })
    strings = _extract_strings(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DanEP ()" not in strings
    assert "()" not in "".join(strings)
    assert "DanEP (Daniel Peters)" not in strings


def test_pdf_uses_only_the_first_name_when_the_last_name_is_missing() -> None:
    """A stored first name alone becomes (Daniel)."""
    company = _make_company({"first_name": " Daniel ", "last_name": ""})
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DJ-Set DanEP, 19.10.", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DJ-Set DanEP (Daniel), 19.10." in text


def test_pdf_uses_only_the_last_name_when_the_first_name_is_missing() -> None:
    """A stored last name alone becomes (Peters)."""
    company = _make_company({"first_name": "", "last_name": " Peters "})
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DJ-Set DanEP, 19.10.", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DJ-Set DanEP (Peters), 19.10." in text


def test_pdf_identity_line_uses_only_the_stored_last_name() -> None:
    """The identity line uses the same trimmed legal name as the description."""
    company = _make_company({"first_name": "", "last_name": " Peters "})
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="Webdesign", quantity=1.0, unit_price=250.0),
        ],
    })
    strings = _extract_strings(render_invoice_to_pdf_bytes(invoice, company=company))
    assert strings.count("DanEP (Peters)") == 1


def test_pdf_trims_the_artist_name_before_matching() -> None:
    """Surrounding spaces on the company name do not change the printed stage name."""
    company = _make_company({"name": "  DanEP  "})
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DJ-Set DanEP, 19.10.", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DJ-Set DanEP (Daniel Peters), 19.10." in text


def test_pdf_keeps_typed_quantity_and_unit_price() -> None:
    """Naming the person does not change the typed quantity or unit price."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DJ-Set DanEP, 19.10.", quantity=3.0, unit_price=180.50),
        ],
    })
    strings = _extract_strings(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DJ-Set DanEP (Daniel Peters), 19.10." in strings
    assert "3,00" in strings
    assert "180,50 €" in strings


def test_pdf_leaves_subject_and_intro_unchanged() -> None:
    """Subject and intro keep the artist name without a legal-name parenthesis."""
    company = _make_company()
    invoice = _make_invoice({
        "subject": "Auftrag DanEP",
        "intro_text": "Hallo DanEP.",
        "line_items": [
            SimpleNamespace(description="Webdesign", quantity=1.0, unit_price=250.0),
        ],
    })
    strings = _extract_strings(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "Auftrag DanEP" in strings
    assert "Hallo DanEP." in strings
    assert "Auftrag DanEP (Daniel Peters)" not in strings
    assert "Hallo DanEP (Daniel Peters)." not in strings


def test_pdf_annotates_only_lines_that_name_the_artist() -> None:
    """A line with the artist name is annotated, a line without it stays, and the identity line is absent."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DJ-Set DanEP, 19.10.", quantity=1.0, unit_price=250.0),
            SimpleNamespace(description="Webdesign", quantity=2.0, unit_price=80.0),
        ],
    })
    strings = _extract_strings(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DJ-Set DanEP (Daniel Peters), 19.10." in strings
    assert "Webdesign" in strings
    assert "DanEP (Daniel Peters)" not in strings


def test_pdf_prints_the_same_description_when_rendered_twice() -> None:
    """A second render does not add a second pair of parentheses."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DJ-Set DanEP, 19.10.", quantity=1.0, unit_price=250.0),
        ],
    })
    first = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    second = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert first == second
    assert "DJ-Set DanEP (Daniel Peters), 19.10." in second
    assert "DanEP (Daniel Peters) (Daniel Peters)" not in second


def test_pdf_shows_the_stored_account_holder() -> None:
    """Kontoinhaber: prints the name stored in the bank field."""
    company = _make_company({"account_holder": "Virginie Konto"})
    invoice = _make_invoice()
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "Kontoinhaber: Virginie Konto" in text


def test_contact_footer_uses_account_holder_or_legal_name() -> None:
    invoice = _make_invoice()

    for fields, expected in [
        ({"account_holder": "Kontoinhaber Beispiel"}, "Kontoinhaber Beispiel"),
        ({"account_holder": ""}, "Daniel Peters"),
    ]:
        strings = _extract_strings(render_invoice_to_pdf_bytes(invoice, company=_make_company(fields)))
        contact_index = strings.index("Kontakt")
        assert strings[contact_index + 1] == expected


def test_pdf_omits_account_holder_when_the_field_is_empty() -> None:
    """An empty account holder does not fall back to the legal name."""
    company = _make_company({"account_holder": ""})
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="Webdesign", quantity=1.0, unit_price=250.0),
        ],
    })
    strings = _extract_strings(render_invoice_to_pdf_bytes(invoice, company=company))
    assert not any(line.startswith("Kontoinhaber") for line in strings)
    assert "Daniel Peters" in strings


def test_pdf_omits_account_holder_when_the_field_is_only_whitespace() -> None:
    """Spaces in the account holder field are an empty field."""
    company = _make_company({"account_holder": "   "})
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="Webdesign", quantity=1.0, unit_price=250.0),
        ],
    })
    strings = _extract_strings(render_invoice_to_pdf_bytes(invoice, company=company))
    assert not any(line.startswith("Kontoinhaber") for line in strings)
    assert strings.index("DanEP") < strings.index("Daniel Peters")


def test_pdf_names_a_line_that_is_only_the_artist_name_once() -> None:
    """DanEP becomes DanEP (Daniel Peters) once, without a second identity line."""
    company = _make_company()
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DanEP", quantity=1.0, unit_price=250.0),
        ],
    })
    strings = _extract_strings(render_invoice_to_pdf_bytes(invoice, company=company))
    assert strings.count("DanEP (Daniel Peters)") == 1


def test_pdf_keeps_bank_and_legal_footer_lines_when_account_holder_is_empty() -> None:
    """IBAN, tax id, and the small-business notice stay when Kontoinhaber is omitted."""
    company = _make_company({
        "account_holder": "",
        "is_small_business": True,
        "vat_id": "DE999999999",
    })
    invoice = _make_invoice()
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "Kontoinhaber" not in text
    assert "IBAN: DE89370400440532013000" in text
    assert "Kleinunternehmer" in text
    assert "DE999999999" in text
    assert "Daniel Peters" in text


def test_pdf_does_not_put_the_account_holder_in_the_description() -> None:
    """The bank name and the legal name stay on different lines."""
    company = _make_company({"account_holder": "Virginie Konto"})
    invoice = _make_invoice({
        "line_items": [
            SimpleNamespace(description="DJ-Set DanEP, 19.10.", quantity=1.0, unit_price=250.0),
        ],
    })
    text = _extract_text(render_invoice_to_pdf_bytes(invoice, company=company))
    assert "DJ-Set DanEP (Daniel Peters), 19.10." in text
    assert "Kontoinhaber: Virginie Konto" in text
    assert "DJ-Set DanEP (Virginie Konto)" not in text


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
        found.append("".join(chars).replace("\x80", "€"))
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
