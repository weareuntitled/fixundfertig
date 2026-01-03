import os
from datetime import datetime
from sqlmodel import Session, select
from data import Invoice, InvoiceItem, Company, InvoiceStatus, AuditLog
from renderer import render_invoice_to_pdf_bytes

def calculate_totals(items, ust_enabled):
    netto = 0.0
    for i in items:
        qty = float(i.get('qty') or 0)
        price = float(i.get('price') or 0)
        is_brutto = i.get('is_brutto', False)
        
        unit_net = price
        if ust_enabled and is_brutto:
            unit_net = price / 1.19
            
        netto += qty * unit_net
    
    tax_rate = 0.19 if ust_enabled else 0.0
    brutto = netto * (1 + tax_rate)
    return netto, brutto, tax_rate

def finalize_invoice_logic(session, comp_id, cust_id, title, date_str, delivery_str, recipient_data, items, ust_enabled):
    # 1. Lock Company & Get Number
    company = session.exec(select(Company).where(Company.id == comp_id).with_for_update()).first()
    
    # 2. Create Invoice
    inv = Invoice(
        customer_id=cust_id,
        nr=company.next_invoice_nr,
        title=title,
        date=date_str,
        delivery_date=delivery_str,
        recipient_name=recipient_data.get('name'),
        recipient_street=recipient_data.get('street'),
        recipient_postal_code=recipient_data.get('zip'),
        recipient_city=recipient_data.get('city'),
        status=InvoiceStatus.FINALIZED
    )
    
    # 3. Calculate Totals
    _, brutto, tax_rate = calculate_totals(items, ust_enabled)
    inv.total_brutto = brutto

    # 4. Prepare PDF
    pdf_items = [i for i in items if i['desc']]
    inv.__dict__['line_items'] = pdf_items
    inv.__dict__['tax_rate'] = tax_rate
    pdf_bytes = render_invoice_to_pdf_bytes(inv)
    
    filename = f"rechnung_{inv.nr}.pdf"
    path = f"storage/invoices/{filename}"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(pdf_bytes)
        
    inv.pdf_filename = filename
    inv.pdf_storage = "local"
    inv.pdf_bytes = pdf_bytes

    session.add(inv)
    session.flush() # Get ID

    # 5. Save Items
    for i in pdf_items:
        qty = float(i['qty'])
        price = float(i['price'])
        session.add(InvoiceItem(
            invoice_id=inv.id,
            description=i['desc'],
            quantity=qty,
            unit_price=price
        ))

    # 6. Increment Number & Audit
    company.next_invoice_nr += 1
    session.add(company)
    session.add(AuditLog(action="FINALIZED", invoice_id=inv.id, timestamp=datetime.now().isoformat()))
    
    return inv
