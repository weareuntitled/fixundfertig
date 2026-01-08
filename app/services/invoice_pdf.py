# app/services/invoice_pdf.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas


def _safe_str(x: Any) -> str:
    return (str(x) if x is not None else "").strip()


def _wrap_text(text: str, font: str, size: int, max_width: float) -> list[str]:
    text = _safe_str(text)
    if not text:
        return [""]
    words = text.replace("\n", " ").split()
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip() if cur else w
        if stringWidth(cand, font, size) <= max_width:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


@dataclass
class _InvItem:
    description: str
    quantity: float
    unit_price: float


def render_invoice_to_pdf_bytes(invoice, company=None, customer=None) -> bytes:
    """
    Drop-in replacement style:
    - nimmt invoice (SQLModel) entgegen
    - optional company und customer (wenn du sie beim Aufruf schon hast)
    - nutzt invoice.recipient_* bevorzugt, fallback auf customer recipient
    - wrapped Description, dynamische Zeilenhöhe, sauberes Tabellenlayout
    """

    # try to get company via invoice if not provided
    comp = company or getattr(invoice, "company", None) or getattr(invoice, "__dict__", {}).get("company", None)

    # Resolve recipient
    rec_name = _safe_str(getattr(invoice, "recipient_name", ""))
    rec_street = _safe_str(getattr(invoice, "recipient_street", ""))
    rec_zip = _safe_str(getattr(invoice, "recipient_postal_code", ""))
    rec_city = _safe_str(getattr(invoice, "recipient_city", ""))

    if (not rec_name) and customer is not None:
        rec_name = _safe_str(getattr(customer, "recipient_name", None) or getattr(customer, "display_name", None))
        rec_street = _safe_str(getattr(customer, "recipient_street", None) or getattr(customer, "strasse", None))
        rec_zip = _safe_str(getattr(customer, "recipient_postal_code", None) or getattr(customer, "plz", None))
        rec_city = _safe_str(getattr(customer, "recipient_city", None) or getattr(customer, "ort", None))

    # Items
    raw_items = getattr(invoice, "__dict__", {}).get("line_items", None)
    items: list[_InvItem] = []
    if isinstance(raw_items, list) and raw_items:
        for it in raw_items:
            items.append(
                _InvItem(
                    description=_safe_str(it.get("description") or it.get("desc")),
                    quantity=float(it.get("quantity") or it.get("qty") or 0),
                    unit_price=float(it.get("unit_price") or it.get("price") or 0),
                )
            )
    else:
        # fallback if invoice has items relation
        rel = getattr(invoice, "items", None) or getattr(invoice, "invoice_items", None)
        if rel:
            for it in rel:
                items.append(
                    _InvItem(
                        description=_safe_str(getattr(it, "description", "")),
                        quantity=float(getattr(it, "quantity", 0) or 0),
                        unit_price=float(getattr(it, "unit_price", 0) or 0),
                    )
                )

    # Tax
    tax_rate = float(getattr(invoice, "__dict__", {}).get("tax_rate", None) or getattr(invoice, "tax_rate", 0.0) or 0.0)
    # Kleinunternehmer in deiner App: oft tax_rate = 0
    is_small_business = bool(getattr(comp, "is_small_business", False)) if comp is not None else (tax_rate == 0.0)

    # Dates
    inv_date = _safe_str(getattr(invoice, "date", ""))
    service_date = _safe_str(getattr(invoice, "delivery_date", ""))

    # Pay due (Default 14 Tage)
    due_str = ""
    try:
        if inv_date:
            d = datetime.strptime(inv_date, "%Y-%m-%d").date()
            due = d + timedelta(days=14)
            due_str = due.strftime("%d.%m.%Y")
    except Exception:
        due_str = ""

    # Totals
    net = sum(i.quantity * i.unit_price for i in items)
    tax = net * tax_rate
    gross = net + tax

    buf = BytesIO()
    c = Canvas(buf, pagesize=A4)
    w, h = A4

    # Layout constants
    margin_x = 18 * mm
    top = h - 18 * mm
    bottom = 18 * mm

    font = "Helvetica"
    font_b = "Helvetica-Bold"

    def text(x, y, s, size=10, bold=False):
        c.setFont(font_b if bold else font, size)
        c.drawString(x, y, _safe_str(s))

    def text_r(x_right, y, s, size=10, bold=False):
        s = _safe_str(s)
        c.setFont(font_b if bold else font, size)
        c.drawRightString(x_right, y, s)

    # Header
    title = _safe_str(getattr(invoice, "title", "")) or "Rechnung"
    nr = _safe_str(getattr(invoice, "nr", ""))

    text(margin_x, top, title, size=22, bold=True)
    if nr:
        text_r(w - margin_x, top + 2, f"#{nr}", size=10, bold=False)

    y = top - 18

    # From block (left)
    sender_name = _safe_str(getattr(comp, "name", "")) if comp is not None else ""
    sender_person = (_safe_str(getattr(comp, "first_name", "")) + " " + _safe_str(getattr(comp, "last_name", ""))).strip() if comp is not None else ""
    sender_street = _safe_str(getattr(comp, "street", "")) if comp is not None else ""
    sender_zip = _safe_str(getattr(comp, "postal_code", "")) if comp is not None else ""
    sender_city = _safe_str(getattr(comp, "city", "")) if comp is not None else ""
    sender_email = _safe_str(getattr(comp, "email", "")) if comp is not None else ""
    sender_phone = _safe_str(getattr(comp, "phone", "")) if comp is not None else ""

    text(margin_x, y, "Von", size=10, bold=True)
    y -= 12
    if sender_name:
        text(margin_x, y, sender_name, size=10, bold=True)
        y -= 11
    if sender_person:
        text(margin_x, y, sender_person, size=10)
        y -= 11
    if sender_street:
        text(margin_x, y, sender_street, size=10)
        y -= 11
    if sender_zip or sender_city:
        text(margin_x, y, f"{sender_zip} {sender_city}".strip(), size=10)
        y -= 11
    if sender_email:
        text(margin_x, y, sender_email, size=10)
        y -= 11
    if sender_phone:
        text(margin_x, y, sender_phone, size=10)

    # Right meta block
    meta_x = w - margin_x
    meta_y = top - 20
    text_r(meta_x, meta_y, "Rechnungsdatum", size=9, bold=True)
    text_r(meta_x, meta_y - 11, inv_date or "-", size=9)
    text_r(meta_x, meta_y - 26, "Leistungszeitraum", size=9, bold=True)
    text_r(meta_x, meta_y - 37, service_date or "-", size=9)
    if due_str:
        text_r(meta_x, meta_y - 52, "Zahlung bis", size=9, bold=True)
        text_r(meta_x, meta_y - 63, due_str, size=9)

    # Recipient block
    rx = w * 0.55
    ry = top - 72
    c.setFont(font_b, 10)
    c.drawString(rx, ry, "Rechnung an")
    ry -= 12
    c.setFont(font, 10)

    # If still empty, show placeholder to make it obvious
    rec_lines = [
        rec_name or "",
        rec_street or "",
        (f"{rec_zip} {rec_city}".strip() if (rec_zip or rec_city) else ""),
    ]
    rec_lines = [ln for ln in rec_lines if ln]
    if not rec_lines:
        rec_lines = ["(Kein Empfänger hinterlegt)"]

    for ln in rec_lines:
        c.drawString(rx, ry, ln)
        ry -= 11

    # Intro text
    y = min(y, ry) - 18
    intro = _safe_str(getattr(comp, "invoice_intro", "")) if comp is not None else ""
    if not intro:
        intro = "Vielen Dank für den Auftrag. Hiermit stelle ich folgende Leistungen in Rechnung."

    intro_lines = _wrap_text(intro, font, 10, w - 2 * margin_x)
    c.setFont(font, 10)
    for ln in intro_lines:
        c.drawString(margin_x, y, ln)
        y -= 12

    y -= 6

    # Table
    table_x = margin_x
    table_w = w - 2 * margin_x
    col_desc = table_w * 0.62
    col_qty = table_w * 0.15
    col_price = table_w * 0.23

    row_h_min = 16
    line_h = 11

    def table_header(y0: float) -> float:
        c.setFont(font_b, 9)
        c.setLineWidth(0.5)
        c.rect(table_x, y0 - 14, table_w, 14, stroke=1, fill=0)
        c.drawString(table_x + 6, y0 - 11, "Beschreibung")
        c.drawRightString(table_x + col_desc + col_qty - 6, y0 - 11, "Menge")
        c.drawRightString(table_x + table_w - 6, y0 - 11, "Preis")
        return y0 - 16

    y = table_header(y)

    c.setFont(font, 9)

    for it in items:
        desc_lines = _wrap_text(it.description, font, 9, col_desc - 12)
        needed_h = max(row_h_min, 8 + len(desc_lines) * line_h)

        if y - needed_h < bottom + 55:
            c.showPage()
            y = top
            y = table_header(y)

        # Row border
        c.rect(table_x, y - needed_h, table_w, needed_h, stroke=1, fill=0)

        # Description
        tx = table_x + 6
        ty = y - 12
        for ln in desc_lines:
            c.drawString(tx, ty, ln)
            ty -= line_h

        # Qty
        qty_str = f"{it.quantity:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        c.drawRightString(table_x + col_desc + col_qty - 6, y - 12, qty_str)

        # Price
        price_str = f"{it.unit_price:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        c.drawRightString(table_x + table_w - 6, y - 12, price_str)

        y -= needed_h

    # Totals
    y -= 10
    if y < bottom + 85:
        c.showPage()
        y = top

    c.setFont(font_b, 10)
    c.drawRightString(table_x + table_w - 6, y, "Summe")
    c.setFont(font, 10)
    c.drawRightString(
        table_x + table_w - 6,
        y - 12,
        f"{net:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."),
    )

    if tax_rate > 0:
        c.setFont(font_b, 10)
        c.drawRightString(table_x + table_w - 6, y - 30, f"USt ({int(tax_rate*100)}%)")
        c.setFont(font, 10)
        c.drawRightString(
            table_x + table_w - 6,
            y - 42,
            f"{tax:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."),
        )
        c.setFont(font_b, 12)
        c.drawRightString(table_x + table_w - 6, y - 64, "Gesamt")
        c.drawRightString(
            table_x + table_w - 6,
            y - 78,
            f"{gross:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."),
        )
        y -= 90
    else:
        c.setFont(font_b, 12)
        c.drawRightString(table_x + table_w - 6, y - 30, "Gesamt")
        c.drawRightString(
            table_x + table_w - 6,
            y - 44,
            f"{gross:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."),
        )
        y -= 60

    # Footer
    footer_y = bottom + 40
    c.setFont(font, 8)

    iban = _safe_str(getattr(comp, "iban", "")) if comp is not None else ""
    bic = _safe_str(getattr(comp, "bic", "")) if comp is not None else ""
    bank = _safe_str(getattr(comp, "bank_name", "")) if comp is not None else ""
    tax_id = _safe_str(getattr(comp, "tax_id", "")) if comp is not None else ""
    vat_id = _safe_str(getattr(comp, "vat_id", "")) if comp is not None else ""
    jurisdiction = _safe_str(getattr(comp, "city", "")) if comp is not None else ""

    # Left footer: contact
    left_lines = []
    if sender_name:
        left_lines.append(sender_name)
    if sender_person:
        left_lines.append(sender_person)
    if sender_email:
        left_lines.append(sender_email)
    if sender_phone:
        left_lines.append(sender_phone)

    # Middle footer: bank
    mid_lines = []
    if bank:
        mid_lines.append(bank)
    if iban:
        mid_lines.append(f"IBAN: {iban}")
    if bic:
        mid_lines.append(f"BIC: {bic}")

    # Right footer: legal
    right_lines = []
    if tax_id:
        right_lines.append(f"Steuernummer: {tax_id}")
    if vat_id:
        right_lines.append(f"USt-ID: {vat_id}")
    if jurisdiction:
        right_lines.append(f"Gerichtsstand: {jurisdiction}")

    fx = margin_x
    mx = w * 0.45
    rx = w * 0.72

    yy = footer_y
    for ln in left_lines[:5]:
        c.drawString(fx, yy, ln)
        yy -= 10

    yy = footer_y
    for ln in mid_lines[:5]:
        c.drawString(mx, yy, ln)
        yy -= 10

    yy = footer_y
    for ln in right_lines[:5]:
        c.drawString(rx, yy, ln)
        yy -= 10

    # Kleinunternehmer clause
    if is_small_business:
        clause = "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet."
        c.setFont(font, 8)
        c.drawString(margin_x, bottom + 18, clause)

    c.save()
    return buf.getvalue()
