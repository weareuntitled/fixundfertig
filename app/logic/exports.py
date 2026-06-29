from __future__ import annotations

import io
import json
import mimetypes
import os
import zipfile
from datetime import datetime
from types import SimpleNamespace
from typing import Any, List, Optional

from sqlmodel import select

from data import Company, Customer, Document, InvoiceItem
from renderer import render_invoice_to_pdf_bytes
from services.blob_storage import blob_storage
from services.documents import resolve_document_path

from .utils import csv_bytes, invoices_dir, project_root, safe_filename, parse_export_args
from .invoice import select_invoices_for_company


def export_invoices_pdf_zip(*args: Any, **kwargs: Any) -> bytes:
    session, company_id, invoice_ids = parse_export_args(args, kwargs)

    comp = session.get(Company, int(company_id))
    if not comp:
        raise ValueError("Company nicht gefunden")

    invoices = select_invoices_for_company(session, int(company_id), invoice_ids)
    inv_dir = invoices_dir()
    root = project_root()

    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for inv in invoices:
            pdf: Optional[bytes] = getattr(inv, "pdf_bytes", None)

            if not pdf:
                fn = (getattr(inv, "pdf_filename", "") or "").strip()
                if fn:
                    p = fn if os.path.isabs(fn) else (
                        os.path.join(root, p) if fn.startswith("storage") else os.path.join(inv_dir, fn)
                    )
                    if os.path.exists(p):
                        try:
                            with open(p, "rb") as f:
                                pdf = f.read()
                        except Exception:
                            pdf = None

            if not pdf:
                cust = session.get(Customer, int(inv.customer_id)) if inv.customer_id else None
                if not cust:
                    continue
                its = list(session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == inv.id)).all())
                line_items = [
                    {"description": it.description, "quantity": float(it.quantity or 0),
                     "unit_price": float(it.unit_price or 0), "tax_rate": 0.0}
                    for it in its
                ]
                preview = SimpleNamespace(
                    company=comp, customer=cust, title=inv.title or "Rechnung",
                    invoice_number=inv.nr or f"INV-{inv.id}", date=inv.date or "",
                    delivery_date=inv.delivery_date or "", payment_terms="",
                    address_name=inv.recipient_name or getattr(cust, "display_name", "") or "",
                    address_street=inv.recipient_street or getattr(cust, "strasse", "") or "",
                    address_zip=inv.recipient_postal_code or getattr(cust, "plz", "") or "",
                    address_city=inv.recipient_city or getattr(cust, "ort", "") or "",
                    address_country=getattr(cust, "country", "") or "", ust_enabled=False,
                )
                preview.__dict__["intro_text"] = ""
                preview.__dict__["line_items"] = line_items
                pdf = render_invoice_to_pdf_bytes(preview)

            inv_no = str(getattr(inv, "nr", "") or f"INV-{getattr(inv, 'id', '')}")
            fname = safe_filename(f"{inv_no} {getattr(inv, 'title', 'Rechnung')}.pdf")
            zf.writestr(fname, pdf)

    mem.seek(0)
    return mem.read()


def export_documents_zip(*args: Any, **kwargs: Any) -> bytes:
    session, company_id, document_ids = parse_export_args(args, kwargs)

    def _display_date(doc: Document) -> str:
        for attr in ("doc_date", "invoice_date"):
            val = (getattr(doc, attr, None) or "").strip()
            if val:
                return val
        ts = getattr(doc, "created_at", None)
        return ts.strftime("%Y-%m-%d") if isinstance(ts, datetime) else ""

    def _parse_keywords(value: object) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(i).strip() for i in value if str(i).strip()]
        s = str(value)
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            parsed = s
        if isinstance(parsed, list):
            return [str(i).strip() for i in parsed if str(i).strip()]
        if isinstance(parsed, str):
            return [p.strip() for p in parsed.split(",") if p.strip()]
        return [str(parsed).strip()] if str(parsed).strip() else []

    def _resolve_amounts(doc: Document):
        total = doc.amount_total if doc.amount_total is not None else doc.gross_amount
        net = doc.amount_net if doc.amount_net is not None else doc.net_amount
        tax = doc.amount_tax if doc.amount_tax is not None else doc.tax_amount
        if tax is None and total is not None and net is None:
            rate = 0.19
            tax = float(total) * (rate / (1 + rate)) if float(total) > 0 else 0.0
        return total, net, tax

    stmt = select(Document).where(Document.company_id == int(company_id)).order_by(Document.id.desc())
    if document_ids:
        stmt = stmt.where(Document.id.in_([int(x) for x in document_ids]))
    documents = list(session.exec(stmt).all())

    storage = blob_storage()
    rows: List[List[Any]] = []
    files: List[tuple[int, str, bytes]] = []

    for doc in documents:
        filename = doc.original_filename or doc.filename or doc.title or f"dokument_{doc.id}"
        safe_name = safe_filename(filename)
        mime_type = doc.mime_type or doc.mime or mimetypes.guess_type(filename)[0] or ""
        total, net, tax = _resolve_amounts(doc)
        size = doc.size_bytes or doc.size or 0

        storage_key = getattr(doc, "storage_key", "") or ""
        storage_path = resolve_document_path(doc.storage_path)
        data = b""
        if storage_key and storage_key.startswith(("companies/", "documents/")):
            if storage.exists(storage_key):
                data = storage.get_bytes(storage_key)
        elif storage_path and os.path.exists(storage_path):
            try:
                with open(storage_path, "rb") as f:
                    data = f.read()
            except OSError:
                data = b""

        if data and not size:
            size = len(data)

        kw = _parse_keywords(doc.keywords_json)
        rows.append([
            filename, _display_date(doc), size or "", mime_type,
            doc.doc_number or "", doc.vendor or "", ", ".join(kw) if kw else "-",
            f"{total:.2f}" if total is not None else "",
            f"{net:.2f}" if net is not None else "",
            f"{tax:.2f}" if tax is not None else "",
            doc.description or doc.title or doc.doc_type or "",
        ])
        if data:
            files.append((int(doc.id or 0), safe_name, data))

    date_stamp = datetime.now().strftime("%Y%m%d")
    csv_data = csv_bytes(rows, [
        "Datei", "Datum", "Dateigröße (Bytes)", "MIME", "Belegnummer",
        "Vendor", "Tags", "Betrag", "Netto", "Steuer", "Summary",
    ])

    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"documents_{date_stamp}.csv", csv_data)
        for doc_id, safe_name, data in files:
            zf.writestr(f"{doc_id}_{safe_name}", data)
    mem.seek(0)
    return mem.read()


def export_invoices_csv(*args: Any, **kwargs: Any) -> bytes:
    session, company_id, invoice_ids = parse_export_args(args, kwargs)
    invoices = select_invoices_for_company(session, int(company_id), invoice_ids)

    rows: List[List[Any]] = []
    for inv in invoices:
        cust = session.get(Customer, int(inv.customer_id)) if inv.customer_id else None
        cust_name = (getattr(cust, "display_name", None) or getattr(cust, "name", "") or "").strip() if cust else ""
        rows.append([
            int(inv.id or 0), inv.nr or "", inv.title or "", inv.date or "",
            inv.delivery_date or "", int(inv.customer_id or 0), cust_name,
            inv.status.value if hasattr(inv.status, "value") else str(inv.status),
            float(getattr(inv, "total_brutto", 0) or 0),
        ])

    return csv_bytes(rows, [
        "id", "nr", "title", "date", "delivery_date",
        "customer_id", "customer_name", "status", "total_brutto",
    ])


def export_invoice_items_csv(*args: Any, **kwargs: Any) -> bytes:
    session, company_id, invoice_ids = parse_export_args(args, kwargs)
    invoices = select_invoices_for_company(session, int(company_id), invoice_ids)
    inv_by_id = {int(i.id): i for i in invoices if i and i.id}

    if not inv_by_id:
        return csv_bytes([], ["invoice_id", "invoice_nr", "item_id", "description", "quantity", "unit_price"])

    stmt = select(InvoiceItem).where(InvoiceItem.invoice_id.in_(list(inv_by_id.keys()))).order_by(InvoiceItem.invoice_id, InvoiceItem.id)
    items = list(session.exec(stmt).all())

    rows: List[List[Any]] = []
    for it in items:
        inv = inv_by_id.get(int(it.invoice_id))
        rows.append([
            int(it.invoice_id or 0), getattr(inv, "nr", "") if inv else "",
            int(it.id or 0), it.description or "",
            float(it.quantity or 0), float(it.unit_price or 0),
        ])

    return csv_bytes(rows, ["invoice_id", "invoice_nr", "item_id", "description", "quantity", "unit_price"])


def export_customers_csv(*args: Any, **kwargs: Any) -> bytes:
    session, company_id, _ = parse_export_args(args, kwargs, needs_ids=False)
    stmt = select(Customer).where(Customer.company_id == int(company_id)).order_by(Customer.id)
    customers = list(session.exec(stmt).all())

    rows: List[List[Any]] = []
    for c in customers:
        rows.append([
            int(c.id or 0), int(getattr(c, "kdnr", 0) or 0),
            getattr(c, "name", "") or "", getattr(c, "vorname", "") or "",
            getattr(c, "nachname", "") or "", getattr(c, "email", "") or "",
            getattr(c, "strasse", "") or "", getattr(c, "plz", "") or "",
            getattr(c, "ort", "") or "", getattr(c, "country", "") or "",
            getattr(c, "vat_id", "") or "", getattr(c, "short_code", "") or "",
            int(getattr(c, "archived", 0) or 0),
        ])

    return csv_bytes(rows, [
        "id", "kdnr", "name", "vorname", "nachname", "email",
        "strasse", "plz", "ort", "country", "vat_id", "short_code", "archived",
    ])


def export_database_backup(*args: Any, **kwargs: Any) -> bytes:
    from .utils import storage_dir, invoices_dir, project_root
    stor = storage_dir()
    db_path = os.path.join(stor, "database.db")
    inv_dir = invoices_dir()
    root = project_root()

    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(db_path):
            zf.write(db_path, arcname=os.path.join("storage", "database.db"))
        if os.path.isdir(inv_dir):
            for dirpath, _, filenames in os.walk(inv_dir):
                for fn in filenames:
                    full = os.path.join(dirpath, fn)
                    zf.write(full, arcname=os.path.relpath(full, root))
    mem.seek(0)
    return mem.read()
