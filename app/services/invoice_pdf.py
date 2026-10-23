from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from .invoice_pdf_layout import (
    LAYOUT, InvItem, format_date, format_service_period, get_attr, load_fonts, safe_float, safe_str,
)
from .invoice_pdf_draw import (
    draw_header, draw_recipient, draw_title_block, draw_identity_line,
    draw_table, draw_totals, draw_payment_box, draw_footer, company_legal_name, uses_artist_wordmark,
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
    artist_name = safe_str(get_attr(comp, "name")) if comp is not None else ""
    legal_name = company_legal_name(comp)
    line_holds_artist_name_as_its_own_token = False
    for it in item_iter:
        description = safe_str(get_attr(it, "description", "desc", default=""))
        if artist_name and _has_artist_name(description, artist_name):
            line_holds_artist_name_as_its_own_token = True
        if artist_name and legal_name:
            description = _append_legal_name(description, artist_name, legal_name)
        items.append(InvItem(
            description=description,
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
    service_date = format_date(get_attr(invoice, "delivery_date", default=""))
    if not service_date:
        service_date = format_service_period(
            get_attr(invoice, "service_from", default=""),
            get_attr(invoice, "service_to", default=""),
        )

    due_str = ""
    try:
        if inv_date:
            d = datetime.strptime(inv_date, "%Y-%m-%d").date()
            due_str = (d + timedelta(days=14)).strftime("%d.%m.%Y")
            inv_date = d.strftime("%d.%m.%Y")
    except Exception:
        pass

    nr = safe_str(get_attr(invoice, "nr", "invoice_number", default=""))

    fonts = load_fonts()
    font_r = fonts["regular"]
    font_b = fonts["bold"]
    w, h = A4
    mx = LAYOUT["margin_x"]
    my_bot = LAYOUT["margin_bottom"]
    content_w = w - (2 * mx)
    company_tax_id = safe_str(get_attr(comp, "tax_id"))
    company_vat_id = safe_str(get_attr(comp, "vat_id"))

    def draw_document(total_pages: int) -> tuple[bytes, int]:
        buf = BytesIO()
        c = Canvas(buf, pagesize=A4)
        c.setLineWidth(LAYOUT["line_width"])

        def set_font(bold=False, size=10, color=LAYOUT["col_primary"]):
            c.setFont(font_b if bold else font_r, size)
            c.setFillColorRGB(*color)

        def page_footer() -> None:
            draw_footer(c, w, mx, content_w, my_bot, comp, company_tax_id, company_vat_id,
                        fonts, c.getPageNumber(), total_pages or 1)

        def new_page() -> float:
            page_footer()
            c.showPage()
            c.setLineWidth(LAYOUT["line_width"])
            return h - LAYOUT["margin_top"]

        top_y = h - LAYOUT["margin_top"]
        rule_y = draw_header(c, w, mx, top_y, content_w, comp, fonts)
        y = draw_recipient(c, mx, rule_y, content_w, rec_name, rec_street, rec_zip, rec_city, rec_country, fonts)
        y = draw_title_block(c, w, mx, y - 39, content_w, invoice, comp, nr, inv_date, service_date, fonts)
        if artist_name and legal_name and not uses_artist_wordmark(comp) and not line_holds_artist_name_as_its_own_token:
            y = draw_identity_line(c, mx, y, f"{artist_name} ({legal_name})", set_font)
        y -= 22
        y = draw_table(c, w, mx, y, content_w, my_bot, items, new_page, fonts)
        y = draw_totals(c, w, mx, y, content_w, my_bot, net, tax, gross, tax_rate, is_small_business, due_str, new_page, fonts)
        draw_payment_box(c, w, mx, y, content_w, my_bot, comp, nr, new_page, fonts)
        page_footer()

        pages = c.getPageNumber()
        c.save()
        return buf.getvalue(), pages

    _, page_count = draw_document(0)
    return draw_document(page_count)[0]


def _is_name_token_char(char: str) -> bool:
    return char.isalpha() or char.isdigit()


def _standalone_artist_hits(description: str, artist_name: str) -> Iterator[tuple[int, int]]:
    cursor = 0
    while True:
        found = description.find(artist_name, cursor)
        if found < 0:
            return
        end = found + len(artist_name)
        preceded_by_token = found > 0 and _is_name_token_char(description[found - 1])
        followed_by_token = end < len(description) and _is_name_token_char(description[end])
        if preceded_by_token or followed_by_token:
            cursor = found + 1
            continue
        yield found, end
        cursor = end


def _has_artist_name(description: str, artist_name: str) -> bool:
    return any(_standalone_artist_hits(description, artist_name))


def _append_legal_name(description: str, artist_name: str, legal_name: str) -> str:
    suffix = f" ({legal_name})"
    parts: list[str] = []
    cursor = 0
    for start, end in _standalone_artist_hits(description, artist_name):
        parts.append(description[cursor:start])
        parts.append(description[start:end])
        if not description.startswith(suffix, end):
            parts.append(suffix)
        cursor = end
    parts.append(description[cursor:])
    return "".join(parts)
