import os
import csv
import zipfile
import shutil
from datetime import datetime
import requests
from nicegui import ui
from sqlmodel import Session, select
from data import Invoice, InvoiceItem, Company, Customer, InvoiceStatus, AuditLog, log_audit_action
from renderer import render_invoice_to_pdf_bytes
from invoice_numbering import build_invoice_filename, build_invoice_number

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
    customer = session.get(Customer, int(cust_id)) if cust_id else None
    invoice_nr = build_invoice_number(company, customer, company.next_invoice_nr, date_str)
    
    # 2. Create Invoice
    inv = Invoice(
        customer_id=cust_id,
        nr=invoice_nr,
        title=title,
        date=date_str,
        delivery_date=delivery_str,
        recipient_name=recipient_data.get('name'),
        recipient_street=recipient_data.get('street'),
        recipient_postal_code=recipient_data.get('zip'),
        recipient_city=recipient_data.get('city'),
        status=InvoiceStatus.OPEN
    )
    
    # 3. Calculate Totals
    _, brutto, tax_rate = calculate_totals(items, ust_enabled)
    inv.total_brutto = brutto

    # 4. Prepare PDF
    pdf_items = [i for i in items if i['desc']]
    inv.__dict__['line_items'] = pdf_items
    inv.__dict__['tax_rate'] = tax_rate
    pdf_bytes = render_invoice_to_pdf_bytes(inv)
    
    filename = build_invoice_filename(company, inv, customer)
    path = f"storage/invoices/{filename}"
    if os.path.exists(path):
        suffix = datetime.now().strftime("%Y%m%d%H%M%S%f")
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{suffix}{ext or '.pdf'}"
        path = f"storage/invoices/{filename}"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = f"{path}.tmp"
    with open(temp_path, "wb") as f:
        f.write(pdf_bytes)
    os.replace(temp_path, path)
        
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
    log_audit_action(session, "INVOICE_FINALIZED", invoice_id=inv.id)
    
    return inv

def _build_export_path(filename):
    base_dir = "storage/exports"
    os.makedirs(base_dir, exist_ok=True)
    path = os.path.join(base_dir, filename)
    if os.path.exists(path):
        suffix = datetime.now().strftime("%Y%m%d%H%M%S%f")
        name, ext = os.path.splitext(filename)
        path = os.path.join(base_dir, f"{name}_{suffix}{ext}")
    return path

def _write_csv(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)

def _create_zip(path, entries):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path, arcname in entries:
            if file_path and os.path.exists(file_path):
                zf.write(file_path, arcname=arcname or os.path.basename(file_path))

def _ensure_invoice_pdf_path(session, invoice):
    pdf_path = invoice.pdf_filename
    if pdf_path:
        if not os.path.isabs(pdf_path) and not pdf_path.startswith("storage/"):
            pdf_path = f"storage/invoices/{pdf_path}"
        if os.path.exists(pdf_path):
            return pdf_path
    customer = session.get(Customer, int(invoice.customer_id)) if invoice.customer_id else None
    company = session.exec(select(Company)).first() or Company()
    pdf_bytes = render_invoice_to_pdf_bytes(invoice)
    if isinstance(pdf_bytes, bytearray): pdf_bytes = bytes(pdf_bytes)
    if not isinstance(pdf_bytes, bytes): raise TypeError("PDF output must be bytes")
    filename = build_invoice_filename(company, invoice, customer) if invoice.nr else f"rechnung_{invoice.id}.pdf"
    pdf_path = f"storage/invoices/{filename}"
    if os.path.exists(pdf_path):
        suffix = datetime.now().strftime("%Y%m%d%H%M%S%f")
        if invoice.nr:
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{suffix}{ext or '.pdf'}"
        else:
            filename = f"rechnung_{invoice.id}_{suffix}.pdf"
        pdf_path = f"storage/invoices/{filename}"
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    temp_path = f"{pdf_path}.tmp"
    with open(temp_path, "wb") as f:
        f.write(pdf_bytes)
    os.replace(temp_path, pdf_path)
    invoice.pdf_filename = filename
    invoice.pdf_storage = "local"
    session.add(invoice)
    session.flush()
    return pdf_path

def _log_export_created(session):
    session.add(AuditLog(action="EXPORT_CREATED", timestamp=datetime.now().isoformat()))

def export_invoices_pdf_zip(session):
    invoices = session.exec(select(Invoice)).all()
    entries = []
    for inv in invoices:
        path = _ensure_invoice_pdf_path(session, inv)
        entries.append((path, os.path.basename(path)))
    zip_path = _build_export_path("rechnungen_pdf.zip")
    _create_zip(zip_path, entries)
    _log_export_created(session)
    session.commit()
    return zip_path

def export_invoices_csv(session):
    invoices = session.exec(select(Invoice)).all()
    headers = [
        "id", "nr", "titel", "datum", "lieferdatum",
        "kunde_id", "summe_brutto", "status"
    ]
    rows = [
        [
            inv.id, inv.nr, inv.title, inv.date, inv.delivery_date,
            inv.customer_id, f"{inv.total_brutto:.2f}", inv.status
        ]
        for inv in invoices
    ]
    csv_path = _build_export_path("rechnungen.csv")
    _write_csv(csv_path, headers, rows)
    _log_export_created(session)
    session.commit()
    return csv_path

def export_invoice_items_csv(session):
    items = session.exec(select(InvoiceItem)).all()
    headers = ["id", "rechnung_id", "beschreibung", "menge", "preis"]
    rows = [
        [item.id, item.invoice_id, item.description, item.quantity, item.unit_price]
        for item in items
    ]
    csv_path = _build_export_path("positionen.csv")
    _write_csv(csv_path, headers, rows)
    _log_export_created(session)
    session.commit()
    return csv_path

def export_customers_csv(session):
    customers = session.exec(select(Customer)).all()
    headers = [
        "id", "kdnr", "name", "vorname", "nachname", "email",
        "strasse", "plz", "ort", "ust_id"
    ]
    rows = [
        [
            c.id, c.kdnr, c.name, c.vorname, c.nachname, c.email,
            c.strasse, c.plz, c.ort, c.vat_id
        ]
        for c in customers
    ]
    csv_path = _build_export_path("kunden.csv")
    _write_csv(csv_path, headers, rows)
    _log_export_created(session)
    session.commit()
    return csv_path

def export_database_backup(session):
    db_path = "storage/database.db"
    backup_path = _build_export_path("database_backup.db")
    if os.path.exists(db_path):
        shutil.copy2(db_path, backup_path)
    else:
        with open(backup_path, "wb") as f:
            f.write(b"")
    _log_export_created(session)
    session.commit()
    return backup_path
