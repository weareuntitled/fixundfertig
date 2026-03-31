from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app"
if str(APP_PATH) not in __import__("sys").path:
    __import__("sys").path.append(str(APP_PATH))

data_module = importlib.import_module("data")
logic_module = importlib.import_module("logic")
Company = data_module.Company
Customer = data_module.Customer
Invoice = data_module.Invoice
InvoiceItem = data_module.InvoiceItem
get_session = data_module.get_session
finalize_invoice_logic = logic_module.finalize_invoice_logic


def _setup_company_and_customer(*, is_small_business: bool = False):
    with get_session() as session:
        comp = Company(
            name="Test GmbH",
            is_small_business=is_small_business,
            next_invoice_nr=100,
        )
        session.add(comp)
        session.commit()
        session.refresh(comp)

        cust = Customer(
            company_id=int(comp.id),
            kdnr=1,
            name="ACME Corp",
            vorname="",
            nachname="",
            email="kunde@example.com",
            strasse="Musterstraße 1",
            plz="12345",
            ort="Musterstadt",
            recipient_name="ACME Corp Rechnung",
            recipient_street="Rechnungsstraße 9",
            recipient_postal_code="54321",
            recipient_city="Rechnungsstadt",
        )
        session.add(cust)
        session.commit()
        session.refresh(cust)

        return int(comp.id), int(cust.id)


def test_finalize_invoice_with_minimal_valid_data():
    comp_id, cust_id = _setup_company_and_customer()
    items = [
        {"description": "Leistung A", "quantity": 2, "unit_price": 50.0, "tax_rate": 19},
    ]

    with get_session() as session:
        invoice_id = finalize_invoice_logic(
            session=session,
            comp_id=comp_id,
            cust_id=cust_id,
            title="Testrechnung",
            date_str="2024-01-10",
            delivery_str="2024-01-10",
            recipient_data={},
            items=items,
            ust_enabled=True,
            intro_text="Danke für den Auftrag.",
            service_from=None,
            service_to=None,
        )

        inv = session.get(Invoice, int(invoice_id))
        assert inv is not None
        assert inv.status.name == "OPEN"
        assert inv.title == "Testrechnung"
        assert inv.nr is not None and inv.nr != ""
        assert inv.date == "2024-01-10"
        assert inv.delivery_date == "2024-01-10"
        assert inv.total_brutto > 0
        assert inv.pdf_bytes is not None

        from sqlmodel import select

        items_db = list(
            session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == int(invoice_id))).all()
        )
        assert len(items_db) == 1
        assert items_db[0].description == "Leistung A"


def test_finalize_invoice_recipient_fallbacks_from_customer():
    comp_id, cust_id = _setup_company_and_customer()
    items = [
        {"description": "Leistung B", "quantity": 1, "unit_price": 100.0, "tax_rate": 19},
    ]

    with get_session() as session:
        invoice_id = finalize_invoice_logic(
            session=session,
            comp_id=comp_id,
            cust_id=cust_id,
            title="",
            date_str="2024-02-01",
            delivery_str="",
            recipient_data={},
            items=items,
            ust_enabled=False,
            intro_text="",
            service_from="2024-02-01",
            service_to="2024-02-10",
        )

        inv = session.get(Invoice, int(invoice_id))
        assert inv is not None

        # Fallback nutzt display_name/name des Kunden, nicht zwingend recipient_name
        assert inv.recipient_name == "ACME Corp"
        assert inv.recipient_street == "Rechnungsstraße 9"
        assert inv.recipient_postal_code == "54321"
        assert inv.recipient_city == "Rechnungsstadt"

        assert inv.title == "Rechnung"
        assert inv.delivery_date == "2024-02-01 bis 2024-02-10"


def test_finalize_invoice_ignores_items_without_description():
    comp_id, cust_id = _setup_company_and_customer()
    items = [
        {"description": "  ", "quantity": 1, "unit_price": 10.0, "tax_rate": 19},
        {"description": "Gültige Position", "quantity": 2, "unit_price": 20.0, "tax_rate": 19},
    ]

    with get_session() as session:
        invoice_id = finalize_invoice_logic(
            session=session,
            comp_id=comp_id,
            cust_id=cust_id,
            title="Rechnung mit Filter",
            date_str="2024-03-01",
            delivery_str="2024-03-01",
            recipient_data={},
            items=items,
            ust_enabled=True,
            intro_text="",
            service_from=None,
            service_to=None,
        )

        inv = session.get(Invoice, int(invoice_id))
        assert inv is not None

        from sqlmodel import select

        items_db = list(
            session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == int(invoice_id))).all()
        )
        assert len(items_db) == 1
        assert items_db[0].description == "Gültige Position"


def test_finalize_invoice_gross_with_ust_enabled():
    comp_id, cust_id = _setup_company_and_customer(is_small_business=False)
    items = [
        {"description": "Leistung", "quantity": 1, "unit_price": 100.0, "tax_rate": 19},
    ]
    with get_session() as session:
        invoice_id = finalize_invoice_logic(
            session=session,
            comp_id=comp_id,
            cust_id=cust_id,
            title="USt an",
            date_str="2024-04-01",
            delivery_str="2024-04-01",
            recipient_data={},
            items=items,
            ust_enabled=True,
            intro_text="",
            service_from=None,
            service_to=None,
        )
        inv = session.get(Invoice, int(invoice_id))
        assert inv is not None
        assert abs(float(inv.total_brutto) - 119.0) < 1e-6


def test_finalize_invoice_gross_with_ust_disabled():
    comp_id, cust_id = _setup_company_and_customer(is_small_business=False)
    items = [
        {"description": "Leistung", "quantity": 1, "unit_price": 100.0, "tax_rate": 19},
    ]
    with get_session() as session:
        invoice_id = finalize_invoice_logic(
            session=session,
            comp_id=comp_id,
            cust_id=cust_id,
            title="USt aus",
            date_str="2024-04-02",
            delivery_str="2024-04-02",
            recipient_data={},
            items=items,
            ust_enabled=False,
            intro_text="",
            service_from=None,
            service_to=None,
        )
        inv = session.get(Invoice, int(invoice_id))
        assert inv is not None
        assert abs(float(inv.total_brutto) - 100.0) < 1e-6


def test_finalize_invoice_small_business_ignores_ust_even_if_enabled():
    comp_id, cust_id = _setup_company_and_customer(is_small_business=True)
    items = [
        {"description": "Leistung", "quantity": 1, "unit_price": 100.0, "tax_rate": 19},
    ]
    with get_session() as session:
        invoice_id = finalize_invoice_logic(
            session=session,
            comp_id=comp_id,
            cust_id=cust_id,
            title="Kleinunternehmer",
            date_str="2024-04-03",
            delivery_str="2024-04-03",
            recipient_data={},
            items=items,
            ust_enabled=True,
            intro_text="",
            service_from=None,
            service_to=None,
        )
        inv = session.get(Invoice, int(invoice_id))
        assert inv is not None
        assert abs(float(inv.total_brutto) - 100.0) < 1e-6

