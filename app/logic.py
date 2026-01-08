from __future__ import annotations

import csv
import io
import os
import re
import zipfile
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from data import Company, Customer, Invoice, InvoiceItem, InvoiceStatus
from renderer import render_invoice_to_pdf_bytes


def _safe_filename(name: str) -> str:
    name = (name or "").strip() or "export"
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"[^a-zA-Z0-9äöüÄÖÜß _\.\(\)\[\]\-]+", "_", name)
    name = name.replace("/", "_").replace("\\", "_").replace(":", "_")
    return name[:120] if len(name) > 120 else name


def _project_root() -> str:
    # logic.py liegt in /app, root ist eine Ebene höher
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _storage_dir() -> str:
    return os.path.join(_project_root(), "storage")


def _invoices_dir() -> str:
    return os.path.join(_storage_dir(), "invoices")


def _build_invoice_number(comp: Company) -> str:
    seq = int(getattr(comp, "next_invoice_nr", 10000) or 10000)
    tpl = (getattr(comp, "invoice_number_template", "{seq}") or "{seq}").strip()

    now = datetime.now()
    ctx = {
        "seq": seq,
        "year": now.strftime("%Y"),
        "month": now.strftime("%m"),
        "day": now.strftime("%d"),
        "ym": now.strftime("%Y%m"),
        "ymd": now.strftime("%Y%m%d"),
    }

    try:
        nr = tpl.format(**ctx)
    except Exception:
        nr = str(seq)

    # seq hochzählen
    comp.next_invoice_nr = seq + 1
    return (nr or str(seq)).strip()


def _period_from_inputs(delivery_str: str | None, service_from: str | None, service_to: str | None) -> str:
    d = (delivery_str or "").strip()
    if d:
        return d
    f = (service_from or "").strip()
    t = (service_to or "").strip()
    if f and (not t or t == f):
        return f
    if f and t and f != t:
        return f"{f} bis {t}"
    return t or ""


def _calc_gross(items: List[Dict[str, Any]], *, ust_enabled: bool, is_small_business: bool) -> float:
    net = 0.0
    tax = 0.0
    for it in items:
        qty = float(it.get("quantity", 0) or 0)
        unit = float(it.get("unit_price", 0) or 0)
        rate = float(it.get("tax_rate", 0) or 0)
        line = qty * unit
        net += line
        if (not is_small_business) and ust_enabled and rate > 0:
            tax += line * (rate / 100.0)
    return net + tax


def finalize_invoice_logic(
    session: Session,
    comp_id: int,
    cust_id: int,
    title: str,
    date_str: str,
    delivery_str: str,
    recipient_data: Dict[str, str],
    items: List[Dict[str, Any]],
    ust_enabled: bool,
    intro_text: str = "",
    service_from: Optional[str] = None,
    service_to: Optional[str] = None,
) -> int:
    comp = session.get(Company, int(comp_id))
    cust = session.get(Customer, int(cust_id))
    if not comp or not cust:
        raise ValueError("Company oder Customer nicht gefunden")

    clean_items: List[Dict[str, Any]] = []
    for it in (items or []):
        desc = str(it.get("description", "") or "").strip()
        if not desc:
            continue
        clean_items.append(
            {
                "description": desc,
                "quantity": float(it.get("quantity", 0) or 0),
                "unit_price": float(it.get("unit_price", 0) or 0),
                "tax_rate": float(it.get("tax_rate", 0) or 0),
            }
        )
    if not clean_items:
        raise ValueError("Keine Positionen")

    # Nummer + seq speichern
    nr = _build_invoice_number(comp)
    session.add(comp)

    # Leistungszeitraum
    period = _period_from_inputs(delivery_str, service_from, service_to)

    # Recipient mapping, akzeptiert beide Varianten (recipient_* oder address_*)
    rec_name = (recipient_data.get("recipient_name") or recipient_data.get("address_name") or "").strip()
    rec_street = (recipient_data.get("recipient_street") or recipient_data.get("address_street") or "").strip()
    rec_zip = (recipient_data.get("recipient_postal_code") or recipient_data.get("address_zip") or "").strip()
    rec_city = (recipient_data.get("recipient_city") or recipient_data.get("address_city") or "").strip()

    if not rec_name:
        rec_name = (getattr(cust, "display_name", None) or getattr(cust, "name", "") or "").strip()
    if not rec_street:
        rec_street = (getattr(cust, "recipient_street", "") or getattr(cust, "strasse", "") or "").strip()
    if not rec_zip:
        rec_zip = (getattr(cust, "recipient_postal_code", "") or getattr(cust, "plz", "") or "").strip()
    if not rec_city:
        rec_city = (getattr(cust, "recipient_city", "") or getattr(cust, "ort", "") or "").strip()

    is_small = bool(getattr(comp, "is_small_business", False))
    gross = _calc_gross(clean_items, ust_enabled=bool(ust_enabled), is_small_business=is_small)

    inv = Invoice(
        customer_id=int(cust.id),
        nr=str(nr),
        title=(title or "Rechnung").strip() or "Rechnung",
        date=(date_str or "").strip(),
        delivery_date=(period or "").strip(),
        recipient_name=rec_name,
        recipient_street=rec_street,
        recipient_postal_code=rec_zip,
        recipient_city=rec_city,
        total_brutto=float(gross),
        status=InvoiceStatus.OPEN,
    )

    # PDF direkt mit den Clean Items rendern, Intro Text ist nur im PDF
    preview = SimpleNamespace()
    preview.company = comp
    preview.customer = cust
    preview.title = inv.title
    preview.invoice_number = inv.nr
    preview.date = inv.date
    preview.delivery_date = inv.delivery_date
    preview.payment_terms = ""
    preview.address_name = inv.recipient_name
    preview.address_street = inv.recipient_street
    preview.address_zip = inv.recipient_postal_code
    preview.address_city = inv.recipient_city
    preview.address_country = getattr(cust, "country", "") or ""
    preview.ust_enabled = (not is_small) and bool(ust_enabled)
    preview.__dict__["intro_text"] = (intro_text or "").strip()
    preview.__dict__["line_items"] = clean_items
    preview.__dict__["totals"] = {"gross": gross}

    inv.pdf_bytes = render_invoice_to_pdf_bytes(preview)

    session.add(inv)
    session.flush()

    # Items speichern (DB Modell hat nur description, quantity, unit_price)
    for it in clean_items:
        session.add(
            InvoiceItem(
                invoice_id=int(inv.id),
                description=str(it["description"]),
                quantity=float(it["quantity"]),
                unit_price=float(it["unit_price"]),
            )
        )

    session.commit()
    return int(inv.id)


def _select_invoices_for_company(session: Session, company_id: int, invoice_ids: Optional[List[int]] = None) -> List[Invoice]:
    stmt = (
        select(Invoice)
        .join(Customer, Invoice.customer_id == Customer.id)
        .where(Customer.company_id == int(company_id))
        .order_by(Invoice.id.desc())
    )
    if invoice_ids:
        stmt = stmt.where(Invoice.id.in_([int(x) for x in invoice_ids]))
    return list(session.exec(stmt).all())


def export_invoices_pdf_zip(*args: Any, **kwargs: Any) -> bytes:
    """
    Robust für verschiedene Aufrufe:
      export_invoices_pdf_zip(session, company_id, invoice_ids=None)
      export_invoices_pdf_zip(session=session, company_id=..., invoice_ids=[...])
    """
    session: Optional[Session] = None
    company_id: Optional[int] = None
    invoice_ids: Optional[List[int]] = None

    if args:
        if isinstance(args[0], Session):
            session = args[0]
        if len(args) > 1 and isinstance(args[1], int):
            company_id = int(args[1])
        if len(args) > 2 and isinstance(args[2], list):
            invoice_ids = [int(x) for x in args[2]]

    session = session or kwargs.get("session")
    company_id = company_id or kwargs.get("company_id") or kwargs.get("comp_id")
    invoice_ids = invoice_ids or kwargs.get("invoice_ids") or kwargs.get("ids")

    if session is None:
        raise ValueError("export_invoices_pdf_zip: session fehlt")
    if company_id is None:
        raise ValueError("export_invoices_pdf_zip: company_id fehlt")

    comp = session.get(Company, int(company_id))
    if not comp:
        raise ValueError("Company nicht gefunden")

    invoices = _select_invoices_for_company(session, int(company_id), invoice_ids)

    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for inv in invoices:
            pdf: Optional[bytes] = getattr(inv, "pdf_bytes", None)

            # Fallback: lokale Datei
            if not pdf:
                fn = (getattr(inv, "pdf_filename", "") or "").strip()
                if fn:
                    p = fn
                    if not os.path.isabs(p):
                        if not p.startswith("storage"):
                            p = os.path.join(_invoices_dir(), p)
                        else:
                            p = os.path.join(_project_root(), p)
                    if os.path.exists(p):
                        try:
                            with open(p, "rb") as f:
                                pdf = f.read()
                        except Exception:
                            pdf = None

            # Fallback: neu rendern
            if not pdf:
                cust = session.get(Customer, int(inv.customer_id)) if inv.customer_id else None
                if not cust:
                    continue
                its = list(session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == inv.id)).all())
                line_items = [
                    {
                        "description": it.description,
                        "quantity": float(it.quantity or 0),
                        "unit_price": float(it.unit_price or 0),
                        "tax_rate": 0.0,
                    }
                    for it in its
                ]
                preview = SimpleNamespace()
                preview.company = comp
                preview.customer = cust
                preview.title = inv.title or "Rechnung"
                preview.invoice_number = inv.nr or f"INV-{inv.id}"
                preview.date = inv.date or ""
                preview.delivery_date = inv.delivery_date or ""
                preview.payment_terms = ""
                preview.address_name = inv.recipient_name or getattr(cust, "display_name", "") or getattr(cust, "name", "")
                preview.address_street = inv.recipient_street or getattr(cust, "strasse", "") or ""
                preview.address_zip = inv.recipient_postal_code or getattr(cust, "plz", "") or ""
                preview.address_city = inv.recipient_city or getattr(cust, "ort", "") or ""
                preview.address_country = getattr(cust, "country", "") or ""
                preview.ust_enabled = False
                preview.__dict__["intro_text"] = ""
                preview.__dict__["line_items"] = line_items
                pdf = render_invoice_to_pdf_bytes(preview)

            inv_no = str(getattr(inv, "nr", "") or f"INV-{getattr(inv, 'id', '')}")
            title = str(getattr(inv, "title", "") or "Rechnung")
            fname = _safe_filename(f"{inv_no} {title}.pdf")
            zf.writestr(fname, pdf)

    mem.seek(0)
    return mem.read()


def _csv_bytes(rows: List[List[Any]], header: List[str]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(header)
    for r in rows:
        writer.writerow([("" if v is None else v) for v in r])
    # Excel freundlich
    return buf.getvalue().encode("utf-8-sig")


def export_invoices_csv(*args: Any, **kwargs: Any) -> bytes:
    """
    export_invoices_csv(session, company_id, invoice_ids=None)
    """
    session: Optional[Session] = None
    company_id: Optional[int] = None
    invoice_ids: Optional[List[int]] = None

    if args:
        if isinstance(args[0], Session):
            session = args[0]
        if len(args) > 1 and isinstance(args[1], int):
            company_id = int(args[1])
        if len(args) > 2 and isinstance(args[2], list):
            invoice_ids = [int(x) for x in args[2]]

    session = session or kwargs.get("session")
    company_id = company_id or kwargs.get("company_id") or kwargs.get("comp_id")
    invoice_ids = invoice_ids or kwargs.get("invoice_ids") or kwargs.get("ids")

    if session is None:
        raise ValueError("export_invoices_csv: session fehlt")
    if company_id is None:
        raise ValueError("export_invoices_csv: company_id fehlt")

    invoices = _select_invoices_for_company(session, int(company_id), invoice_ids)

    rows: List[List[Any]] = []
    for inv in invoices:
        cust = session.get(Customer, int(inv.customer_id)) if inv.customer_id else None
        cust_name = ""
        if cust:
            cust_name = (getattr(cust, "display_name", None) or getattr(cust, "name", "") or "").strip()
        rows.append(
            [
                int(inv.id or 0),
                (inv.nr or ""),
                (inv.title or ""),
                (inv.date or ""),
                (inv.delivery_date or ""),
                int(inv.customer_id or 0),
                cust_name,
                (inv.status.value if hasattr(inv.status, "value") else str(inv.status)),
                float(getattr(inv, "total_brutto", 0) or 0),
            ]
        )

    header = [
        "id",
        "nr",
        "title",
        "date",
        "delivery_date",
        "customer_id",
        "customer_name",
        "status",
        "total_brutto",
    ]
    return _csv_bytes(rows, header)


def export_invoice_items_csv(*args: Any, **kwargs: Any) -> bytes:
    """
    export_invoice_items_csv(session, company_id, invoice_ids=None)
    """
    session: Optional[Session] = None
    company_id: Optional[int] = None
    invoice_ids: Optional[List[int]] = None

    if args:
        if isinstance(args[0], Session):
            session = args[0]
        if len(args) > 1 and isinstance(args[1], int):
            company_id = int(args[1])
        if len(args) > 2 and isinstance(args[2], list):
            invoice_ids = [int(x) for x in args[2]]

    session = session or kwargs.get("session")
    company_id = company_id or kwargs.get("company_id") or kwargs.get("comp_id")
    invoice_ids = invoice_ids or kwargs.get("invoice_ids") or kwargs.get("ids")

    if session is None:
        raise ValueError("export_invoice_items_csv: session fehlt")
    if company_id is None:
        raise ValueError("export_invoice_items_csv: company_id fehlt")

    invoices = _select_invoices_for_company(session, int(company_id), invoice_ids)
    inv_by_id = {int(i.id): i for i in invoices if i and i.id}

    if not inv_by_id:
        return _csv_bytes([], ["invoice_id", "invoice_nr", "item_id", "description", "quantity", "unit_price"])

    stmt = select(InvoiceItem).where(InvoiceItem.invoice_id.in_(list(inv_by_id.keys()))).order_by(InvoiceItem.invoice_id, InvoiceItem.id)
    items = list(session.exec(stmt).all())

    rows: List[List[Any]] = []
    for it in items:
        inv = inv_by_id.get(int(it.invoice_id))
        rows.append(
            [
                int(it.invoice_id or 0),
                (getattr(inv, "nr", "") if inv else ""),
                int(it.id or 0),
                (it.description or ""),
                float(it.quantity or 0),
                float(it.unit_price or 0),
            ]
        )

    header = ["invoice_id", "invoice_nr", "item_id", "description", "quantity", "unit_price"]
    return _csv_bytes(rows, header)


def export_customers_csv(*args: Any, **kwargs: Any) -> bytes:
    """
    export_customers_csv(session, company_id)
    """
    session: Optional[Session] = None
    company_id: Optional[int] = None

    if args:
        if isinstance(args[0], Session):
            session = args[0]
        if len(args) > 1 and isinstance(args[1], int):
            company_id = int(args[1])

    session = session or kwargs.get("session")
    company_id = company_id or kwargs.get("company_id") or kwargs.get("comp_id")

    if session is None:
        raise ValueError("export_customers_csv: session fehlt")
    if company_id is None:
        raise ValueError("export_customers_csv: company_id fehlt")

    stmt = select(Customer).where(Customer.company_id == int(company_id)).order_by(Customer.id)
    customers = list(session.exec(stmt).all())

    rows: List[List[Any]] = []
    for c in customers:
        rows.append(
            [
                int(c.id or 0),
                int(getattr(c, "kdnr", 0) or 0),
                getattr(c, "name", "") or "",
                getattr(c, "vorname", "") or "",
                getattr(c, "nachname", "") or "",
                getattr(c, "email", "") or "",
                getattr(c, "strasse", "") or "",
                getattr(c, "plz", "") or "",
                getattr(c, "ort", "") or "",
                getattr(c, "country", "") or "",
                getattr(c, "vat_id", "") or "",
                getattr(c, "short_code", "") or "",
                int(getattr(c, "archived", 0) or 0),
            ]
        )

    header = [
        "id",
        "kdnr",
        "name",
        "vorname",
        "nachname",
        "email",
        "strasse",
        "plz",
        "ort",
        "country",
        "vat_id",
        "short_code",
        "archived",
    ]
    return _csv_bytes(rows, header)


def export_database_backup(*args: Any, **kwargs: Any) -> bytes:
    """
    export_database_backup() -> zip bytes
    Nimmt optional company_id oder session, ist aber nicht nötig.
    Sichert:
      - storage/database.db
      - storage/invoices/*
    """
    storage = _storage_dir()
    db_path = os.path.join(storage, "database.db")
    inv_dir = _invoices_dir()

    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(db_path):
            zf.write(db_path, arcname=os.path.join("storage", "database.db"))

        if os.path.isdir(inv_dir):
            for root, _, files in os.walk(inv_dir):
                for fn in files:
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, _project_root())
                    zf.write(full, arcname=rel)

    mem.seek(0)
    return mem.read()
