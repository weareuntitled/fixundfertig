"""Rechnungen aus einem Angebot erzeugen (#489, Abschläge #490).

Ein Angebot kann mehrere Rechnungen haben. Jede trägt `quote_id` = Angebots-ID;
`related_invoice_id` bleibt den Korrekturen vorbehalten. Eine Abschlagsrechnung
trägt zusätzlich `down_payment_index` = Index der abgerechneten Rate im Zahlungsplan.
"""
from __future__ import annotations

from datetime import date
import json
from typing import Any

from sqlmodel import Session, select

from data import Company, Customer, DocumentType, Invoice, InvoiceStatus
from logic.belegsummen_zugang import belegsummen_for_invoice
from logic.final_invoice import issued_down_payments
from logic.invoice import document_vat_rate, finalize_invoice_logic
from invoice_numbering import build_invoice_filename
from logic.quote_billing import BillingConflict, ensure_billable
from renderer import render_invoice_to_pdf_bytes
from services.invoice_pdf_draw import DOWN_PAYMENT_INTRO, INVOICE_INTRO
from services.invoice_pdf_layout import format_date
from services.payment_plan import format_percent, parse_payment_plan, round_cents


class DownPaymentConflict(BillingConflict):
    """Die Rate wurde bereits abgerechnet und ihre Abschlagsrechnung ist nicht storniert."""


def quote_reference_intro(quote: Invoice, company: Any = None) -> str:
    """Einleitung einer Rechnung zum Angebot: „Gemäß Angebot A-10000 vom 23.10.2026.“ + Standardtext."""
    when = format_date(quote.date or "")
    reference = f"Gemäß Angebot {quote.nr} vom {when}." if when else f"Gemäß Angebot {quote.nr}."
    standard = (getattr(company, "invoice_intro", "") or "").strip() or INVOICE_INTRO
    return f"{reference} {standard}"


def _quote_positions(quote: Invoice) -> list[dict[str, Any]]:
    """Die Positionen des Angebots als Rechnungspositionen."""
    return [
        {"description": it.description, "quantity": float(it.quantity), "unit_price": float(it.unit_price)}
        for it in quote.items
    ]


def _quote_recipient(quote: Invoice) -> dict[str, str]:
    """Die Empfängeranschrift des Angebots für die daraus entstehende Rechnung."""
    return {
        "recipient_name": quote.recipient_name or "",
        "recipient_street": quote.recipient_street or "",
        "recipient_postal_code": quote.recipient_postal_code or "",
        "recipient_city": quote.recipient_city or "",
    }


def _invoice_draft_from_quote(
    session: Session,
    quote: Invoice,
    *,
    title: str,
    vat_percent: float,
    intro_text: str,
    items: list[dict[str, Any]] | None = None,
) -> Invoice:
    """Rechnungsentwurf aus einem Angebot: Kopf, Empfänger und Positionen übernommen.

    Ohne eigene `items` werden die Positionen des Angebots übernommen. Das Rechnungs-
    datum ist der Tag der Erstellung (das Angebotsdatum bleibt im Angebotsbezug).
    Der Entwurf trägt `quote_id`; das Committen bleibt dem Aufrufer (er ergänzt
    Betrag und PDF).
    """
    positions = _quote_positions(quote) if items is None else items
    invoice_id = finalize_invoice_logic(
        session=session,
        comp_id=int(quote.company_id),
        cust_id=int(quote.customer_id),
        title=title,
        subject=quote.subject or "",
        date_str=date.today().isoformat(),
        delivery_str=quote.delivery_date or "",
        recipient_data=_quote_recipient(quote),
        items=[it | {"tax_rate": vat_percent} for it in positions],
        ust_enabled=vat_percent > 0,
        status=InvoiceStatus.DRAFT,
        intro_text=intro_text,
        commit=False,
    )
    invoice = session.get(Invoice, invoice_id)
    assert invoice is not None
    invoice.quote_id = int(quote.id)
    invoice.quote = quote  # the PDF names the quote ("gemäß Angebot …") before the next flush
    session.add(invoice)
    return invoice


def create_invoice_from_quote(session: Session, quote: Invoice) -> Invoice:
    """Legt einen Rechnungsentwurf zum Angebot an und gibt ihn zurück.

    Die Positionen des Angebots werden übernommen. Der Steuersatz des Angebots
    (`document_vat_rate`) gilt auch für die Rechnung; Kleinunternehmer bekommen
    0 % und damit keine Steuerzeilen.
    """
    if quote.document_type != DocumentType.QUOTE:
        raise ValueError("Nur Angebote lassen sich in Rechnungen umwandeln")
    ensure_billable(session, quote, "convert")
    vat_percent = document_vat_rate(quote)
    company = session.get(Company, int(quote.company_id))
    invoice = _invoice_draft_from_quote(
        session,
        quote,
        title="Rechnung",
        vat_percent=vat_percent,
        intro_text=quote_reference_intro(quote, company),
    )
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
    """Einleitung: „Abschlagsrechnung zu Angebot A-10000 über 50 % – bei Auftrag.“ + Abschlagstext.

    Der eigene Rechnungs-Standardtext der Firma spricht von erbrachten Leistungen und
    gilt deshalb nicht. Formulierung vom Steuerberater zu prüfen.
    """
    text = f"Abschlagsrechnung zu Angebot {quote.nr} über {format_percent(percent)}"
    if label:
        text = f"{text} – {label}"
    return f"{text}. {DOWN_PAYMENT_INTRO}"


def create_down_payment_invoice(
    session: Session, quote: Invoice, installment_index: int
) -> Invoice:
    """Abschlagsrechnung (Rechnungsentwurf) für eine Rate des Zahlungsplans anlegen."""
    if quote.document_type != DocumentType.QUOTE:
        raise ValueError("Nur Angebote lassen sich als Abschlag abrechnen")
    ensure_billable(session, quote, "down_payment")
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
    amount = round_cents(net * float(rate["percent"]) / 100.0)
    is_small = bool(getattr(company, "is_small_business", False))
    vat_percent = 0.0 if is_small else document_vat_rate(quote)
    description = down_payment_description(quote, rate["percent"], rate["label"])
    invoice = _invoice_draft_from_quote(
        session,
        quote,
        title="Abschlagsrechnung",
        vat_percent=vat_percent,
        intro_text=down_payment_intro(quote, company, rate["percent"], rate["label"]),
        items=[{"description": description, "quantity": 1, "unit_price": amount}],
    )
    invoice.down_payment_index = int(installment_index)
    customer = session.get(Customer, int(quote.customer_id))
    invoice.pdf_filename = build_invoice_filename(company, invoice, customer)
    invoice.pdf_bytes = render_invoice_to_pdf_bytes(invoice=invoice, company=company, customer=customer)
    session.add(invoice)
    _accept_quote(session, quote)
    session.commit()
    session.refresh(invoice)
    return invoice


def create_final_invoice(session: Session, quote: Invoice) -> Invoice:
    """Schlussrechnung als Rechnungsentwurf anlegen: Positionen des Angebots, Restbetrag zahlbar.

    Abgezogen werden die tatsächlich gestellten, nicht stornierten Abschlagsrechnungen
    des Angebots (Netto und Steuer getrennt). Die Positionen bleiben danach frei
    änderbar; jede Änderung verschiebt den Restbetrag.
    """
    if quote.document_type != DocumentType.QUOTE:
        raise ValueError("Nur Angebote lassen sich als Schlussrechnung abrechnen")
    ensure_billable(session, quote, "final_invoice")
    # „Gestellt" heißt: weder Entwurf noch storniert. Dieselbe Liste entscheidet
    # (in `quote_billing`), ob es die Schlussrechnung geben darf, und was abgezogen wird.
    rows = issued_down_payments(session, int(quote.id))

    company = session.get(Company, int(quote.company_id))
    is_small = bool(getattr(company, "is_small_business", False))
    vat_percent = 0.0 if is_small else document_vat_rate(quote)
    invoice = _invoice_draft_from_quote(
        session,
        quote,
        title="Schlussrechnung",
        vat_percent=vat_percent,
        intro_text=quote_reference_intro(quote, company),
    )
    invoice.is_final_invoice = True
    invoice.final_deductions_json = json.dumps([row.as_dict() for row in rows], ensure_ascii=False)
    invoice.vat_rate = vat_percent

    invoice.total_brutto = float(belegsummen_for_invoice(invoice, session).payable)

    customer = session.get(Customer, int(quote.customer_id))
    invoice.pdf_bytes = render_invoice_to_pdf_bytes(
        invoice=invoice,
        company=company,
        customer=customer,
        down_payments=[row.as_dict() for row in rows],
    )
    session.add(invoice)
    _accept_quote(session, quote)
    session.commit()
    session.refresh(invoice)
    return invoice
