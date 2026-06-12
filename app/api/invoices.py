# =========================
# APP/API/INVOICES.PY
# =========================
"""
Invoice API: /api/invoices[/...]

Endpoints (Stand 2026-06-10):
- GET  /api/invoices                — Liste
- GET  /api/invoices/{id}           — Detail
- PUT  /api/invoices/{id}/status    — Status-Transition
- POST /api/invoices/preview-pdf    — PDF-Bytes (Live-Preview, kein State)

Später (M5): POST /api/invoices (create + finalize), POST /api/invoices/{id}/correction.
"""

from __future__ import annotations

import logging
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import select

from data import Company, Customer, Invoice, InvoiceItem as InvoiceItemModel
from data import InvoiceStatus
from dependencies import db_session, get_current_company, require_session_auth
from invoice_numbering import build_invoice_filename
from logic import finalize_invoice_logic
from renderer import render_invoice_to_pdf_bytes
from schemas.invoice import (
    InvoiceDraft,
    InvoiceItem,
    InvoiceRead,
    InvoiceStatusUpdate,
)
from services.email import send_email

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/invoices", tags=["invoices"])


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
    return InvoiceRead(
        id=int(invoice.id),
        customer_id=int(invoice.customer_id),
        nr=invoice.nr,
        title=invoice.title or "Rechnung",
        date=invoice.date or "",
        delivery_date=invoice.delivery_date or "",
        recipient_name=invoice.recipient_name or "",
        recipient_street=invoice.recipient_street or "",
        recipient_postal_code=invoice.recipient_postal_code or "",
        recipient_city=invoice.recipient_city or "",
        total_brutto=float(invoice.total_brutto or 0.0),
        status=invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status),
        revision_nr=int(invoice.revision_nr or 0),
        updated_at=invoice.updated_at or "",
        related_invoice_id=int(invoice.related_invoice_id) if invoice.related_invoice_id else None,
        items=items,
    )


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """List all invoices. Filter (year, customer, status) kommt in M5."""
    statement = select(Invoice)
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


@router.post("/preview-pdf", responses={200: {"content": {"application/pdf": {}}}})
def preview_pdf(
    payload: InvoiceDraft,
    _user_id: int = Depends(require_session_auth),
    company: Company = Depends(get_current_company),
) -> Response:
    """Generate PDF bytes for a draft invoice (no DB write, no invoice number assigned)."""
    pdf_bytes = render_invoice_to_pdf_bytes(payload.model_dump(), company=company)
    return Response(content=pdf_bytes, media_type="application/pdf")


def _resolve_invoice_pdf_bytes(invoice) -> bytes:
    """Liefert die PDF-Bytes: erst gespeichert, sonst live rendern.

    Beim Live-Render müssen Company und Customer aus den Relationships geladen
    werden, damit die PDF Absender (Firmenname, IBAN, BIC) + Empfänger hat.
    """
    if getattr(invoice, "pdf_bytes", None):
        return bytes(invoice.pdf_bytes)
    company = getattr(invoice, "company", None)
    customer = getattr(invoice, "customer", None)
    # KRITISCH: invoice MUSS als kwarg übergeben werden, sonst gibt
    # render_invoice_to_pdf_bytes `kwargs.get("invoice") = None` zurück
    # und der ReportLab-Renderer bekommt eine leere Invoice.
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
    pdf_bytes = _resolve_invoice_pdf_bytes(invoice)
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
    pdf_bytes = _resolve_invoice_pdf_bytes(invoice)
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


@router.post("/{invoice_id}/send")
def send_invoice_email_endpoint(
    invoice_id: int,
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

    pdf_bytes = _resolve_invoice_pdf_bytes(invoice)
    filename = build_invoice_filename(company, invoice, customer)

    subject = f"Rechnung {invoice.nr or ''}".strip()
    amount = f"{float(invoice.total_brutto or 0):,.2f} EUR"
    recipient_name = customer.display_name or ""
    body = (
        f"Guten Tag {recipient_name},\n\n"
        f"im Anhang finden Sie Ihre Rechnung {invoice.nr or ''} vom {invoice.date} über {amount}.\n\n"
        f"Viele Grüße\n{company.name or ''}"
    ).strip()

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
            subject=subject,
            text=body,
            smtp_config=smtp_config,
            attachments=[
                {
                    "filename": filename,
                    "content": bytes(pdf_bytes),
                    "mime_type": "application/pdf",
                }
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
