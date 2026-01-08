from datetime import datetime
from sqlmodel import select

from data import Invoice, InvoiceItem, InvoiceStatus, get_session, log_audit_action

STATUS_AUDIT_ACTIONS = {
    InvoiceStatus.SENT: "INVOICE_SENT",
    InvoiceStatus.PAID: "INVOICE_PAID",
    InvoiceStatus.OPEN: "INVOICE_OPEN",
    InvoiceStatus.FINALIZED: "INVOICE_FINALIZED",
    InvoiceStatus.CANCELLED: "INVOICE_CANCELLED",
}

def update_status_logic(session, invoice_id, target_status):
    invoice = session.get(Invoice, int(invoice_id))
    if not invoice:
        return None, "Rechnung nicht gefunden"
    if invoice.status == InvoiceStatus.DRAFT:
        return None, "Entwürfe können nicht aktualisiert werden"
    if invoice.status == InvoiceStatus.CANCELLED:
        return None, "Rechnung ist bereits storniert"
    if invoice.status == target_status:
        return None, "Status ist bereits gesetzt"
    if target_status not in STATUS_AUDIT_ACTIONS:
        return None, "Ungültiger Zielstatus"

    invoice.status = target_status
    invoice.updated_at = datetime.now().isoformat()
    session.add(invoice)
    log_audit_action(session, STATUS_AUDIT_ACTIONS[target_status], invoice_id=invoice.id)
    return invoice, ""

def create_correction(original_invoice_id, use_negative_items=True):
    with get_session() as session:
        original = session.get(Invoice, int(original_invoice_id))
        if not original:
            return None, "Rechnung nicht gefunden"

        items = session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == original.id)).all()
        reference_text = f"Bezug: Rechnung Nr. {original.nr} vom {original.date}"

        correction = Invoice(
            customer_id=original.customer_id,
            nr=None,
            date=datetime.now().strftime('%Y-%m-%d'),
            total_brutto=-float(original.total_brutto or 0),
            status=InvoiceStatus.DRAFT,
            related_invoice_id=original.id
        )
        session.add(correction)
        session.commit()
        session.refresh(correction)

        total_items = 0.0
        for item in items:
            total_items += float(item.quantity or 0) * float(item.unit_price or 0)

        for item in items:
            desc = f"Korrektur - {item.description}"
            desc = f"{desc} ({reference_text})"
            price = float(item.unit_price or 0)
            if use_negative_items:
                price = -abs(price)
            session.add(InvoiceItem(
                invoice_id=correction.id,
                description=desc,
                quantity=float(item.quantity or 0),
                unit_price=price
            ))

        if not use_negative_items:
            balance_desc = f"Korrektur - Ausgleichsposten ({reference_text})"
            balance_amount = -2 * total_items
            session.add(InvoiceItem(
                invoice_id=correction.id,
                description=balance_desc,
                quantity=1,
                unit_price=balance_amount
            ))

        session.commit()

    return correction, ""

def delete_draft(invoice_id):
    with get_session() as session:
        inv = session.get(Invoice, int(invoice_id))
        if not inv:
            return False, "Rechnung nicht gefunden"
        if inv.status != InvoiceStatus.DRAFT:
            return False, "Nur Entwürfe können gelöscht werden"

        items = session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == inv.id)).all()
        for item in items:
            session.delete(item)
        session.delete(inv)
        session.commit()
    return True, ""

def cancel_invoice(invoice_id):
    with get_session() as session:
        inv = session.get(Invoice, int(invoice_id))
        if not inv:
            return False, "Rechnung nicht gefunden"
        if inv.status == InvoiceStatus.CANCELLED:
            return False, "Rechnung ist bereits storniert"
        if inv.status == InvoiceStatus.DRAFT:
            return False, "Entwürfe dürfen nur gelöscht werden"

        inv.status = InvoiceStatus.CANCELLED
        session.add(inv)
        log_audit_action(session, "INVOICE_CANCELLED", invoice_id=inv.id)
        session.commit()
    return True, ""
