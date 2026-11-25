"""Rechnungen aus einem Angebot erzeugen (#489, Abschläge #490).

Ein Angebot kann mehrere Rechnungen haben. Jede trägt `quote_id` = Angebots-ID;
`related_invoice_id` bleibt den Korrekturen vorbehalten. Eine Abschlagsrechnung
trägt zusätzlich `down_payment_index` = Index der abgerechneten Rate im Zahlungsplan.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from data import Company, DocumentType, Invoice, InvoiceStatus
from logic.invoice import document_vat_rate, finalize_invoice_logic
from services.invoice_pdf_draw import INVOICE_INTRO
from services.invoice_pdf_layout import format_date
from services.payment_plan import format_percent, parse_payment_plan


class DownPaymentConflict(Exception):
    """Die Rate wurde bereits abgerechnet und ihre Abschlagsrechnung ist nicht storniert."""


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
    _accept_quote(session, quote)
    session.commit()
    session.refresh(invoice)
    return invoice


def _accept_quote(session: Session, quote: Invoice) -> None:
    """Ein Abrechnen ist kein Bearbeiten: auch gesperrte Angebote werden Angenommen."""
    if quote.status != InvoiceStatus.ACCEPTED:
        quote.status = InvoiceStatus.ACCEPTED
        quote.revision_nr = int(quote.revision_nr or 0) + 1
        session.add(quote)


def down_payment_description(quote: Invoice, percent: float, label: str) -> str:
    """Positions- und PDF-Text: „Abschlag 50 % gemäß Angebot A-10000 – bei Auftrag“."""
    text = f"Abschlag {format_percent(percent)} gemäß Angebot {quote.nr}"
    return f"{text} – {label}" if label else text


def down_payment_intro(quote: Invoice, company: Any, percent: float, label: str) -> str:
    """Einleitung: „Abschlagsrechnung zu Angebot A-10000 über 50 % – bei Auftrag.“ + Standardtext."""
    text = f"Abschlagsrechnung zu Angebot {quote.nr} über {format_percent(percent)}"
    if label:
        text = f"{text} – {label}"
    standard = (getattr(company, "invoice_intro", "") or "").strip() or INVOICE_INTRO
    return f"{text}. {standard}"


def create_down_payment_invoice(
    session: Session, quote: Invoice, installment_index: int
) -> Invoice:
    """Abschlagsrechnung (Rechnungsentwurf) für eine Rate des Zahlungsplans anlegen."""
    if quote.document_type != DocumentType.QUOTE:
        raise ValueError("Nur Angebote lassen sich als Abschlag abrechnen")
    plan = parse_payment_plan(quote.payment_plan)
    if installment_index < 0 or installment_index >= len(plan):
        raise ValueError("Diese Rate gibt es im Zahlungsplan des Angebots nicht")
    rate = plan[installment_index]
    existing = session.exec(
        select(Invoice).where(
            Invoice.quote_id == int(quote.id),
            Invoice.down_payment_index == int(installment_index),
            Invoice.document_type == DocumentType.INVOICE,
            Invoice.status != InvoiceStatus.CANCELLED,
        )
    ).first()
    if existing is not None:
        raise DownPaymentConflict(
            f"Diese Rate ist bereits abgerechnet (Rechnung {existing.nr}). "
            "Stornieren Sie die Abschlagsrechnung, um sie erneut abzurechnen."
        )

    company = session.get(Company, int(quote.company_id))
    net = sum(float(it.quantity or 0) * float(it.unit_price or 0) for it in quote.items)
    amount = round(net * float(rate["percent"]) / 100.0, 2)
    is_small = bool(getattr(company, "is_small_business", False))
    vat_percent = 0.0 if is_small else document_vat_rate(quote)
    description = down_payment_description(quote, rate["percent"], rate["label"])
    invoice_id = finalize_invoice_logic(
        session=session,
        comp_id=int(quote.company_id),
        cust_id=int(quote.customer_id),
        title="Abschlagsrechnung",
        subject=quote.subject or "",
        date_str="",
        delivery_str=quote.delivery_date or "",
        recipient_data={
            "recipient_name": quote.recipient_name or "",
            "recipient_street": quote.recipient_street or "",
            "recipient_postal_code": quote.recipient_postal_code or "",
            "recipient_city": quote.recipient_city or "",
        },
        items=[{"description": description, "quantity": 1, "unit_price": amount, "tax_rate": vat_percent}],
        ust_enabled=vat_percent > 0,
        status=InvoiceStatus.DRAFT,
        intro_text=down_payment_intro(quote, company, rate["percent"], rate["label"]),
    )
    invoice = session.get(Invoice, invoice_id)
    assert invoice is not None
    invoice.quote_id = int(quote.id)
    invoice.down_payment_index = int(installment_index)
    session.add(invoice)
    _accept_quote(session, quote)
    session.commit()
    session.refresh(invoice)
    return invoice
