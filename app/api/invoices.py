# =========================
# APP/API/INVOICES.PY
# =========================
"""
Invoice API: /api/invoices[/...]

Endpoints (Stand 2026-06-12):
- GET  /api/invoices                — Liste
- GET  /api/invoices/suggestions    — Line-Item-Vorschläge (unique description + unit_price)
- POST /api/invoices/bulk-status    — Bulk-Status-Transition (atomar)
- GET  /api/invoices/{id}           — Detail
- PUT  /api/invoices/{id}/status    — Status-Transition
- POST /api/invoices/{id}/duplicate — Duplicate (DRAFT, gleiche Items + Kunde)
- POST /api/invoices/{id}/payment-link — Stripe-Zahlungslink erzeugen
- POST /api/invoices/{id}/check-payment — Stripe-Zahlungsstatus prüfen
- POST /api/invoices/preview-pdf    — PDF-Bytes (Live-Preview, kein State)

Später (M5): POST /api/invoices (create + finalize), POST /api/invoices/{id}/correction.
"""

from __future__ import annotations

import logging
import os
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import object_session, selectinload
from sqlmodel import Session, select

from data import Company, Customer, Document, Invoice, InvoiceItem as InvoiceItemModel
from data import DocumentType, InvoiceAttachment, InvoiceRevision, InvoiceStatus
from actions import delete_invoice
from dependencies import db_session, get_current_company, require_session_auth
from invoice_numbering import build_invoice_filename
from logic import document_vat_rate, finalize_invoice_logic, recompute_total_brutto
from logic.document_status import (
    accepted_quote_status_reason,
    creation_status_reason,
    is_accepted_quote,
    is_rejected_quote,
    status_not_allowed_reason,
)
from logic.final_invoice import issued_down_payments
from logic.quote_billing import BillingConflict, quote_billing
from logic.quote_conversion import (
    create_down_payment_invoice,
    create_final_invoice,
    create_invoice_from_quote,
)
from logic.quote_decision import (
    decision_reset_reason,
    extended_valid_until,
    mark_sent_reason,
    quote_has_invoices,
    validity_extension_reason,
)
from renderer import render_invoice_to_pdf_bytes
from schemas.invoice import (
    BulkStatusUpdate,
    DownPaymentRequest,
    InvoiceAttachmentCreate,
    InvoiceAttachmentRead,
    InvoiceDraft,
    InvoiceItem,
    InvoiceRead,
    LinkedInvoiceRead,
    QuoteBillingRead,
    InvoiceSendRequest,
    InvoiceStatusUpdate,
    InvoiceUpdate,
    PaymentInstallmentRead,
)
from services.documents import build_download_filename, read_document_bytes
from services.email import send_email
from services.payment_plan import dump_payment_plan, installments_with_amounts, parse_payment_plan
from services.invoice_email import build_invoice_email
from services.payment import check_payment, create_payment_link

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/invoices", tags=["invoices"])


@router.post("/{invoice_id}/duplicate", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def duplicate_invoice(
    invoice_id: int,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Duplicate an existing document as a new DRAFT with the same customer and items.

    A quote stays a quote: it gets its own quote number, validity and payment plan.
    """
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    is_quote = getattr(invoice, "document_type", None) == DocumentType.QUOTE
    items = [
        {
            "description": it.description,
            "quantity": float(it.quantity),
            "unit_price": float(it.unit_price),
        }
        for it in (getattr(invoice, "items", None) or [])
    ]

    ust_enabled = True
    quote_options: dict = {}
    if is_quote:
        vat_percent = document_vat_rate(invoice)
        items = [item | {"tax_rate": vat_percent} for item in items]
        ust_enabled = vat_percent > 0
        quote_options = {
            "document_type": DocumentType.QUOTE,
            "valid_until": getattr(invoice, "valid_until", "") or "",
            "payment_plan": parse_payment_plan(getattr(invoice, "payment_plan", None)),
        }

    try:
        inv_id = finalize_invoice_logic(
            session=session,
            comp_id=int(company.id),
            cust_id=int(invoice.customer_id),
            title=invoice.title or ("Angebot" if is_quote else "Rechnung"),
            subject=invoice.subject or "",
            date_str="",
            delivery_str="",
            recipient_data={
                "recipient_name": invoice.recipient_name or "",
                "recipient_street": invoice.recipient_street or "",
                "recipient_postal_code": invoice.recipient_postal_code or "",
                "recipient_city": invoice.recipient_city or "",
            },
            items=items,
            ust_enabled=ust_enabled,
            status=InvoiceStatus.DRAFT,
            **quote_options,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    session.commit()

    new_invoice = session.get(Invoice, inv_id)
    if not new_invoice:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invoice not found after duplicate")
    return _to_read_model(new_invoice)


@router.post("/{invoice_id}/convert", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def convert_quote_to_invoice(
    invoice_id: int,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Angebot in Rechnung umwandeln: neuer Rechnungsentwurf mit den Positionen des Angebots."""
    quote = _get_invoice_for_company(session, invoice_id, company)
    try:
        invoice = create_invoice_from_quote(session, quote)
    except BillingConflict as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return _to_read_model(invoice)


@router.post("/{invoice_id}/down-payment", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def create_quote_down_payment(
    invoice_id: int,
    payload: DownPaymentRequest,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Abschlagsrechnung aus einer Rate des Zahlungsplans eines Angebots."""
    quote = _get_invoice_for_company(session, invoice_id, company)
    try:
        invoice = create_down_payment_invoice(session, quote, payload.installment_index)
    except BillingConflict as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return _to_read_model(invoice)


@router.post("/{invoice_id}/final-invoice", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def create_quote_final_invoice(
    invoice_id: int,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Schlussrechnung zum Angebot: Positionen übernehmen, gestellte Abschläge abziehen (#491)."""
    quote = _get_invoice_for_company(session, invoice_id, company)
    try:
        invoice = create_final_invoice(session, quote)
    except BillingConflict as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return _to_read_model(invoice)


@router.post("/{invoice_id}/mark-sent", response_model=InvoiceRead)
def mark_quote_as_sent(
    invoice_id: int,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Angebot ohne Mailserver auf „Gesendet“ setzen (#497).

    Wer das PDF selbst verschickt, markiert das Angebot so als gesendet. Aus einer
    Entscheidung („Angenommen“, „Abgelehnt“) geht das nur zurück, solange das Angebot
    keine Rechnung hat; mit Rechnung bleibt die Entscheidung endgültig (409).
    """
    quote = _get_invoice_for_company(session, invoice_id, company)
    if getattr(quote, "document_type", None) != DocumentType.QUOTE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nur Angebote können als gesendet markiert werden",
        )
    reason = mark_sent_reason(quote, quote_has_invoices(session, quote))
    if reason:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)
    quote.status = InvoiceStatus.SENT
    quote.revision_nr = int(quote.revision_nr or 0) + 1
    session.add(quote)
    session.commit()
    session.refresh(quote)
    return _to_read_model(quote)


@router.post("/{invoice_id}/extend-validity", response_model=InvoiceRead)
def extend_quote_validity(
    invoice_id: int,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """„Gültigkeit verlängern“: „gültig bis“ = heute + 30 Tage (#497)."""
    quote = _get_invoice_for_company(session, invoice_id, company)
    if getattr(quote, "document_type", None) != DocumentType.QUOTE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nur Angebote haben eine Gültigkeit",
        )
    reason = validity_extension_reason(quote)
    if reason:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)
    quote.valid_until = extended_valid_until()
    quote.revision_nr = int(quote.revision_nr or 0) + 1
    session.add(quote)
    session.commit()
    session.refresh(quote)
    _rerender_quote_pdf(session, quote)
    return _to_read_model(quote)


def _attachment_to_read(attachment: InvoiceAttachment) -> InvoiceAttachmentRead:
    document = attachment.document
    return InvoiceAttachmentRead(
        id=int(attachment.id),
        document_id=int(attachment.document_id),
        title=(document.title or "").strip(),
        filename=(document.original_filename or document.filename or "").strip(),
        mime=(document.mime or document.mime_type or "").strip(),
        size=int(document.size_bytes or document.size or 0),
        created_at=attachment.created_at.isoformat(),
    )


def _document_type_value(invoice: Invoice) -> str:
    doc_type = getattr(invoice, "document_type", None) or DocumentType.INVOICE
    return doc_type.value if hasattr(doc_type, "value") else str(doc_type)


def _down_payment_rows(session: Session, quote_id: int) -> list[dict]:
    """Billed down payments of a quote in the shape the PDF renderer expects."""
    return [row.as_dict() for row in issued_down_payments(session, int(quote_id))]


def _final_invoice_down_payments(session: Session | None, invoice) -> list[dict] | None:
    """Die Abschlagsrechnungen, die eine Schlussrechnung abzieht; None für andere Dokumente."""
    if session is None or not getattr(invoice, "is_final_invoice", False):
        return None
    quote_id = getattr(invoice, "quote_id", None)
    if not quote_id:
        return None
    return _down_payment_rows(session, int(quote_id))


def _render_document_pdf(session: Session | None, invoice, company=None, customer=None) -> bytes:
    """PDF eines Dokuments; eine Schlussrechnung zieht ihre Abschlagsrechnungen ab."""
    comp = company or getattr(invoice, "company", None)
    cust = customer or getattr(invoice, "customer", None)
    if session is not None:
        if comp is None and getattr(invoice, "company_id", None):
            comp = session.get(Company, int(invoice.company_id))
        if cust is None and getattr(invoice, "customer_id", None):
            cust = session.get(Customer, int(invoice.customer_id))
    return render_invoice_to_pdf_bytes(
        invoice=invoice,
        company=comp,
        customer=cust,
        down_payments=_final_invoice_down_payments(session, invoice),
    )


def _ensure_status_allowed(session: Session, invoice: Invoice, new_status: str) -> None:
    """Prüft, ob der Statuswechsel erlaubt ist; wirft 409 (Konflikt) oder 400 (ungültig)."""
    # Das Zurücksetzen einer Entscheidung auf „Gesendet“ kommt vor der Endgültigkeit:
    # es ist der dokumentierte Rückweg, solange das Angebot keine Rechnung hat.
    reset = decision_reset_reason(invoice, new_status, quote_has_invoices(session, invoice))
    if reset:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reset)
    finality = accepted_quote_status_reason(invoice, new_status)
    if finality:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=finality)
    reason = status_not_allowed_reason(invoice, new_status)
    if reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)


def _ensure_quote_editable(invoice: Invoice) -> None:
    """Angenommene und abgelehnte Angebote sind nur noch lesbar."""
    if is_accepted_quote(invoice):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ein angenommenes Angebot lässt sich nicht mehr ändern",
        )
    if is_rejected_quote(invoice):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ein abgelehntes Angebot lässt sich nicht mehr ändern",
        )


def _billing_read(invoice: Invoice) -> QuoteBillingRead | None:
    """Erlaubte Abrechnungsaktionen eines Angebots (#495); None für Rechnungen."""
    if getattr(invoice, "document_type", None) != DocumentType.QUOTE:
        return None
    session = object_session(invoice)
    if session is None:
        return None
    return QuoteBillingRead(**quote_billing(session, invoice).as_dict())


def _to_read_model(invoice: Invoice) -> InvoiceRead:
    """Convert SQLModel Invoice + Items to InvoiceRead (Pydantic)."""
    items: list[InvoiceItem] = []
    for it in (getattr(invoice, "items", None) or []):
        items.append(InvoiceItem(
            id=int(it.id) if it.id else None,
            description=it.description,
            quantity=float(it.quantity),
            unit_price=float(it.unit_price),
        ))
    attachments = [_attachment_to_read(attachment) for attachment in invoice.attachments]
    quote = getattr(invoice, "quote", None)
    return InvoiceRead(
        id=int(invoice.id),
        customer_id=int(invoice.customer_id),
        document_type=_document_type_value(invoice),
        nr=invoice.nr,
        title=invoice.title or "Rechnung",
        subject=invoice.subject or "",
        date=invoice.date or "",
        delivery_date=invoice.delivery_date or "",
        valid_until=getattr(invoice, "valid_until", "") or "",
        recipient_name=invoice.recipient_name or "",
        recipient_street=invoice.recipient_street or "",
        recipient_postal_code=invoice.recipient_postal_code or "",
        recipient_city=invoice.recipient_city or "",
        legacy=bool(invoice.legacy) if hasattr(invoice, 'legacy') else False,
        total_brutto=float(invoice.total_brutto or 0.0),
        status=invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status),
        revision_nr=int(invoice.revision_nr or 0),
        updated_at=invoice.updated_at or "",
        related_invoice_id=int(invoice.related_invoice_id) if invoice.related_invoice_id else None,
        quote_id=int(quote.id) if quote else None,
        quote_nr=quote.nr if quote else None,
        down_payment_index=(
            int(invoice.down_payment_index)
            if getattr(invoice, "down_payment_index", None) is not None
            else None
        ),
        is_final_invoice=bool(getattr(invoice, "is_final_invoice", False)),
        linked_invoices=[
            LinkedInvoiceRead(
                id=int(linked.id),
                nr=linked.nr,
                status=linked.status.value if hasattr(linked.status, "value") else str(linked.status),
                total_brutto=float(linked.total_brutto or 0.0),
                installment_index=(
                    int(linked.down_payment_index)
                    if getattr(linked, "down_payment_index", None) is not None
                    else None
                ),
                is_down_payment=getattr(linked, "down_payment_index", None) is not None,
                is_final_invoice=bool(getattr(linked, "is_final_invoice", False)),
            )
            for linked in (getattr(invoice, "quote_invoices", None) or [])
        ],
        payment_link_url=invoice.payment_link_url or "",
        payment_provider=invoice.payment_provider or "",
        items=items,
        attachments=attachments,
        payment_plan=[
            PaymentInstallmentRead(**rate)
            for rate in installments_with_amounts(
                getattr(invoice, "payment_plan", None), float(invoice.total_brutto or 0.0)
            )
        ],
        billing=_billing_read(invoice),
    )


@router.get("/suggestions")
def get_line_item_suggestions(
    customer_id: int,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Return distinct line item descriptions + unit prices from past invoices for a customer."""
    stmt = (
        select(InvoiceItemModel.description, InvoiceItemModel.unit_price)
        .join(Invoice, InvoiceItemModel.invoice_id == Invoice.id)
        .where(
            Invoice.customer_id == customer_id,
            Invoice.document_type == DocumentType.INVOICE,
        )
        .distinct()
        .limit(50)
    )
    rows = session.exec(stmt).all()
    seen = set()
    result = []
    for desc, price in rows:
        key = (desc.strip().lower() if desc else "", float(price) if price else 0.0)
        if key not in seen:
            seen.add(key)
            result.append({"description": desc, "unit_price": float(price) if price else 0.0})
    return result


@router.post("/bulk-status", response_model=list[InvoiceRead])
def bulk_status_update(
    payload: BulkStatusUpdate,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Transition multiple invoices to a new status atomically."""
    updated = []
    for inv_id in payload.invoice_ids:
        invoice = session.get(Invoice, inv_id)
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invoice {inv_id} not found",
            )
        _ensure_status_allowed(session, invoice, payload.status)
        invoice.status = payload.status
        invoice.revision_nr = int(invoice.revision_nr or 0) + 1
        session.add(invoice)
    session.commit()
    for inv_id in payload.invoice_ids:
        invoice = session.get(Invoice, inv_id)
        updated.append(_to_read_model(invoice))
    return updated


@router.post("/{invoice_id}/payment-link")
def generate_invoice_payment_link(
    invoice_id: int,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Generate a Stripe Checkout Session URL for an invoice."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    url = create_payment_link(invoice_id=invoice_id, company=company, session=session)
    return {"payment_link_url": url}


@router.post("/{invoice_id}/check-payment")
def check_invoice_payment(
    invoice_id: int,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Check Stripe for a completed payment on this invoice. Returns paid status."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    paid = check_payment(invoice_id=invoice_id, company=company, session=session)
    return {"paid": paid}


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    document_type: DocumentType = DocumentType.INVOICE,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
    company: Company = Depends(get_current_company),
):
    """List documents of one type (default invoices) for current company, newest first."""
    statement = (
        select(Invoice)
        .where(Invoice.company_id == int(company.id), Invoice.document_type == document_type)
        .options(selectinload(Invoice.attachments).selectinload(InvoiceAttachment.document))
        .order_by(Invoice.nr.desc())
    )
    invoices = session.exec(statement).all()
    return [_to_read_model(inv) for inv in invoices]


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: int,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Get one invoice by id."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return _to_read_model(invoice)


@router.put("/{invoice_id}/status", response_model=InvoiceRead)
def update_invoice_status(
    invoice_id: int,
    payload: InvoiceStatusUpdate,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Transition invoice status. Bumps revision_nr."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    _ensure_status_allowed(session, invoice, payload.status)
    invoice.status = payload.status
    invoice.revision_nr = int(invoice.revision_nr or 0) + 1
    invoice.updated_at = invoice.updated_at  # server-computed in real impl
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    # A down payment becoming billable (or cancelled) changes the rest of its final invoice.
    if getattr(invoice, "down_payment_index", None) is not None and getattr(invoice, "quote_id", None):
        _refresh_final_invoices_for_quote(session, int(invoice.quote_id))
    return _to_read_model(invoice)


@router.put("/{invoice_id}", response_model=InvoiceRead)
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Update invoice header fields. Creates revision record, re-renders PDF."""
    from datetime import datetime
    from types import SimpleNamespace
    from data import InvoiceRevision, Company, Customer

    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    _ensure_quote_editable(invoice)

    changed = False
    for field in ("title", "subject", "date", "delivery_date", "recipient_name",
                  "recipient_street", "recipient_postal_code", "recipient_city",
                  "valid_until"):
        val = getattr(payload, field, None)
        if val is not None and val != getattr(invoice, field, ""):
            setattr(invoice, field, val)
            changed = True
    if payload.payment_plan is not None:
        if invoice.document_type != DocumentType.QUOTE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nur Angebote haben einen Zahlungsplan")
        plan_json = dump_payment_plan(payload.payment_plan)
        if plan_json != (invoice.payment_plan or "[]"):
            invoice.payment_plan = plan_json
            changed = True
    if payload.intro_text is not None and payload.intro_text != (invoice.intro_text or ""):
        invoice.intro_text = payload.intro_text
        changed = True
    if payload.service_from is not None:
        f = payload.service_from
        t = payload.service_to or ""
        if t and t != f:
            invoice.delivery_date = f"{f} bis {t}"
        else:
            invoice.delivery_date = f or ""
        changed = True

    if changed:
        invoice.revision_nr = int(invoice.revision_nr or 0) + 1
        invoice.updated_at = datetime.now().isoformat()
        try:
            comp = session.get(Company, int(invoice.company_id)) if invoice.company_id else None
            cust = session.get(Customer, int(invoice.customer_id)) if invoice.customer_id else None
            items = list(getattr(invoice, "items", None) or [])
            clean_items = [{"description": it.description or "",
                            "quantity": float(it.quantity or 0),
                            "unit_price": float(it.unit_price or 0),
                            "tax_rate": 0} for it in items]
            preview = SimpleNamespace(
                company=comp, customer=cust, title=invoice.title,
                invoice_number=invoice.nr, date=invoice.date,
                delivery_date=invoice.delivery_date, payment_terms="",
                address_name=invoice.recipient_name,
                address_street=invoice.recipient_street,
                address_zip=invoice.recipient_postal_code,
                address_city=invoice.recipient_city,
                address_country=getattr(cust, "country", "") or "",
                ust_enabled=not bool(getattr(comp, "is_small_business", False)) if comp else True,
                document_type=invoice.document_type, valid_until=invoice.valid_until,
                payment_plan=invoice.payment_plan, vat_rate=invoice.vat_rate,
                down_payment_index=getattr(invoice, "down_payment_index", None),
            )
            preview.__dict__["intro_text"] = invoice.intro_text or ""
            preview.__dict__["line_items"] = clean_items
            preview.__dict__["totals"] = {"gross": float(invoice.total_brutto or 0)}
            preview.__dict__["total_brutto"] = float(invoice.total_brutto or 0)
            is_final = bool(getattr(invoice, "is_final_invoice", False))
            preview.__dict__["is_final_invoice"] = is_final
            invoice.pdf_bytes = render_invoice_to_pdf_bytes(
                preview, down_payments=_final_invoice_down_payments(session, invoice)
            )
        except Exception as e:
            logger.exception("PDF re-render failed on invoice update")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"PDF-Neuerstellung fehlgeschlagen: {e}") from e

        session.add(InvoiceRevision(
            invoice_id=invoice_id,
            revision_nr=int(invoice.revision_nr),
            reason=payload.reason or "Bearbeitung",
            pdf_filename_previous=invoice.pdf_filename or "",
        ))
        session.add(invoice)
        session.commit()
        session.refresh(invoice)

    return _to_read_model(invoice)


@router.post("/{invoice_id}/regenerate-pdf")
def regenerate_invoice_pdf(
    invoice_id: int,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Replace the stored PDF from current invoice and company data, retaining its number."""
    from datetime import datetime

    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    pdf_bytes = _render_document_pdf(session, invoice)

    next_revision = int(invoice.revision_nr or 0) + 1
    invoice.pdf_bytes = pdf_bytes
    invoice.pdf_storage = "db"
    invoice.revision_nr = next_revision
    invoice.updated_at = datetime.now().isoformat()
    session.add(InvoiceRevision(
        invoice_id=invoice_id,
        revision_nr=next_revision,
        reason="PDF mit aktuellen Firmendaten neu erzeugt",
        pdf_filename_previous=invoice.pdf_filename or "",
    ))
    session.add(invoice)
    session.commit()
    return {"invoice_id": invoice_id, "invoice_number": invoice.nr, "revision_nr": next_revision}


@router.post("/preview-pdf", responses={200: {"content": {"application/pdf": {}}}})
def preview_pdf(
    payload: InvoiceDraft,
    _user_id: int = Depends(require_session_auth),
    company: Company = Depends(get_current_company),
) -> Response:
    """Generate PDF bytes for a draft invoice (no DB write, no invoice number assigned)."""
    pdf_bytes = render_invoice_to_pdf_bytes(payload.model_dump(), company=company)
    return Response(content=pdf_bytes, media_type="application/pdf")


def _resolve_invoice_pdf_bytes(invoice, session=None) -> bytes:
    """Liefert die PDF-Bytes: erst gespeichert, sonst live rendern.

    Beim Live-Render müssen Company und Customer aus den Relationships geladen
    werden, damit die PDF Absender (Firmenname, IBAN, BIC) + Empfänger hat.
    """
    if getattr(invoice, "pdf_bytes", None):
        return bytes(invoice.pdf_bytes)
    return _render_document_pdf(session, invoice)


@router.get(
    "/{invoice_id}/preview-pdf",
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {"description": "Invoice not found"},
    },
)
def preview_pdf_for_invoice(
    invoice_id: int,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
) -> Response:
    """PDF der finalisierten Rechnung (server-gespeichert oder on-the-fly gerendert)."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    pdf_bytes = _resolve_invoice_pdf_bytes(invoice, session)
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get(
    "/{invoice_id}/download",
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {"description": "Invoice not found"},
    },
)
def download_invoice_pdf(
    invoice_id: int,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
) -> Response:
    """PDF als Download (Content-Disposition: attachment)."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    pdf_bytes = _resolve_invoice_pdf_bytes(invoice, session)
    fallback = "angebot" if getattr(invoice, "document_type", None) == DocumentType.QUOTE else "rechnung"
    filename = (getattr(invoice, "pdf_filename", "") or "").strip() or f"{fallback}-{invoice_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def create_invoice(
    payload: InvoiceDraft,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Finalize a draft invoice: assign number, persist items, render PDF, store."""
    document_type = DocumentType(payload.document_type)
    doc_status = InvoiceStatus(payload.status)
    if "status" in payload.model_fields_set:
        # Ausdrücklich gewählter Status: die Regeln der Dokumentart gelten.
        reason = creation_status_reason(document_type, doc_status)
        if reason:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)
    else:
        # Ohne ausdrücklichen Status: ein Angebot startet im Entwurf, eine Rechnung offen.
        doc_status = InvoiceStatus.DRAFT if document_type == DocumentType.QUOTE else InvoiceStatus.OPEN
    try:
        inv_id = finalize_invoice_logic(
            session=session,
            comp_id=int(company.id),
            cust_id=payload.customer_id,
            title=payload.title,
            date_str=payload.date,
            delivery_str=payload.delivery_date,
            recipient_data={
                "recipient_name": payload.recipient_name,
                "recipient_street": payload.recipient_street,
                "recipient_postal_code": payload.recipient_postal_code,
                "recipient_city": payload.recipient_city,
            },
            items=[it.model_dump() | {"tax_rate": payload.vat_rate} for it in payload.items],
            ust_enabled=payload.ust_enabled,
            status=doc_status,
            subject=payload.subject,
            intro_text=payload.intro_text,
            service_from=payload.service_from,
            service_to=payload.service_to,
            document_type=document_type,
            valid_until=payload.valid_until,
            payment_plan=payload.payment_plan,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    session.commit()

    invoice = session.get(Invoice, inv_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invoice not found after finalize")
    return _to_read_model(invoice)


# ── Invoice Item CRUD ──


def _rerender_quote_pdf(session: Session, invoice: Invoice) -> None:
    """Keep a quote's or final invoice's stored PDF in step with its positions (preview = download)."""
    is_final = bool(getattr(invoice, "is_final_invoice", False))
    if getattr(invoice, "document_type", None) != DocumentType.QUOTE and not is_final:
        return
    invoice.pdf_bytes = _render_document_pdf(session, invoice)
    session.add(invoice)
    session.commit()
    session.refresh(invoice)


def _refresh_final_invoices_for_quote(session: Session, quote_id: int) -> None:
    """Recompute and re-render every open final invoice after its deductions changed."""
    finals = session.exec(
        select(Invoice).where(
            Invoice.quote_id == int(quote_id),
            Invoice.is_final_invoice == True,  # noqa: E712 — SQLModel column comparison
            Invoice.status != InvoiceStatus.CANCELLED,
        )
    ).all()
    if not finals:
        return
    for final in finals:
        recompute_total_brutto(final, document_vat_rate(final), session)
        final.pdf_bytes = _render_document_pdf(session, final)
        final.revision_nr = int(final.revision_nr or 0) + 1
        session.add(final)
    session.commit()


def _refresh_quote_after_down_payment_change(session: Session, invoice: Invoice) -> None:
    """Nach einer Änderung an einer Abschlagsrechnung: die Schlussrechnungen nachziehen.

    Der Betrag einer Abschlagsrechnung ist der Abzug der Schlussrechnung. Wird die
    Abschlagsrechnung geändert oder gelöscht, verschiebt sich der Restbetrag.
    """
    if getattr(invoice, "down_payment_index", None) is None:
        return
    quote_id = getattr(invoice, "quote_id", None)
    if not quote_id:
        return
    _refresh_final_invoices_for_quote(session, int(quote_id))


@router.post("/{invoice_id}/items", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def add_invoice_item(
    invoice_id: int,
    payload: InvoiceItem,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Add a line item to an existing invoice."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    _ensure_quote_editable(invoice)
    vat_rate = document_vat_rate(invoice)
    item = InvoiceItemModel(
        invoice_id=invoice_id,
        description=payload.description,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
    )
    session.add(item)
    session.flush()
    session.refresh(invoice)
    recompute_total_brutto(invoice, vat_rate, session)
    invoice.revision_nr = int(invoice.revision_nr or 0) + 1
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    _rerender_quote_pdf(session, invoice)
    _refresh_quote_after_down_payment_change(session, invoice)
    return _to_read_model(invoice)


@router.put("/{invoice_id}/items/{item_id}", response_model=InvoiceRead)
def update_invoice_item(
    invoice_id: int,
    item_id: int,
    payload: InvoiceItem,
    _user_user: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Update a line item on an existing invoice."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    _ensure_quote_editable(invoice)
    item = session.get(InvoiceItemModel, item_id)
    if not item or item.invoice_id != invoice_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    vat_rate = document_vat_rate(invoice)
    item.description = payload.description
    item.quantity = payload.quantity
    item.unit_price = payload.unit_price
    session.add(item)
    session.flush()
    recompute_total_brutto(invoice, vat_rate, session)
    invoice.revision_nr = int(invoice.revision_nr or 0) + 1
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    _rerender_quote_pdf(session, invoice)
    _refresh_quote_after_down_payment_change(session, invoice)
    return _to_read_model(invoice)


@router.delete("/{invoice_id}/items/{item_id}", response_model=InvoiceRead)
def delete_invoice_item(
    invoice_id: int,
    item_id: int,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Delete a line item from an existing invoice."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    _ensure_quote_editable(invoice)
    item = session.get(InvoiceItemModel, item_id)
    if not item or item.invoice_id != invoice_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    vat_rate = document_vat_rate(invoice)
    session.delete(item)
    session.flush()
    session.refresh(invoice)
    recompute_total_brutto(invoice, vat_rate, session)
    invoice.revision_nr = int(invoice.revision_nr or 0) + 1
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    _rerender_quote_pdf(session, invoice)
    _refresh_quote_after_down_payment_change(session, invoice)
    return _to_read_model(invoice)


def _get_invoice_for_company(session: Session, invoice_id: int, company: Company) -> Invoice:
    invoice = session.get(Invoice, invoice_id)
    if not invoice or int(invoice.company_id) != int(company.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


def _get_document_for_company(session: Session, document_id: int, company: Company) -> Document:
    document = session.get(Document, document_id)
    if not document or int(document.company_id) != int(company.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.post("/{invoice_id}/attachments", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def add_invoice_attachment(
    invoice_id: int,
    payload: InvoiceAttachmentCreate,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Link an existing document (Beleg) to an invoice."""
    invoice = _get_invoice_for_company(session, invoice_id, company)
    document = _get_document_for_company(session, payload.document_id, company)
    session.add(InvoiceAttachment(invoice_id=invoice.id, document_id=document.id))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Beleg ist bereits angehängt")
    session.refresh(invoice)
    return _to_read_model(invoice)


@router.delete("/{invoice_id}/attachments/{attachment_id}", response_model=InvoiceRead)
def delete_invoice_attachment(
    invoice_id: int,
    attachment_id: int,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Remove a document link from an invoice. The document itself stays in Belege."""
    invoice = _get_invoice_for_company(session, invoice_id, company)
    attachment = session.get(InvoiceAttachment, attachment_id)
    if not attachment or int(attachment.invoice_id) != invoice_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    session.delete(attachment)
    session.commit()
    session.refresh(invoice)
    return _to_read_model(invoice)


MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


def _attachment_filename(document: Document, taken: set[str]) -> str:
    """Mail filename of a receipt: title plus the file's own extension, unique within the mail."""
    mime_type = document.mime or document.mime_type or "application/pdf"
    name = build_download_filename(document.title or document.original_filename, mime_type)
    root, ext = os.path.splitext(name)
    if not ext:
        ext = os.path.splitext(document.original_filename or document.filename or "")[1]
    candidate, counter = f"{root}{ext}", 2
    while candidate.lower() in taken:
        candidate = f"{root} ({counter}){ext}"
        counter += 1
    taken.add(candidate.lower())
    return candidate


def _load_send_attachments(invoice: Invoice, invoice_filename: str) -> list[dict]:
    """Receipts as mail attachments. A missing file or an oversized mail aborts the send."""
    payloads: list[dict] = []
    taken = {invoice_filename.lower()}
    total = 0
    for attachment in invoice.attachments:
        document = attachment.document
        content = read_document_bytes(document)
        if not content:
            logger.warning(
                "Invoice attachment file missing invoice=%s document=%s",
                invoice.id,
                document.id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Datei des Belegs „{document.title or document.original_filename}“ fehlt",
            )
        total += len(content)
        if total > MAX_ATTACHMENT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Die Belege sind zusammen zu groß für eine E-Mail (max. 20 MB)",
            )
        payloads.append({
            "filename": _attachment_filename(document, taken),
            "content": content,
            "mime_type": document.mime or document.mime_type or "application/pdf",
        })
    return payloads


@router.post("/{invoice_id}/send")
def send_invoice_email_endpoint(
    invoice_id: int,
    payload: InvoiceSendRequest | None = None,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
    company: Company = Depends(get_current_company),
):
    """Send the invoice PDF as an email attachment to the customer."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    customer = session.get(Customer, invoice.customer_id) if invoice.customer_id else None
    if not customer or not customer.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer has no email address",
        )

    quote = invoice.document_type == DocumentType.QUOTE
    if quote:
        # A quote may have changed since its PDF was stored: always send the current one.
        _rerender_quote_pdf(session, invoice)
    pdf_bytes = _resolve_invoice_pdf_bytes(invoice, session)
    filename = build_invoice_filename(company, invoice, customer)
    payload = payload or InvoiceSendRequest()

    extra_attachments = (
        _load_send_attachments(invoice, filename)
        if payload.include_attachments
        else []
    )

    email = build_invoice_email(
        company=company,
        customer=customer,
        invoice=invoice,
        message=payload.message,
    )

    smtp_config = {
        "host": company.smtp_server,
        "port": company.smtp_port or 587,
        "user": company.smtp_user,
        "password": company.smtp_password,
        "sender": company.default_sender_email or company.email or company.smtp_user,
    }

    try:
        success = send_email(
            to=customer.email,
            subject=email.subject,
            text=email.text,
            html=email.html,
            smtp_config=smtp_config,
            attachments=[
                {
                    "filename": filename,
                    "content": bytes(pdf_bytes),
                    "mime_type": "application/pdf",
                },
                *extra_attachments,
            ],
        )
    except Exception:
        logger.exception("Failed to send invoice email")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Der E-Mail-Versand ist fehlgeschlagen.",
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Der E-Mail-Versand ist noch nicht eingerichtet.",
        )

    if invoice.document_type != DocumentType.QUOTE or invoice.status == InvoiceStatus.DRAFT:
        invoice.status = InvoiceStatus.SENT
    invoice.revision_nr = int(invoice.revision_nr or 0) + 1
    session.add(invoice)
    session.commit()

    label = "Angebot" if quote else "Rechnung"
    return {"status": "ok", "message": f"{label} an {customer.email} gesendet"}


@router.delete("/{invoice_id}")
def delete_invoice_endpoint(
    invoice_id: int,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Delete an invoice and all associated records (items, revisions, audit logs, PDF)."""
    document = session.get(Invoice, invoice_id)
    if document is not None and document.quote_invoices:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ein Angebot mit Rechnungen lässt sich nicht löschen",
        )
    # Vor dem Löschen merken: eine gelöschte Abschlagsrechnung wird nicht mehr abgezogen.
    down_payment_quote_id = (
        int(document.quote_id)
        if document is not None
        and getattr(document, "down_payment_index", None) is not None
        and getattr(document, "quote_id", None)
        else None
    )
    ok, msg = delete_invoice(invoice_id, session=session)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    if down_payment_quote_id:
        _refresh_final_invoices_for_quote(session, down_payment_quote_id)
    return {"status": "ok", "message": f"Rechnung #{invoice_id} gelöscht"}
