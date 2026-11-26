"""PDF metadata (#500, WCAG/PDF-UA basics): viewers show the title, screen readers get the language."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import sys

from pypdf import PdfReader

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.invoice_pdf import render_invoice_to_pdf_bytes  # noqa: E402


COMPANY = SimpleNamespace(id=1, name="Studio Muster", is_small_business=False, street="Weg 1", postal_code="10115",
                          city="Berlin", email="", phone="", iban="", bic="", bank_name="", tax_id="", vat_id="")


def _doc(**extra) -> SimpleNamespace:
    base = dict(nr="A-10007", recipient_name="Spanndecken Muster GmbH", date="2026-11-26", tax_rate=19.0,
                line_items=[SimpleNamespace(description="Website", quantity=1, unit_price=1000)])
    base.update(extra)
    return SimpleNamespace(**base)


def _read(doc) -> PdfReader:
    return PdfReader(BytesIO(render_invoice_to_pdf_bytes(doc, company=COMPANY)))


def test_quote_pdf_names_itself_and_its_language() -> None:
    reader = _read(_doc(document_type="QUOTE", valid_until="2026-12-26"))
    assert reader.metadata.title == "Angebot A-10007 – Studio Muster"
    assert reader.metadata.author == "Studio Muster"
    assert reader.metadata.subject == "Angebot A-10007 an Spanndecken Muster GmbH"
    assert reader.trailer["/Root"]["/Lang"] == "de-DE"


def test_invoice_kinds_carry_their_own_title() -> None:
    assert _read(_doc(nr="10010", down_payment_index=0)).metadata.title == "Abschlagsrechnung 10010 – Studio Muster"
    assert _read(_doc(nr="10012", is_final_invoice=True)).metadata.title == "Schlussrechnung 10012 – Studio Muster"
    assert _read(_doc(nr="10013")).metadata.title == "Rechnung 10013 – Studio Muster"
