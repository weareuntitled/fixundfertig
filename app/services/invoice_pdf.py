from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from .invoice_pdf_layout import LAYOUT, InvItem, safe_str, safe_float, get_attr, wrap_text
from .invoice_pdf_draw import (
    draw_logo, draw_recipient, draw_meta, draw_intro,
    draw_table, draw_totals, draw_footer,
)


def render_invoice_to_pdf_bytes(invoice, company=None, customer=None) -> bytes:
    comp = company or get_attr(invoice, "company", default=None) or getattr(invoice, "__dict__", {}).get("company", None)
    if customer is None:
        customer = get_attr(invoice, "customer", default=None)

    rec_name = safe_str(get_attr(invoice, "recipient_name", "address_name", default=""))
    rec_street = safe_str(get_attr(invoice, "recipient_street", "address_street", default=""))
    rec_zip = safe_str(get_attr(invoice, "recipient_postal_code", "address_zip", default=""))
    rec_city = safe_str(get_attr(invoice, "recipient_city", "address_city", default=""))
    rec_country = safe_str(get_attr(invoice, "recipient_country", "address_country", default=""))

    if (not rec_name) and customer is not None:
        rec_name = safe_str(get_attr(customer, "recipient_name", "display_name", "name", default=""))
        rec_street = safe_str(get_attr(customer, "recipient_street", "strasse", default=""))
        rec_zip = safe_str(get_attr(customer, "recipient_postal_code", "plz", default=""))
        rec_city = safe_str(get_attr(customer, "recipient_city", "ort", default=""))
        rec_country = safe_str(get_attr(customer, "country", default=""))

    raw_items = get_attr(invoice, "line_items", "items", "positions", default=None)
    if raw_items is None:
        raw_items = getattr(invoice, "__dict__", {}).get("line_items", None)

    items: list[InvItem] = []
    item_iter = raw_items if isinstance(raw_items, list) else (getattr(invoice, "items", []) or [])
    for it in item_iter:
        items.append(InvItem(
            description=safe_str(get_attr(it, "description", "desc", default="")),
            quantity=safe_float(get_attr(it, "quantity", "qty", default=0)),
            unit_price=safe_float(get_attr(it, "unit_price", "price", default=0)),
        ))

    tax_rate = safe_float(get_attr(invoice, "tax_rate", default=0.0))
    if tax_rate > 1.0:
        tax_rate = tax_rate / 100.0
    is_small_business = bool(get_attr(comp, "is_small_business", default=False)) if comp is not None else (tax_rate == 0.0)

    net = sum(i.quantity * i.unit_price for i in items)
    tax = net * tax_rate
    gross = net + tax

    inv_date = safe_str(get_attr(invoice, "date", "invoice_date", default=""))
    service_date = safe_str(get_attr(invoice, "delivery_date", default=""))
    if not service_date:
        service_from = safe_str(get_attr(invoice, "service_from", default=""))
        service_to = safe_str(get_attr(invoice, "service_to", default=""))
        if service_from and service_to and service_from != service_to:
            service_date = f"{service_from} bis {service_to}"
        else:
            service_date = service_from or service_to

    due_str = ""
    try:
        if inv_date:
            d = datetime.strptime(inv_date, "%Y-%m-%d").date()
            due_str = (d + timedelta(days=14)).strftime("%d.%m.%Y")
            inv_date = d.strftime("%d.%m.%Y")
    except Exception:
        pass

    nr = safe_str(get_attr(invoice, "nr", "invoice_number", default=""))

    buf = BytesIO()
    c = Canvas(buf, pagesize=A4)
    w, h = A4
    c.setLineWidth(LAYOUT["line_width"])
    mx = LAYOUT["margin_x"]
    my_bot = LAYOUT["margin_bottom"]
    content_w = w - (2 * mx)
    font_r = LAYOUT["font_reg"]
    font_b = LAYOUT["font_bold"]

    def set_font(bold=False, size=10, color=LAYOUT["col_primary"]):
        c.setFont(font_b if bold else font_r, size)
        c.setFillColorRGB(*color)

    top_y = h - LAYOUT["margin_top"]
    right_col_w = min(70 * mm, content_w * 0.38)

    draw_logo(c, mx, top_y, content_w, comp)
    y_rec = draw_recipient(c, w, h, mx, content_w, rec_name, rec_street, rec_zip, rec_city, rec_country,
                           comp, top_y, right_col_w, font_r, set_font)
    y_meta, company_tax_id, company_vat_id = draw_meta(
        c, w, h, mx, comp, top_y, right_col_w, nr, inv_date, service_date, due_str, font_r, font_b, set_font)

    y = min(y_rec, y_meta) - 12 * mm
    y = draw_intro(c, mx, y, content_w, invoice, comp, font_r, set_font)
    y = draw_table(c, w, mx, y, content_w, my_bot, items, h, font_r, set_font)
    draw_totals(c, w, mx, y, content_w, my_bot, net, tax, gross, tax_rate, is_small_business, h, set_font)
    draw_footer(c, w, mx, content_w, my_bot, comp, company_tax_id, company_vat_id, font_r, font_b, set_font)

    c.save()
    return buf.getvalue()
