from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from .invoice_pdf_layout import (
    FONTS, LAYOUT, InvItem, format_date, format_money, format_service_period, get_attr, is_quote, payment_due_date, safe_float, safe_str,
)
from .invoice_pdf_draw import (
    draw_header, draw_recipient, draw_title_block, draw_identity_line,
    draw_table, draw_totals, draw_final_totals, draw_payment_box, draw_payment_plan, draw_footer,
    company_legal_name, uses_artist_wordmark,
)
from .invoice_pdf_stamp import stamp
from .payment_plan import format_percent, installments_with_amounts


def stored_invoice_pdf(invoice) -> bytes | None:
    """Read an existing PDF without regenerating or replacing historical output."""
    if getattr(invoice, "pdf_bytes", None):
        return bytes(invoice.pdf_bytes)
    filename = getattr(invoice, "pdf_filename", None)
    if isinstance(filename, str) and filename.strip():
        path = Path(filename)
        if not path.is_absolute() and not filename.startswith("storage/"):
            path = Path("storage/invoices") / path
        try:
            return path.read_bytes() or None
        except OSError:
            pass
    return None


def render_invoice_to_pdf_bytes(invoice, company=None, customer=None, down_payments=None) -> bytes:
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
    item_iter = list(raw_items if isinstance(raw_items, list) else (getattr(invoice, "items", []) or []))
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

    is_small_business = bool(get_attr(comp, "is_small_business", default=False)) if comp is not None else False
    is_final_invoice = bool(get_attr(invoice, "is_final_invoice", default=False))

    net = round(sum(i.quantity * i.unit_price for i in items), 2)
    tax_rate = (safe_float(get_attr(invoice, "vat_rate", default=0)) / 100.0
                if is_final_invoice else (0.0 if is_small_business else _vat_rate(invoice, net)))
    if is_final_invoice and tax_rate > 0:
        is_small_business = False
    tax = round(net * tax_rate, 2)

    deductions: list[dict] = []
    if is_final_invoice:
        from logic.final_invoice import final_deductions
        down_payments = [row.as_dict() for row in final_deductions(invoice)]
        for row in (down_payments or []):
            if isinstance(row, dict):
                deductions.append({
                    "nr": safe_str(row.get("nr")),
                    "date": format_date(row.get("date") or ""),
                    "net": safe_float(row.get("net")),
                    "tax": safe_float(row.get("tax")),
                    "total": safe_float(row.get("total")),
                })
            else:
                deductions.append({
                    "nr": safe_str(get_attr(row, "nr")),
                    "date": format_date(get_attr(row, "date")),
                    "net": safe_float(get_attr(row, "net")),
                    "tax": safe_float(get_attr(row, "tax")),
                    "total": safe_float(get_attr(row, "total")),
                })
        sum_net = round(sum(row["net"] for row in deductions), 2)
        sum_tax = round(sum(row["tax"] for row in deductions), 2)
        gross = round(net + tax, 2)
        rest = round(gross - sum_net - sum_tax, 2)
    else:
        sum_net = sum_tax = rest = 0.0
        gross = net + tax

    inv_date = safe_str(get_attr(invoice, "date", "invoice_date", default=""))
    service_date = format_date(get_attr(invoice, "delivery_date", default=""))
    if not service_date:
        service_date = format_service_period(
            get_attr(invoice, "service_from", default=""),
            get_attr(invoice, "service_to", default=""),
        )

    quote = is_quote(invoice)
    # A quote asks for no payment: no "Zahlbar bis", no payment box.
    due_str = "" if quote else payment_due_date(inv_date)
    valid_until = format_date(get_attr(invoice, "valid_until", default="")) if quote else ""
    inv_date = format_date(inv_date)
    # Installment amounts come from the gross total shown above them; invoices have no plan.
    plan_rows = [
        (format_percent(rate["percent"]), rate["label"], format_money(rate["amount"]))
        for rate in installments_with_amounts(get_attr(invoice, "payment_plan", default=None), round(gross, 2))
    ] if quote else []

    nr = safe_str(get_attr(invoice, "nr", "invoice_number", default=""))
    # The send path compares this with the stored invoice to catch an outdated PDF.
    keywords = stamp(nr, item_iter, rest if is_final_invoice else gross)

    fonts = FONTS
    font_r = fonts["regular"]
    font_b = fonts["bold"]
    w, h = A4
    mx = LAYOUT["margin_x"]
    my_bot = LAYOUT["margin_bottom"]
    content_w = w - (2 * mx)
    company_tax_id = safe_str(get_attr(comp, "tax_id"))
    company_vat_id = safe_str(get_attr(comp, "vat_id"))

    kind = _document_kind(invoice)
    doc_label = f"{kind} {nr}".strip()
    company_name = artist_name or legal_name

    def draw_document(total_pages: int) -> tuple[bytes, int]:
        buf = BytesIO()
        # Language and title make the PDF readable for screen readers and name the viewer window.
        c = Canvas(buf, pagesize=A4, lang="de-DE")
        c.setTitle(f"{doc_label} – {company_name}" if company_name else doc_label)
        c.setAuthor(company_name)
        c.setSubject(f"{doc_label} an {rec_name}" if rec_name else doc_label)
        c.setCreator("FixundFertig")
        c.setKeywords(keywords)
        c.setLineWidth(LAYOUT["line_width"])

        def set_font(bold=False, size=10, color=LAYOUT["col_primary"]):
            c.setFont(font_b if bold else font_r, size)
            c.setFillColorRGB(*color)

        def page_footer() -> None:
            draw_footer(c, w, mx, content_w, my_bot, comp, company_tax_id, company_vat_id,
                        fonts, c.getPageNumber(), total_pages or 1, quote)

        def new_page() -> float:
            page_footer()
            c.showPage()
            c.setLineWidth(LAYOUT["line_width"])
            return h - LAYOUT["margin_top"]

        top_y = h - LAYOUT["margin_top"]
        rule_y = draw_header(c, w, mx, top_y, content_w, comp, fonts)
        y = draw_recipient(c, mx, rule_y, content_w, rec_name, rec_street, rec_zip, rec_city, rec_country, fonts, quote)
        y = draw_title_block(c, w, mx, y - 39, content_w, invoice, comp, nr, inv_date, service_date, fonts,
                             quote, valid_until)
        # An invoice names the legal person above the services; a quote needs no such
        # line (#496): its footer already names the Anbieter with the legal name.
        if (not quote and artist_name and legal_name and not uses_artist_wordmark(comp)
                and not line_holds_artist_name_as_its_own_token):
            y = draw_identity_line(c, mx, y, f"{artist_name} ({legal_name})", set_font)
        y -= 22
        y = draw_table(c, w, mx, y, content_w, my_bot, items, new_page, fonts)
        if is_final_invoice:
            y = draw_final_totals(
                c, w, mx, y, content_w, my_bot, net, tax, tax_rate, is_small_business,
                deductions, sum_net, sum_tax, rest, due_str, new_page, fonts,
            )
        else:
            y = draw_totals(c, w, mx, y, content_w, my_bot, net, tax, gross, tax_rate, is_small_business, due_str, new_page, fonts)
        if not quote:
            draw_payment_box(c, w, mx, y, content_w, my_bot, comp, nr, new_page, fonts)
        else:
            draw_payment_plan(c, mx, y, content_w, my_bot, plan_rows, new_page, fonts)
        page_footer()

        pages = c.getPageNumber()
        c.save()
        return buf.getvalue(), pages

    _, page_count = draw_document(0)
    return draw_document(page_count)[0]


def _document_kind(invoice) -> str:
    """The document's name as a reader would say it: Angebot, Schlussrechnung, Abschlagsrechnung or Rechnung."""
    if is_quote(invoice):
        return "Angebot"
    if bool(get_attr(invoice, "is_final_invoice", default=False)):
        return "Schlussrechnung"
    if get_attr(invoice, "down_payment_index", default=None) is not None:
        return "Abschlagsrechnung"
    return "Rechnung"


def _vat_rate(invoice, net: float) -> float:
    """The VAT rate as a fraction. Drafts carry it as vat_rate, stored invoices only their total."""
    if get_attr(invoice, "ust_enabled", default=True) is False:
        return 0.0
    percent = safe_float(get_attr(invoice, "tax_rate", "vat_rate", default=0.0))
    if percent > 1.0:
        percent /= 100.0
    if percent > 0:
        return percent
    gross = safe_float(get_attr(invoice, "total_brutto", default=0.0))
    if net > 0 and gross > net + 0.005:
        return round((gross - net) / net, 3)
    return 0.0


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
