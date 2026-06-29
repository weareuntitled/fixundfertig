"""TDD: Invoice-Model braucht customer + company Relationships + company_id Field.

Hintergrund: Beim PDF-Re-Render (`_resolve_invoice_pdf_bytes` in `app/api/invoices.py`)
muss der Renderer Zugriff auf Company (für Bankdaten, Absender) und Customer (für
Empfänger) haben. Aktuell hat das Invoice-Model KEINE `company` oder `customer`
Relationship, sondern nur `customer_id: int` als FK. Resultat: PDF zeigt keine
Firmendaten, keine Bankverbindung, keine Steuernummer.
"""
from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app"
if str(APP_PATH) not in __import__("sys").path:
    __import__("sys").path.append(str(APP_PATH))

data_module = importlib.import_module("data")
Invoice = data_module.Invoice
Customer = data_module.Customer
Company = data_module.Company


def test_invoice_has_company_id_field() -> None:
    """Invoice braucht `company_id` als Field (FK auf company.id) — sonst
    kann der PDF-Re-Render die Company nicht laden."""
    annotations = Invoice.__annotations__
    assert "company_id" in annotations, f"Invoice hat kein company_id. Felder: {list(annotations.keys())}"


def test_invoice_has_customer_relationship() -> None:
    """Invoice braucht eine `customer` Relationship damit PDF-Re-Render
    `invoice.customer.recipient_name` etc. lesen kann."""
    inv = Invoice.__new__(Invoice)
    # After model change, this attribute should exist
    has_attr = hasattr(Invoice, "customer") or "customer" in Invoice.__annotations__
    # Also check via model field
    mapper_attrs = dir(Invoice)
    # The relationship attribute must be defined
    assert "customer" in Invoice.__annotations__ or any(
        a == "customer" for a in mapper_attrs
    ), "Invoice.customer Relationship fehlt"


def test_invoice_has_company_relationship() -> None:
    """Invoice braucht eine `company` Relationship für Bankdaten etc."""
    annotations = Invoice.__annotations__
    assert "company" in annotations, f"Invoice.company fehlt. Felder: {list(annotations.keys())}"


def test_pdf_rerender_uses_relationships(monkeypatch, tmp_path) -> None:
    """Wenn _resolve_invoice_pdf_bytes eine Invoice OHNE pdf_bytes bekommt,
    soll es company + customer aus den Relationships laden, nicht None."""
    import sys
    sys.path.insert(0, str(APP_PATH))

    # IMPORTANT: importlib the top-level "invoices" module (not app.api.invoices)
    # because of the sys.path trick in app/api/__init__.py — the function
    # _resolve_invoice_pdf_bytes is defined in the top-level module.
    import importlib
    invoices_top = importlib.import_module("invoices")
    dependencies_top = importlib.import_module("dependencies")

    # Use temp DB
    from sqlalchemy.orm import sessionmaker
    from sqlmodel import Session, SQLModel, create_engine
    test_engine = create_engine(f"sqlite:///{tmp_path}/test_rel.db")
    SQLModel.metadata.create_all(test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine, class_=Session, expire_on_commit=False)

    with TestSessionLocal() as s:
        comp = Company(name="Musterfirma", iban="DE89370400440532013000", bic="COBADEFFXXX", bank_name="Commerzbank")
        s.add(comp)
        s.commit()
        s.refresh(comp)

        cust = Customer(
            company_id=int(comp.id),
            kdnr=1,
            name="Kunde A",
            recipient_name="Kunde A GmbH",
            recipient_street="Kundenstr 1",
            recipient_postal_code="12345",
            recipient_city="Kundenstadt",
        )
        s.add(cust)
        s.commit()
        s.refresh(cust)

        inv = Invoice(
            customer_id=int(cust.id),
            company_id=int(comp.id),
            nr="200",
            title="Test",
            date="2026-06-10",
            total_brutto=119.0,
            pdf_bytes=None,  # lost!
            pdf_filename="",
        )
        s.add(inv)
        s.commit()
        s.refresh(inv)

        # Now test the rerender
        captured = {}

        def fake_render(invoice, **kwargs):
            captured["company"] = kwargs.get("company")
            captured["customer"] = kwargs.get("customer")
            return b"%PDF-1.4\nrendered"

        # Patch the TOP-LEVEL invoices module (where the function lives)
        monkeypatch.setattr(invoices_top, "render_invoice_to_pdf_bytes", fake_render)

        # Re-fetch from session to get relationships
        inv2 = s.get(Invoice, int(inv.id))
        bytes_ = invoices_top._resolve_invoice_pdf_bytes(inv2)
        assert bytes_ == b"%PDF-1.4\nrendered"
        # After fix: company + customer should NOT be None
        assert captured["company"] is not None, "company war None — Relationship fehlt"
        assert captured["company"].name == "Musterfirma"
        assert captured["company"].iban == "DE89370400440532013000"
        assert captured["customer"] is not None, "customer war None — Relationship fehlt"
        assert captured["customer"].name == "Kunde A"
