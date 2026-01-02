from datetime import datetime
from sqlmodel import Session, select

from data import Invoice, InvoiceItem, engine

def create_correction(original_invoice_id, use_negative_items=True):
    with Session(engine) as session:
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
            status='Entwurf',
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
