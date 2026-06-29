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
    BulkStatusUpdate,
    InvoiceDraft,
    InvoiceItem,
    InvoiceRead,
    InvoiceStatusUpdate,
)
from services.email import send_email
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
        payment_link_url=invoice.payment_link_url or "",
        payment_provider=invoice.payment_provider or "",
        items=items,
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

    inv_nr = invoice.nr or ""
    inv_date = invoice.date or ""
    amount_float = float(invoice.total_brutto or 0)
    amount_str = f"{amount_float:,.2f} EUR".replace(",", ".")
    # Strip trailing zeros after comma for German format
    amount_german = f"{amount_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    due_date_str = ""
    if inv_date:
        from datetime import datetime, timedelta
        try:
            dt = datetime.fromisoformat(inv_date)
            due = dt + timedelta(days=30)
            due_date_str = due.strftime("%d.%m.%Y")
        except ValueError:
            pass
    inv_date_formatted = ""
    if inv_date:
        try:
            inv_date_formatted = datetime.fromisoformat(inv_date).strftime("%d.%m.%Y")
        except ValueError:
            inv_date_formatted = inv_date

    recipient_name = customer.display_name or ""
    payment_link = getattr(invoice, "payment_link_url", "") or ""

    smtp_config = {
        "host": company.smtp_server,
        "port": company.smtp_port or 587,
        "user": company.smtp_user,
        "password": company.smtp_password,
        "sender": company.default_sender_email or company.email or company.smtp_user,
    }

    # Build lines summary
    items_html = ""
    items_text = ""
    for it in (getattr(invoice, "items", None) or []):
        desc = it.description or ""
        qty = float(it.quantity or 1)
        price = float(it.unit_price or 0)
        total_line = qty * price
        line_german = f"{total_line:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        items_html += f"""<tr style="font-size:14px;color:#374151;">
<td style="padding:6px 0;">{desc} × {qty:g}</td>
<td align="right" style="padding:6px 0;">{line_german} €</td>
</tr>"""
        items_text += f"  {desc} x {qty:g}: {line_german} €\n"

    show_ust = not bool(getattr(company, "is_small_business", False))
    netto = amount_float / 1.19 if show_ust else amount_float
    ust = amount_float - netto
    ust_german = f"{ust:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    ust_text = f"\nMwSt. 19%: {ust_german} €" if show_ust and ust > 0 else ""

    # Plain text body
    text_body = (
        f"Guten Tag {recipient_name},\n\n"
        f"anbei erhalten Sie Ihre Rechnung {inv_nr} vom {inv_date_formatted}.\n\n"
        f"Rechnungsbetrag: {amount_german} €\n"
        f"{ust_text}"
        + (f"\nFällig bis: {due_date_str}" if due_date_str else "")
        + "\n\nPositionen:\n" + items_text
        + ("\nBezahlen Sie jetzt online:\n" + payment_link if payment_link else "")
        + f"\n\nMit freundlichen Grüßen\n{company.name or 'FixundFertig'}"
    )

    # HTML body
    company_name = (company.name or "FixundFertig").strip()
    html_payment_block = ""
    if payment_link:
        html_payment_block = f"""
<tr><td style="padding:0 32px 16px;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;">
<p style="font-size:13px;color:#166534;margin:0 0 12px;font-weight:600;">Jetzt online bezahlen</p>
<a href="{payment_link}" target="_blank" style="display:inline-block;background:#001a42;color:#fff;font-size:14px;font-weight:600;padding:12px 32px;border-radius:8px;text-decoration:none;">Zahlungslink öffnen</a>
<p style="font-size:11px;color:#166534;margin:8px 0 0;">Sicher bezahlen per Karte (Stripe)</p>
</td></tr>
</table>
</td></tr>"""

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Inter,-apple-system,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px;">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08);">
<tr><td style="padding:32px 32px 0;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="font-size:20px;font-weight:700;color:#001a42;">{company_name}</td>
<td align="right" style="font-size:12px;color:#6b7280;">Rechnung {inv_nr}</td>
</tr>
</table>
<hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;">
</td></tr>
<tr><td style="padding:0 32px;">
<p style="font-size:14px;color:#374151;margin:0 0 16px;">Guten Tag {recipient_name},</p>
<p style="font-size:14px;color:#374151;margin:0 0 16px;">vielen Dank für Ihren Auftrag. Im Folgenden erhalten Sie die Details Ihrer Rechnung.</p>
</td></tr>
<tr><td style="padding:0 32px;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;border-radius:8px;padding:16px;">
<tr><td style="font-size:12px;color:#6b7280;padding-bottom:8px;">Rechnungsnummer</td>
<td align="right" style="font-size:12px;color:#6b7280;padding-bottom:8px;">Datum</td></tr>
<tr><td style="font-size:16px;font-weight:600;color:#001a42;">{inv_nr}</td>
<td align="right" style="font-size:16px;font-weight:600;color:#001a42;">{inv_date_formatted}</td></tr>
</table>
</td></tr>
<tr><td style="padding:16px 32px 0;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr style="font-size:12px;color:#6b7280;border-bottom:1px solid #e5e7eb;">
<td style="padding-bottom:8px;">Leistung</td>
<td align="right" style="padding-bottom:8px;">Betrag</td>
</tr>
{items_html}
</table>
</td></tr>
<tr><td style="padding:12px 32px 0;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td style="font-size:12px;color:#6b7280;">Zwischensumme</td>
<td align="right" style="font-size:14px;color:#374151;">{amount_german} €</td></tr>"""
    if show_ust and ust > 0:
        html_body += f"""<tr><td style="font-size:12px;color:#6b7280;">MwSt. 19%</td>
<td align="right" style="font-size:14px;color:#374151;">{ust_german} €</td></tr>"""
    html_body += f"""<tr><td style="font-size:16px;font-weight:700;color:#001a42;padding-top:8px;border-top:2px solid #001a42;">Gesamtbetrag</td>
<td align="right" style="font-size:16px;font-weight:700;color:#001a42;padding-top:8px;border-top:2px solid #001a42;">{amount_german} €</td></tr>
</table>
</td></tr>"""
    if due_date_str:
        html_body += f"""<tr><td style="padding:16px 32px;">
<p style="font-size:12px;color:#6b7280;margin:0;">Fällig bis: <strong style="color:#374151;">{due_date_str}</strong></p>
</td></tr>"""
    html_body += html_payment_block
    html_body += f"""<tr><td style="padding:0 32px 32px;">
<p style="font-size:13px;color:#374151;margin:0 0 4px;">Mit freundlichen Grüßen</p>
<p style="font-size:14px;font-weight:600;color:#001a42;margin:0;">{company_name}</p>
</td></tr>
<tr><td style="padding:16px 32px;background:#f9fafb;border-top:1px solid #e5e7eb;">
<p style="font-size:11px;color:#9ca3af;margin:0;text-align:center;">Diese Rechnung wurde automatisch von FixundFertig erstellt.</p>
</td></tr>
</table>
</td></tr></table>
</body>
</html>"""

    try:
        success = send_email(
            to=customer.email,
            subject=f"Rechnung {inv_nr} von {company_name} — {amount_german} €",
            text=text_body,
            html=html_body,
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
