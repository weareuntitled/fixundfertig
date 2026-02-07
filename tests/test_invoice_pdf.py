from pathlib import Path
from types import SimpleNamespace
import sys

# Damit `services.*` (unterhalb von `app/`) importierbar ist
sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.invoice_pdf import render_invoice_to_pdf_bytes


def _make_company(long_name: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        name=long_name,
        street="Sehr lange Straßennamen mit weiteren Zusätzen 123 b",
        postal_code="12345",
        city="Beispielstadt mit sehr langem Namen",
        is_small_business=False,
        email="test@example.com",
        phone="01234/567890",
        bank_name="Testbank",
        iban="DE12345678901234567890",
        bic="TESTBIC",
        business_type="Freiberufler",
        tax_id="123/456/789",
        vat_id="DE123456789",
    )


def _make_invoice(long_recipient: str) -> SimpleNamespace:
    return SimpleNamespace(
        title="Rechnung",
        nr="2024-0001",
        recipient_name=long_recipient,
        recipient_street="Sehr lange Straße mit vielen Zusätzen und Ergänzungen 987 a",
        recipient_postal_code="98765",
        recipient_city="SehrLangeStadtbezeichnungMitZusatz",
        recipient_country="Deutschland",
        line_items=[
            SimpleNamespace(
                description=(
                    "Sehr ausführliche Leistungsbeschreibung mit vielen Details, "
                    "um den Zeilenumbruch in der Tabelle auszulösen."
                ),
                quantity=1.0,
                unit_price=100.0,
            )
        ],
        tax_rate=19.0,
        date="2024-01-01",
    )


def test_render_invoice_pdf_long_names_returns_bytes() -> None:
    long_company_name = (
        "Sehr Lange Firmenbezeichnung Mit Mehreren Bestandteilen Und "
        "Zusätzen GmbH & Co. KG, Standort Musterstadt"
    )
    long_recipient_name = (
        "Maximilian BeispielhafterEmpfängerMitSehrLangemNachnamen "
        "und weiterer Zusetzung"
    )

    company = _make_company(long_company_name)
    invoice = _make_invoice(long_recipient_name)

    pdf_bytes = render_invoice_to_pdf_bytes(invoice, company=company)

    assert isinstance(pdf_bytes, (bytes, bytearray))
    # Nicht-leere PDF-Ausgabe sicherstellen
    assert len(pdf_bytes) > 0

