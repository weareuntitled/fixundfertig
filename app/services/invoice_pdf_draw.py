from __future__ import annotations

import os

from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from .invoice_pdf_layout import LAYOUT, InvItem, safe_str, get_attr, prefixed_value, wrap_text


def company_legal_name(comp) -> str:
    if comp is None:
        return ""
    first = safe_str(get_attr(comp, "first_name"))
    last = safe_str(get_attr(comp, "last_name"))
    return f"{first} {last}".strip()


def uses_artist_wordmark(comp) -> bool:
    return (
        safe_str(get_attr(comp, "business_type")).casefold() == "dj / producer"
        and bool(safe_str(get_attr(comp, "name")) and company_legal_name(comp))
    )


def draw_logo(c: Canvas, mx: float, top_y: float, content_w: float, comp, font_b: str) -> float:
    """Draw a personal wordmark or company logo; return occupied height in mm."""
    if comp is None:
        return 0.0
    artist_name = safe_str(get_attr(comp, "name"))
    if uses_artist_wordmark(comp):
        heading = artist_name.upper()
        profession = safe_str(get_attr(comp, "business_type"))
        if profession:
            heading += f" · {profession}"
        c.setFont(font_b, LAYOUT["fs_title"])
        c.setFillColorRGB(*LAYOUT["col_primary"])
        y = top_y
        for line in wrap_text(heading, font_b, LAYOUT["fs_title"], content_w):
            c.drawString(mx, y, line)
            y -= 20
        return (top_y - y) / mm + 8
    cid = getattr(comp, "id", None)
    if cid is None:
        return 0.0
    from services.storage import company_logo_path
    path = company_logo_path(int(cid))
    if not os.path.exists(path):
        return 0.0
    try:
        from reportlab.lib.utils import ImageReader
        img = ImageReader(path)
        iw, ih = img.getSize()
        max_w = LAYOUT["logo_max_w"]
        max_h = LAYOUT["logo_max_h"]
        scale = min(max_w / iw, max_h / ih, 1.0)
        dw, dh = iw * scale, ih * scale
        x = mx
        y = top_y - dh
        c.drawImage(img, x, y, width=dw, height=dh, preserveAspectRatio=True, mask="auto")
        return dh / mm + 4  # logo height + 4mm gap
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"draw_logo failed: {e}")
        return 0.0


def draw_recipient(c: Canvas, w: float, h: float, mx: float, content_w: float,
                   rec_name: str, rec_street: str, rec_zip: str, rec_city: str, rec_country: str,
                   comp, top_y: float, right_col_w: float,
                   font_r: str, set_font) -> float:
    y_rec = top_y - 5 * mm
    set_font(size=LAYOUT["fs_text"], color=LAYOUT["col_primary"])

    set_font(bold=True, size=9)
    c.drawString(mx, y_rec, "Rechnung an")
    y_rec -= 14
    set_font(bold=False, size=LAYOUT["fs_text"])

    rec_raw_lines = [l for l in [rec_name, rec_street, f"{rec_zip} {rec_city}".strip(), rec_country] if l]
    if not rec_raw_lines:
        rec_raw_lines = ["(Kein Empfänger hinterlegt)"]

    addr_w = content_w - right_col_w - 10 * mm
    recipient_leading = float(LAYOUT.get("recipient_leading_pt", 12))

    for base_ln in rec_raw_lines:
        for ln in wrap_text(base_ln, font_r, LAYOUT["fs_text"], addr_w):
            if not ln:
                continue
            c.drawString(mx, y_rec, ln)
            y_rec -= recipient_leading

    return y_rec


def draw_meta(c: Canvas, w: float, h: float, mx: float, comp, top_y: float,
              right_col_w: float, nr: str, inv_date: str, service_date: str, due_str: str,
              font_r: str, font_b: str, set_font) -> tuple[float, str, str]:
    meta_col_w = min(float(LAYOUT.get("meta_col_w_mm", 70)) * mm, right_col_w)
    meta_x = w - mx
    y_meta = top_y

    company_tax_id = safe_str(get_attr(comp, "tax_id"))
    company_vat_id = safe_str(get_attr(comp, "vat_id"))

    y_meta -= 14

    # Invoice metadata
    meta_data = [
        ("Rechnungsnr.:", nr or "-"),
        ("Datum:", inv_date or "-"),
        ("Leistungszeitraum:", service_date or "-"),
        ("Zahlung bis:", due_str or "-"),
    ]
    # Tax IDs are listed once, in the footer.

    label_x = meta_x - meta_col_w
    for label, val in meta_data:
        set_font(bold=True, size=9)
        c.drawString(label_x, y_meta, label)
        set_font(bold=False, size=9)
        c.drawRightString(meta_x, y_meta, safe_str(val))
        y_meta -= 14

    return y_meta, company_tax_id, company_vat_id


def draw_intro(c: Canvas, mx: float, y: float, content_w: float, invoice, comp,
               font_r: str, set_font) -> float:
    subject = safe_str(get_attr(invoice, "subject", default=""))
    if subject:
        set_font(bold=True, size=LAYOUT["fs_text"])
        c.drawString(mx, y, subject)
        y -= 14

    intro = safe_str(get_attr(invoice, "intro_text", "intro", default=""))
    if not intro:
        intro = safe_str(get_attr(comp, "invoice_intro", default="")) if comp is not None else ""
    if not intro:
        intro = "Vielen Dank für den Auftrag. Hiermit stelle ich folgende Leistungen in Rechnung."

    intro_lines = wrap_text(intro, font_r, LAYOUT["fs_text"], content_w)
    set_font(size=LAYOUT["fs_text"])
    for ln in intro_lines:
        c.drawString(mx, y, ln)
        y -= 12
    return y - 12


def draw_identity_line(c: Canvas, mx: float, y: float, text: str, set_font) -> float:
    set_font(bold=False, size=LAYOUT["fs_text"])
    c.drawString(mx, y, text)
    return y - 16


def draw_table(c: Canvas, w: float, mx: float, y: float, content_w: float, my_bot: float,
               items: list[InvItem], new_page, font_r: str, set_font) -> float:
    w_desc = content_w * LAYOUT["col_w_desc"]
    w_qty = content_w * LAYOUT["col_w_qty"]

    def draw_header_row(curr_y):
        c.setFillColorRGB(*LAYOUT["col_header_bg"])
        c.rect(mx, curr_y - 16, content_w, 16, stroke=0, fill=1)
        c.setStrokeColorRGB(*LAYOUT["col_line"])
        c.line(mx, curr_y - 16, w - mx, curr_y - 16)
        set_font(bold=True, size=11)
        c.drawString(mx + 6, curr_y - 12, "Beschreibung")
        c.drawRightString(mx + w_desc + w_qty - 6, curr_y - 12, "Menge")
        c.drawRightString(w - mx - 6, curr_y - 12, "Preis")
        return curr_y - 20

    y = draw_header_row(y)
    set_font(bold=False, size=10)

    for it in items:
        desc_lines = wrap_text(it.description, font_r, 10, w_desc - 12)
        row_h = max(16, 8 + len(desc_lines) * 12)

        if y - row_h < my_bot + 50 * mm:
            y = draw_header_row(new_page())
            set_font(bold=False, size=9)

        ty = y - 12
        for ln in desc_lines:
            c.drawString(mx + 6, ty, ln)
            ty -= 11

        qty_str = f"{it.quantity:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        c.drawRightString(mx + w_desc + w_qty - 6, y - 12, qty_str)
        price_str = f"{it.unit_price:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        c.drawRightString(w - mx - 6, y - 12, price_str)

        c.setStrokeColorRGB(*LAYOUT["col_line"])
        c.line(mx, y - row_h, w - mx, y - row_h)
        y -= row_h

    return y


def draw_totals(c: Canvas, w: float, mx: float, y: float, content_w: float, my_bot: float,
                net: float, tax: float, gross: float, tax_rate: float, is_small_business: bool,
                new_page, set_font) -> float:
    y -= 20
    if y < my_bot + 60 * mm:
        y = new_page()

    val_x = w - mx - 10
    lbl_x = val_x - 50 * mm

    def total_line(lbl, val, bold=False, offset=12):
        set_font(bold=bold, size=11 if bold else 10)
        c.drawString(lbl_x, y, lbl)
        c.drawRightString(val_x, y, val)
        return y - offset

    def fmt(v):
        return f"{v:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

    y = total_line("Netto:", fmt(net))
    if tax_rate > 0:
        y = total_line(f"USt ({int(tax_rate * 100)}%):", fmt(tax))
        c.line(lbl_x, y + 2, val_x, y + 2)
        y -= 4
    y = total_line("Gesamt:", fmt(gross), bold=True)

    if is_small_business:
        y -= 10
        set_font(size=8)
        c.drawString(mx, y, LAYOUT["txt_small_biz"])

    return y


def draw_tracked(c: Canvas, x: float, y: float, text: str, font: str, size: float,
                 tracking: float, align: str = "left") -> None:
    if align == "right":
        x -= stringWidth(text, font, size) + tracking * len(text)
    t = c.beginText(x, y)
    t.setFont(font, size)
    t.setCharSpace(tracking)
    t.textOut(text)
    c.drawText(t)


def issuer_lines(comp) -> list[str]:
    legal_name = company_legal_name(comp)
    artist_name = safe_str(get_attr(comp, "name"))
    lines = [legal_name] if uses_artist_wordmark(comp) else [artist_name, legal_name]
    street = safe_str(get_attr(comp, "street"))
    city = f"{safe_str(get_attr(comp, 'postal_code'))} {safe_str(get_attr(comp, 'city'))}".strip()
    lines.append(", ".join(part for part in (street, city) if part))
    country = safe_str(get_attr(comp, "country"))
    if country and country.upper() not in ("DE", "DEUTSCHLAND", "GERMANY"):
        lines.append(country)
    if uses_artist_wordmark(comp):
        lines.append(f"{artist_name} ist der Künstlername von {legal_name}.")
    return [line for line in lines if line]


def draw_footer(c: Canvas, w: float, mx: float, content_w: float, my_bot: float,
                comp, company_tax_id: str, company_vat_id: str,
                font_r: str, font_b: str, set_font, page_no: int, page_total: int):
    footer_y = my_bot + 16 * mm
    muted = LAYOUT["col_muted"]
    size = 7

    contact_name = (
        safe_str(get_attr(comp, "account_holder"))
        or company_legal_name(comp)
        or safe_str(get_attr(comp, "name"))
    )
    columns = [
        (1.5, "RECHNUNGSAUSSTELLER", issuer_lines(comp)),
        (1.0, "KONTAKT", [safe_str(get_attr(comp, "email")), safe_str(get_attr(comp, "phone"))]),
        (1.5, "BANKVERBINDUNG", [
            prefixed_value("Kontoinhaber: ", contact_name),
            safe_str(get_attr(comp, "bank_name")),
            prefixed_value("IBAN: ", get_attr(comp, "iban")),
            prefixed_value("BIC: ", get_attr(comp, "bic", "swift", "swift_code")),
        ]),
        (1.2, "STEUER", [
            prefixed_value("Steuernr.: ", company_tax_id),
            prefixed_value("USt-IdNr.: ", company_vat_id),
            "" if uses_artist_wordmark(comp) else safe_str(get_attr(comp, "business_type")),
        ]),
    ]
    columns = [column for column in columns if any(column[2])]
    page_col_w = 30
    gap = 12
    weights = sum(weight for weight, _, _ in columns)
    unit = (content_w - page_col_w - gap * len(columns)) / weights

    tx = mx
    for weight, head, lines in columns:
        col_w = weight * unit
        c.setFillColorRGB(*muted)
        draw_tracked(c, tx, footer_y, head, font_b, size, 0.6)
        c.setFont(font_r, size)
        ty = footer_y - 9
        for text in lines:
            if text:
                for line in wrap_text(text, font_r, size, col_w):
                    c.drawString(tx, ty, line)
                    ty -= 8.5
        tx += col_w + gap

    right = w - mx
    draw_tracked(c, right, footer_y, "SEITE", font_b, size, 0.6, align="right")
    c.setFont(font_r, size)
    c.drawRightString(right, footer_y - 9, f"{page_no} / {page_total}")
