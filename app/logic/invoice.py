from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from data import Company, Customer, Invoice, InvoiceItem, InvoiceStatus
from invoice_numbering import build_invoice_filename
from renderer import render_invoice_to_pdf_bytes


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
    comp.next_invoice_nr = seq + 1
    return (nr or str(seq)).strip()


def _invoice_number_exists(session: Session, company_id: int, nr: str) -> bool:
    stmt = (
        select(Invoice.id)
        .join(Customer, Invoice.customer_id == Customer.id)
        .where(Customer.company_id == int(company_id), Invoice.nr == str(nr))
        .limit(1)
    )
    return session.exec(stmt).first() is not None


def _next_unique_invoice_number(session: Session, comp: Company) -> str:
    if not comp.id:
        return _build_invoice_number(comp)
    seen: set[str] = set()
    for _ in range(1000):
        candidate = _build_invoice_number(comp)
        if candidate in seen:
            candidate = str(max(int(getattr(comp, "next_invoice_nr", 1) or 1) - 1, 1))
        seen.add(candidate)
        if not _invoice_number_exists(session, int(comp.id), candidate):
            return candidate
    raise ValueError("Konnte keine eindeutige Rechnungsnummer erzeugen")


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
    status: InvoiceStatus = InvoiceStatus.OPEN,
    subject: str = "",
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
        clean_items.append({
            "description": desc,
            "quantity": float(it.get("quantity", 0) or 0),
            "unit_price": float(it.get("unit_price", 0) or 0),
            "tax_rate": float(it.get("tax_rate", 0) or 0),
        })
    if not clean_items:
        raise ValueError("Keine Positionen")

    nr = _next_unique_invoice_number(session, comp)
    session.add(comp)
    period = _period_from_inputs(delivery_str, service_from, service_to)

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
        company_id=int(comp.id),
        nr=str(nr),
        title=(title or "Rechnung").strip() or "Rechnung",
        subject=(subject or "").strip(),
        date=(date_str or "").strip(),
        delivery_date=(period or "").strip(),
        recipient_name=rec_name,
        recipient_street=rec_street,
        recipient_postal_code=rec_zip,
        recipient_city=rec_city,
        total_brutto=float(gross),
        status=status,
        pdf_storage="db",
    )

    preview = SimpleNamespace(
        company=comp, customer=cust, title=inv.title,
        invoice_number=inv.nr, date=inv.date, delivery_date=inv.delivery_date,
        payment_terms="", address_name=inv.recipient_name,
        address_street=inv.recipient_street, address_zip=inv.recipient_postal_code,
        address_city=inv.recipient_city,
        address_country=getattr(cust, "country", "") or "",
        ust_enabled=(not is_small) and bool(ust_enabled),
    )
    preview.__dict__["intro_text"] = (intro_text or "").strip()
    preview.__dict__["line_items"] = clean_items
    preview.__dict__["totals"] = {"gross": gross}

    inv.pdf_bytes = render_invoice_to_pdf_bytes(preview)
    inv.pdf_filename = build_invoice_filename(comp, inv, cust)

    session.add(inv)
    session.flush()

    for it in clean_items:
        session.add(InvoiceItem(
            invoice_id=int(inv.id),
            description=str(it["description"]),
            quantity=float(it["quantity"]),
            unit_price=float(it["unit_price"]),
        ))

    session.commit()
    return int(inv.id)


def select_invoices_for_company(session: Session, company_id: int, invoice_ids: Optional[List[int]] = None) -> List[Invoice]:
    stmt = (
        select(Invoice)
        .join(Customer, Invoice.customer_id == Customer.id)
        .where(Customer.company_id == int(company_id))
        .order_by(Invoice.id.desc())
    )
    if invoice_ids:
        stmt = stmt.where(Invoice.id.in_([int(x) for x in invoice_ids]))
    return list(session.exec(stmt).all())
