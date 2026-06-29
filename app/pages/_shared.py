"""Shared imports, constants and helpers from the former pages.py.

Re-exports everything from shared_helpers and shared_cards for backward compat.
"""
from __future__ import annotations

import os
import json
from datetime import datetime
from io import BytesIO
from urllib.parse import urlencode

from nicegui import ui
from sqlmodel import select

from data import (
    Company,
    Customer,
    Invoice,
    InvoiceItem,
    InvoiceRevision,
    log_audit_action,
    InvoiceStatus,
    get_session,
)

from renderer import render_invoice_to_pdf_bytes
from invoice_numbering import build_invoice_filename

from styles import (
    STYLE_STEPPER_ACTIVE,
    STYLE_STEPPER_ARROW,
    STYLE_STEPPER_INACTIVE,
)


from services.email import send_email

# Re-export everything from extracted modules
from pages.shared_helpers import (  # noqa: F401
    register_shell_navigate,
    app_shell_nav_items,
    go_app_page,
    ui_handler,
    get_current_user_id,
    list_companies,
    get_primary_company,
    log_invoice_action,
    _parse_iso_date,
    _open_invoice_detail,
    _open_invoice_editor,
    is_readonly_mode,
    readonly_scope,
    _fetch_address_autocomplete,
    use_address_autocomplete,
)
from pages.shared_cards import (  # noqa: F401
    customer_contact_card,
    customer_address_card,
    insert_customer,
    customer_business_meta_card,
)


# -------------------------
# PDF Download and Mail
# -------------------------

def download_invoice_file(invoice: Invoice) -> None:

    if invoice and invoice.id:
        log_invoice_action("EXPORT_CREATED", invoice.id)

    pdf_path = (invoice.pdf_filename or "").strip()

    if not pdf_path and invoice.pdf_bytes:
        with get_session() as s:
            customer = s.get(Customer, int(invoice.customer_id)) if invoice.customer_id else None
            company = s.exec(select(Company)).first() or Company()
        filename = build_invoice_filename(company, invoice, customer) if invoice.nr else "rechnung.pdf"
        ui.download(BytesIO(invoice.pdf_bytes), filename=filename)
        return

    if not pdf_path:
        with get_session() as s:
            customer = s.get(Customer, int(invoice.customer_id)) if invoice.customer_id else None
            company = s.exec(select(Company)).first() or Company()
        pdf_bytes = render_invoice_to_pdf_bytes(invoice)
        if isinstance(pdf_bytes, bytearray):
            pdf_bytes = bytes(pdf_bytes)
        if not isinstance(pdf_bytes, bytes):
            raise TypeError("PDF output must be bytes")

        filename = build_invoice_filename(company, invoice, customer) if invoice.nr else "rechnung.pdf"
        invoice.pdf_bytes = pdf_bytes
        invoice.pdf_filename = filename
        if not invoice.pdf_storage:
            invoice.pdf_storage = "db"

        if invoice.id:
            with get_session() as s:
                inv = s.get(Invoice, invoice.id)
                if inv:
                    inv.pdf_bytes = pdf_bytes
                    inv.pdf_filename = filename
                    if not inv.pdf_storage:
                        inv.pdf_storage = "db"
                    s.add(inv)
                    s.commit()

        ui.download(BytesIO(pdf_bytes), filename=filename)
        return

    # Normalized path
    if not os.path.isabs(pdf_path) and not str(pdf_path).startswith("storage/"):
        pdf_path = f"storage/invoices/{pdf_path}"

    if os.path.exists(pdf_path):
        ui.download(pdf_path)
        return

    # File missing but invoice exists, regenerate
    with get_session() as s:
        customer = s.get(Customer, int(invoice.customer_id)) if invoice.customer_id else None
        company = s.exec(select(Company)).first() or Company()
    pdf_bytes = invoice.pdf_bytes or render_invoice_to_pdf_bytes(invoice)
    if isinstance(pdf_bytes, bytearray):
        pdf_bytes = bytes(pdf_bytes)
    if not isinstance(pdf_bytes, bytes):
        raise TypeError("PDF output must be bytes")

    filename = os.path.basename(invoice.pdf_filename) if invoice.pdf_filename else (build_invoice_filename(company, invoice, customer) if invoice.nr else "rechnung.pdf")
    pdf_path = f"storage/invoices/{filename}"
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    invoice.pdf_filename = filename
    if not invoice.pdf_storage:
        invoice.pdf_storage = "db"

    if invoice.id:
        with get_session() as s:
            inv = s.get(Invoice, invoice.id)
            if inv:
                inv.pdf_filename = filename
                if not inv.pdf_storage:
                    inv.pdf_storage = "db"
                s.add(inv)
                s.commit()

    ui.download(pdf_path)


def build_invoice_mailto(comp: Company | None, customer: Customer | None, invoice: Invoice) -> str:
    subject = f"Rechnung {invoice.nr or ''}".strip()
    amount = f"{float(invoice.total_brutto or 0):,.2f} EUR"

    body_lines = [
        f"Guten Tag {customer.display_name if customer else ''},".strip(),
        "",
        f"im Anhang finden Sie Ihre Rechnung {invoice.nr or ''} vom {invoice.date} über {amount}.",
        "",
        "Viele Grüße",
        comp.name if comp else "",
    ]

    params = urlencode({
        "subject": subject,
        "body": "\n".join(line for line in body_lines if line is not None),
    })

    recipient = customer.email if customer and customer.email else ""
    return f"mailto:{recipient}?{params}"


def send_invoice_email(comp: Company | None, customer: Customer | None, invoice: Invoice) -> None:
    if not customer or not customer.email:
        ui.notify("Keine Email-Adresse beim Kunden hinterlegt", color="red")
        return

    with get_session() as s:
        customer_db = s.get(Customer, int(invoice.customer_id)) if invoice.customer_id else customer
        company = s.exec(select(Company)).first() or comp or Company()

    filename = build_invoice_filename(company, invoice, customer_db) if invoice.nr else "rechnung.pdf"
    pdf_bytes = invoice.pdf_bytes
    if not pdf_bytes:
        pdf_bytes = render_invoice_to_pdf_bytes(invoice)

    subject = f"Rechnung {invoice.nr or ''}".strip()
    amount = f"{float(invoice.total_brutto or 0):,.2f} EUR"
    recipient_name = customer.display_name if customer else ""
    body = "\n".join(
        [
            f"Guten Tag {recipient_name},".strip(),
            "",
            f"im Anhang finden Sie Ihre Rechnung {invoice.nr or ''} vom {invoice.date} über {amount}.",
            "",
            "Viele Grüße",
            (comp.name if comp else "").strip(),
        ]
    ).strip()

    try:
        sent = send_email(
            to=customer.email,
            subject=subject,
            text=body,
            attachments=[
                {
                    "filename": filename,
                    "content": bytes(pdf_bytes),
                    "mime_type": "application/pdf",
                }
            ],
        )
    except Exception as exc:
        ui.notify(f"E-Mail Versand fehlgeschlagen: {exc}", color="red")
        return

    if sent:
        ui.notify("E-Mail mit PDF-Anhang gesendet", color="green")
        return

    mailto = build_invoice_mailto(comp, customer, invoice)
    ui.run_javascript(f"window.location.href = {json.dumps(mailto)}")
    ui.notify("SMTP nicht konfiguriert: Mail-Client ohne Anhang geöffnet", color="orange")


# -------------------------
# Revisions "Edit with risk"
# -------------------------

def _snapshot_invoice(session, invoice: Invoice) -> str:
    items = session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id)).all()
    payload = {
        "invoice": {
            "id": invoice.id,
            "customer_id": invoice.customer_id,
            "nr": invoice.nr,
            "title": invoice.title,
            "date": invoice.date,
            "delivery_date": invoice.delivery_date,
            "recipient_name": invoice.recipient_name,
            "recipient_street": invoice.recipient_street,
            "recipient_postal_code": invoice.recipient_postal_code,
            "recipient_city": invoice.recipient_city,
            "total_brutto": invoice.total_brutto,
            "status": invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status),
            "revision_nr": invoice.revision_nr,
            "updated_at": invoice.updated_at,
            "related_invoice_id": invoice.related_invoice_id,
            "pdf_filename": invoice.pdf_filename,
            "pdf_storage": invoice.pdf_storage,
        },
        "items": [
            {
                "id": it.id,
                "description": it.description,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
            }
            for it in items
        ],
    }
    return json.dumps(payload)


def create_invoice_revision_and_edit(invoice_id: int, reason: str) -> int | None:
    with get_session() as s:
        original = s.get(Invoice, invoice_id)
        if not original:
            return None

        next_revision = int(original.revision_nr or 0) + 1
        snapshot_json = _snapshot_invoice(s, original)

        s.add(InvoiceRevision(
            invoice_id=original.id,
            revision_nr=next_revision,
            reason=reason,
            snapshot_json=snapshot_json,
            pdf_filename_previous=original.pdf_filename or "",
        ))

        original.revision_nr = next_revision
        original.updated_at = datetime.now().isoformat()
        s.add(original)

        new_inv = Invoice(
            customer_id=original.customer_id,
            nr=None,
            title=original.title,
            date=original.date,
            delivery_date=original.delivery_date,
            recipient_name=original.recipient_name,
            recipient_street=original.recipient_street,
            recipient_postal_code=original.recipient_postal_code,
            recipient_city=original.recipient_city,
            total_brutto=original.total_brutto,
            status=InvoiceStatus.DRAFT,
            related_invoice_id=original.id,
        )
        s.add(new_inv)
        s.commit()
        s.refresh(new_inv)

        old_items = s.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == original.id)).all()
        for it in old_items:
            s.add(InvoiceItem(
                invoice_id=new_inv.id,
                description=it.description,
                quantity=it.quantity,
                unit_price=it.unit_price,
            ))

        log_audit_action(s, "INVOICE_RISK_EDIT", invoice_id=original.id)
        s.commit()

        return int(new_inv.id)


# -------------------------
# Invoice Detail
# -------------------------

def _status_step_current(invoice: Invoice) -> InvoiceStatus:
    s = invoice.status
    if s == InvoiceStatus.DRAFT:
        return InvoiceStatus.DRAFT
    if s in (InvoiceStatus.OPEN, InvoiceStatus.FINALIZED):
        return InvoiceStatus.OPEN
    if s == InvoiceStatus.SENT:
        return InvoiceStatus.SENT
    if s == InvoiceStatus.PAID:
        return InvoiceStatus.PAID
    if s == InvoiceStatus.CANCELLED:
        return InvoiceStatus.CANCELLED
    return InvoiceStatus.OPEN


def _render_status_stepper(invoice: Invoice) -> None:
    current = _status_step_current(invoice)
    steps = [
        (InvoiceStatus.DRAFT, "Entwurf"),
        (InvoiceStatus.OPEN, "Finalisiert"),
        (InvoiceStatus.SENT, "Gesendet"),
        (InvoiceStatus.PAID, "Bezahlt"),
        (InvoiceStatus.CANCELLED, "Storniert"),
    ]
    with ui.row().classes("items-center gap-2 flex-wrap"):
        for idx, (key, label) in enumerate(steps):
            is_active = key == current
            cls = STYLE_STEPPER_ACTIVE if is_active else STYLE_STEPPER_INACTIVE
            ui.label(label).classes(cls)
            if idx < len(steps) - 1:
                ui.label("→").classes(STYLE_STEPPER_ARROW)


__all__ = [name for name in globals() if not name.startswith("_")]
