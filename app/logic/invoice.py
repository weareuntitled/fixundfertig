from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from data import Company, Customer, DocumentType, Invoice, InvoiceItem, InvoiceStatus
from invoice_numbering import build_invoice_filename
from renderer import render_invoice_to_pdf_bytes
from services.payment_plan import dump_payment_plan


def _build_invoice_number(comp: Company, document_type: DocumentType = DocumentType.INVOICE) -> str:
    """Nächste Nummer nach dem Rechnungsmuster der Firma.

    Angebote zählen mit `next_quote_nr` und tragen `quote_prefix` (Vorgabe "A-")
    vor dem Muster; der Rechnungszähler bleibt dabei unberührt.
    """
    is_quote = document_type == DocumentType.QUOTE
    counter = "next_quote_nr" if is_quote else "next_invoice_nr"
    seq = int(getattr(comp, counter, 10000) or 10000)
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
    setattr(comp, counter, seq + 1)
    nr = (nr or str(seq)).strip()
    if is_quote:
        prefix = getattr(comp, "quote_prefix", "A-")
        nr = f"{'A-' if prefix is None else prefix}{nr}"
    return nr


def _invoice_number_exists(
    session: Session, company_id: int, nr: str, document_type: DocumentType = DocumentType.INVOICE
) -> bool:
    stmt = (
        select(Invoice.id)
        .join(Customer, Invoice.customer_id == Customer.id)
        .where(
            Customer.company_id == int(company_id),
            Invoice.nr == str(nr),
            Invoice.document_type == document_type,
        )
        .limit(1)
    )
    return session.exec(stmt).first() is not None


def _next_unique_invoice_number(
    session: Session, comp: Company, document_type: DocumentType = DocumentType.INVOICE
) -> str:
    if not comp.id:
        return _build_invoice_number(comp, document_type)
    seen: set[str] = set()
    for _ in range(1000):
        candidate = _build_invoice_number(comp, document_type)
        if candidate in seen and document_type == DocumentType.INVOICE:
            candidate = str(max(int(getattr(comp, "next_invoice_nr", 1) or 1) - 1, 1))
        seen.add(candidate)
        if not _invoice_number_exists(session, int(comp.id), candidate, document_type):
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


def document_vat_rate(invoice: Invoice) -> float:
    """VAT rate in percent the document charges.

    Stored on new documents; legacy rows carry only their gross total, so the rate
    is derived from gross vs. net of the current positions (rounded to 0.1 %).
    """
    stored = getattr(invoice, "vat_rate", None)
    if stored is not None:
        return float(stored)
    net = sum(float(it.quantity or 0) * float(it.unit_price or 0) for it in (invoice.items or []))
    gross = float(invoice.total_brutto or 0)
    if net > 0 and gross > net + 0.005:
        return round((gross - net) / net * 100, 1)
    return 0.0


def recompute_total_brutto(invoice: Invoice, vat_rate: float, session: Optional[Session] = None) -> None:
    """Payable total from the current positions at the document's VAT rate.

    A final invoice (#491) keeps the rate stored but its payable amount is the
    rest after the quote's billed down payments. Without a session the deductions
    cannot be read, so it falls back to the plain gross total.
    """
    from .final_invoice import billed_down_payments, final_invoice_totals

    net = sum(float(it.quantity or 0) * float(it.unit_price or 0) for it in (invoice.items or []))
    invoice.vat_rate = float(vat_rate)
    if bool(getattr(invoice, "is_final_invoice", False)) and getattr(invoice, "quote_id", None) and session is not None:
        rows = billed_down_payments(session, int(invoice.quote_id))
        invoice.total_brutto = final_invoice_totals(net, float(vat_rate), rows)["rest"]
        return
    invoice.total_brutto = round(net * (1 + float(vat_rate) / 100.0), 2)


QUOTE_VALIDITY_DAYS = 30


def default_quote_valid_until(date_str: str | None) -> str:
    """Vorgabe für „gültig bis“: Angebotsdatum (sonst heute) plus 30 Tage."""
    try:
        base = date.fromisoformat((date_str or "").strip())
    except ValueError:
        base = date.today()
    return (base + timedelta(days=QUOTE_VALIDITY_DAYS)).isoformat()


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
    document_type: DocumentType = DocumentType.INVOICE,
    valid_until: str = "",
    payment_plan: Optional[List[Any]] = None,
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

    is_quote = document_type == DocumentType.QUOTE
    if is_quote:
        status = InvoiceStatus.DRAFT
        if not (title or "").strip() or (title or "").strip() == "Rechnung":
            title = "Angebot"
        valid_until = (valid_until or "").strip() or default_quote_valid_until(date_str)
        plan_json = dump_payment_plan(payment_plan)
    else:
        valid_until = ""
        plan_json = "[]"  # invoices have no payment plan
    nr = _next_unique_invoice_number(session, comp, document_type)
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
    charges_vat = (not is_small) and bool(ust_enabled)
    vat_rate = float(clean_items[0].get("tax_rate", 0) or 0) if charges_vat else 0.0

    inv = Invoice(
        customer_id=int(cust.id),
        company_id=int(comp.id),
        nr=str(nr),
        document_type=document_type,
        valid_until=valid_until,
        payment_plan=plan_json,
        intro_text=(intro_text or "").strip(),
        title=(title or "Rechnung").strip() or "Rechnung",
        subject=(subject or "").strip(),
        date=(date_str or "").strip(),
        delivery_date=(period or "").strip(),
        recipient_name=rec_name,
        recipient_street=rec_street,
        recipient_postal_code=rec_zip,
        recipient_city=rec_city,
        total_brutto=float(gross),
        vat_rate=vat_rate,
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
        document_type=inv.document_type, valid_until=inv.valid_until,
        payment_plan=inv.payment_plan,
    )
    preview.__dict__["intro_text"] = (intro_text or "").strip()
    preview.__dict__["line_items"] = clean_items
    preview.__dict__["totals"] = {"gross": gross}
    preview.__dict__["total_brutto"] = gross

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
        .where(Customer.company_id == int(company_id), Invoice.document_type == DocumentType.INVOICE)
        .order_by(Invoice.id.desc())
    )
    if invoice_ids:
        stmt = stmt.where(Invoice.id.in_([int(x) for x in invoice_ids]))
    return list(session.exec(stmt).all())
