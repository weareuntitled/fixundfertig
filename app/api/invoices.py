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
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from data import Company, Customer, Document, Invoice, InvoiceItem as InvoiceItemModel
from data import InvoiceAttachment, InvoiceRevision, InvoiceStatus
from actions import delete_invoice
from dependencies import db_session, get_current_company, require_session_auth
from invoice_numbering import build_invoice_filename
from logic import finalize_invoice_logic
from renderer import render_invoice_to_pdf_bytes
from schemas.invoice import (
    BulkStatusUpdate,
    InvoiceAttachmentCreate,
    InvoiceAttachmentRead,
    InvoiceDraft,
    InvoiceItem,
    InvoiceRead,
    InvoiceSendRequest,
    InvoiceStatusUpdate,
    InvoiceUpdate,
)
from services.documents import build_download_filename, read_document_bytes
from services.email import send_email
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
    """Duplicate an existing invoice as a new DRAFT with same customer + items."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    items = [
        {
            "description": it.description,
            "quantity": float(it.quantity),
            "unit_price": float(it.unit_price),
        }
        for it in (getattr(invoice, "items", None) or [])
    ]

    try:
        inv_id = finalize_invoice_logic(
            session=session,
            comp_id=int(company.id),
            cust_id=int(invoice.customer_id),
            title=invoice.title or "Rechnung",
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
            ust_enabled=True,
            status=InvoiceStatus.DRAFT,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    session.commit()

    new_invoice = session.get(Invoice, inv_id)
    if not new_invoice:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invoice not found after duplicate")
    return _to_read_model(new_invoice)


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
    return InvoiceRead(
        id=int(invoice.id),
        customer_id=int(invoice.customer_id),
        nr=invoice.nr,
        title=invoice.title or "Rechnung",
        subject=invoice.subject or "",
        date=invoice.date or "",
        delivery_date=invoice.delivery_date or "",
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
        payment_link_url=invoice.payment_link_url or "",
        payment_provider=invoice.payment_provider or "",
        items=items,
        attachments=attachments,
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
        .where(Invoice.customer_id == customer_id)
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
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
    company: Company = Depends(get_current_company),
):
    """List invoices for current company, newest first."""
    statement = (
        select(Invoice)
        .where(Invoice.company_id == int(company.id))
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
    invoice.status = payload.status
    invoice.revision_nr = int(invoice.revision_nr or 0) + 1
    invoice.updated_at = invoice.updated_at  # server-computed in real impl
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
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

    changed = False
    for field in ("title", "subject", "date", "delivery_date", "recipient_name",
                  "recipient_street", "recipient_postal_code", "recipient_city",
                  "intro_text"):
        val = getattr(payload, field, None)
        if val is not None and val != getattr(invoice, field, ""):
            setattr(invoice, field, val)
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
            )
            preview.__dict__["intro_text"] = invoice.intro_text or ""
            preview.__dict__["line_items"] = clean_items
            preview.__dict__["totals"] = {"gross": float(invoice.total_brutto or 0)}
            preview.__dict__["total_brutto"] = float(invoice.total_brutto or 0)
            invoice.pdf_bytes = render_invoice_to_pdf_bytes(preview)
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

    company = session.get(Company, int(invoice.company_id)) if invoice.company_id else None
    customer = session.get(Customer, int(invoice.customer_id)) if invoice.customer_id else None
    pdf_bytes = render_invoice_to_pdf_bytes(invoice=invoice, company=company, customer=customer)

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
    company = getattr(invoice, "company", None)
    customer = getattr(invoice, "customer", None)
    # ponytail: lazy-load company/customer if session available and relationships not loaded
    if session is not None and company is None and getattr(invoice, "company_id", None):
        company = session.get(Company, int(invoice.company_id))
    if session is not None and customer is None and getattr(invoice, "customer_id", None):
        customer = session.get(Customer, int(invoice.customer_id))
    return render_invoice_to_pdf_bytes(
        invoice=invoice, company=company, customer=customer,
    )


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
    filename = (getattr(invoice, "pdf_filename", "") or "").strip() or f"rechnung-{invoice_id}.pdf"
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
            status=InvoiceStatus(payload.status),
            subject=payload.subject,
            intro_text=payload.intro_text,
            service_from=payload.service_from,
            service_to=payload.service_to,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    session.commit()

    invoice = session.get(Invoice, inv_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invoice not found after finalize")
    return _to_read_model(invoice)


# ── Invoice Item CRUD ──


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
    item = InvoiceItemModel(
        invoice_id=invoice_id,
        description=payload.description,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
    )
    session.add(item)
    # Recalculate total
    items = list(getattr(invoice, "items", None) or [])
    items.append(item)
    invoice.total_brutto = sum(it.quantity * it.unit_price for it in items)
    invoice.revision_nr = int(invoice.revision_nr or 0) + 1
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
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
    item = session.get(InvoiceItemModel, item_id)
    if not item or item.invoice_id != invoice_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    item.description = payload.description
    item.quantity = payload.quantity
    item.unit_price = payload.unit_price
    session.add(item)
    # Recalculate total
    items = list(getattr(invoice, "items", None) or [])
    invoice.total_brutto = sum(it.quantity * it.unit_price for it in items)
    invoice.revision_nr = int(invoice.revision_nr or 0) + 1
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
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
    item = session.get(InvoiceItemModel, item_id)
    if not item or item.invoice_id != invoice_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    session.delete(item)
    # Recalculate total from remaining items
    remaining = [it for it in (getattr(invoice, "items", None) or []) if int(it.id) != item_id]
    invoice.total_brutto = sum(it.quantity * it.unit_price for it in remaining)
    invoice.revision_nr = int(invoice.revision_nr or 0) + 1
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
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
    except Exception as exc:
        logger.exception("Failed to send invoice email")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"E-Mail-Versand fehlgeschlagen: {exc}",
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="E-Mail konnte nicht gesendet werden (SMTP nicht konfiguriert)",
        )

    invoice.status = InvoiceStatus.SENT
    invoice.revision_nr = int(invoice.revision_nr or 0) + 1
    session.add(invoice)
    session.commit()

    return {"status": "ok", "message": f"Rechnung an {customer.email} gesendet"}


@router.delete("/{invoice_id}")
def delete_invoice_endpoint(
    invoice_id: int,
    _user_id: int = Depends(require_session_auth),
):
    """Delete an invoice and all associated records (items, revisions, audit logs, PDF)."""
    ok, msg = delete_invoice(invoice_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return {"status": "ok", "message": f"Rechnung #{invoice_id} gelöscht"}
