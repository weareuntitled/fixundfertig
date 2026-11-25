"""Rechnungen aus einem Angebot erzeugen (#489, später Abschläge #490).

Ein Angebot kann mehrere Rechnungen haben. Jede trägt `quote_id` = Angebots-ID;
`related_invoice_id` bleibt den Korrekturen vorbehalten.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlmodel import Session

from data import Company, DocumentType, Invoice, InvoiceStatus
from logic.invoice import document_vat_rate, finalize_invoice_logic
from services.invoice_pdf_draw import INVOICE_INTRO
from services.invoice_pdf_layout import format_date


def quote_reference_intro(quote: Invoice, company: Any = None) -> str:
    """Einleitung einer Rechnung zum Angebot: „Gemäß Angebot A-10000 vom 23.10.2026.“ + Standardtext."""
    when = format_date(quote.date or "")
    reference = f"Gemäß Angebot {quote.nr} vom {when}." if when else f"Gemäß Angebot {quote.nr}."
    standard = (getattr(company, "invoice_intro", "") or "").strip() or INVOICE_INTRO
    return f"{reference} {standard}"


def create_invoice_from_quote(
    session: Session,
    quote: Invoice,
    *,
    items: Optional[List[Dict[str, Any]]] = None,
) -> Invoice:
    """Legt einen Rechnungsentwurf zum Angebot an und gibt ihn zurück.

    Ohne `items` werden die Positionen des Angebots übernommen. Der Steuersatz des
    Angebots (`document_vat_rate`) gilt auch für die Rechnung; Kleinunternehmer
    bekommen 0 % und damit keine Steuerzeilen.
    """
    if quote.document_type != DocumentType.QUOTE:
        raise ValueError("Nur Angebote lassen sich in Rechnungen umwandeln")
    vat_percent = document_vat_rate(quote)
    if items is None:
        items = [
            {"description": it.description, "quantity": float(it.quantity), "unit_price": float(it.unit_price)}
            for it in quote.items
        ]
    company = session.get(Company, int(quote.company_id))
    invoice_id = finalize_invoice_logic(
        session=session,
        comp_id=int(quote.company_id),
        cust_id=int(quote.customer_id),
        title="Rechnung",
        subject=quote.subject or "",
        date_str="",
        delivery_str=quote.delivery_date or "",
        recipient_data={
            "recipient_name": quote.recipient_name or "",
            "recipient_street": quote.recipient_street or "",
            "recipient_postal_code": quote.recipient_postal_code or "",
            "recipient_city": quote.recipient_city or "",
        },
        items=[it | {"tax_rate": vat_percent} for it in items],
        ust_enabled=vat_percent > 0,
        status=InvoiceStatus.DRAFT,
        intro_text=quote_reference_intro(quote, company),
    )
    invoice = session.get(Invoice, invoice_id)
    assert invoice is not None
    invoice.quote_id = int(quote.id)
    session.add(invoice)
    if quote.status != InvoiceStatus.ACCEPTED:
        # Bewusst ohne die Sperre angenommener Angebote: Umwandeln ist kein Bearbeiten.
        quote.status = InvoiceStatus.ACCEPTED
        quote.revision_nr = int(quote.revision_nr or 0) + 1
        session.add(quote)
    session.commit()
    session.refresh(invoice)
    return invoice
