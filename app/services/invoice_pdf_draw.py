from __future__ import annotations

import os

from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from .invoice_pdf_layout import LAYOUT, InvItem, safe_str, get_attr, prefixed_value, wrap_text


def draw_logo(c: Canvas, mx: float, top_y: float, content_w: float, comp) -> None:
    if comp is None:
        return
    cid = getattr(comp, "id", None)
    if cid is None:
        return
    from services.storage import company_logo_path
    path = company_logo_path(int(cid))
    if not os.path.exists(path):
        return
    try:
        from reportlab.lib.utils import ImageReader
        img = ImageReader(path)
        iw, ih = img.getSize()
        max_w = LAYOUT["logo_max_w"]
        max_h = LAYOUT["logo_max_h"]
        scale = min(max_w / iw, max_h / ih, 1.0)
        dw, dh = iw * scale, ih * scale
        x = mx + content_w - dw
        y = top_y - dh - 2 * mm
        c.drawImage(img, x, y, width=dw, height=dh, preserveAspectRatio=True, mask="auto")
    except Exception:
        pass


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

    # Sender address block
    if comp:
        set_font(bold=True, size=9)
        c.drawRightString(meta_x, y_meta, safe_str(get_attr(comp, "name")))
        y_meta -= 11
        set_font(bold=False, size=9)
        s_str = safe_str(get_attr(comp, "street"))
        if s_str:
            c.drawRightString(meta_x, y_meta, s_str)
            y_meta -= 11
        s_city = f"{safe_str(get_attr(comp, 'postal_code'))} {safe_str(get_attr(comp, 'city'))}".strip()
        if s_city:
            c.drawRightString(meta_x, y_meta, s_city)
            y_meta -= 11

    y_meta -= 6

    # Invoice metadata
    meta_data = [
        ("Rechnungsnr.:", nr or "-"),
        ("Datum:", inv_date or "-"),
        ("Leistungszeitraum:", service_date or "-"),
        ("Zahlung bis:", due_str or "-"),
    ]
    if company_vat_id:
        meta_data.append(("USt-ID:", company_vat_id))
    elif company_tax_id:
        meta_data.append(("Steuernr.:", company_tax_id))

    for label, val in meta_data:
        set_font(bold=True, size=9)
        c.drawRightString(meta_x, y_meta, label)
        val_text = safe_str(val)
        if val_text:
            set_font(bold=False, size=9)
            val_lines = wrap_text(val_text, font_r, 9, meta_col_w)
            line_height = 11
            v_y = y_meta - line_height
            for ln in val_lines:
                if not ln:
                    continue
                c.drawRightString(meta_x, v_y, ln)
                v_y -= line_height
            used_lines = max(1, len([l for l in val_lines if l]))
            y_meta = y_meta - (used_lines * line_height + 12)
        else:
            y_meta -= 24

    return y_meta, company_tax_id, company_vat_id


def draw_intro(c: Canvas, mx: float, y: float, content_w: float, invoice, comp,
               font_r: str, set_font) -> float:
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


def draw_table(c: Canvas, w: float, mx: float, y: float, content_w: float, my_bot: float,
               items: list[InvItem], h: float, font_r: str, set_font) -> float:
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
    set_font(bold=False, size=9)

    for it in items:
        desc_lines = wrap_text(it.description, font_r, 9, w_desc - 12)
        row_h = max(16, 8 + len(desc_lines) * 11)

        if y - row_h < my_bot + 50 * mm:
            c.showPage()
            c.setLineWidth(LAYOUT["line_width"])
            y = h - LAYOUT["margin_top"]
            y = draw_header_row(y)
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
                h: float, set_font) -> float:
    y -= 20
    if y < my_bot + 60 * mm:
        c.showPage()
        c.setLineWidth(LAYOUT["line_width"])
        y = h - LAYOUT["margin_top"]

    val_x = w - mx - 10
    lbl_x = val_x - 30 * mm

    def total_line(lbl, val, bold=False, offset=12):
        set_font(bold=bold, size=10)
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


def draw_footer(c: Canvas, w: float, mx: float, content_w: float, my_bot: float,
                comp, company_tax_id: str, company_vat_id: str,
                font_r: str, font_b: str, set_font):
    footer_y = my_bot + 25 * mm
    c.setStrokeColorRGB(*LAYOUT["col_line"])
    c.line(mx, footer_y, w - mx, footer_y)
    footer_y -= 5 * mm
    set_font(size=7, color=(0.4, 0.4, 0.4))

    comp_name = safe_str(get_attr(comp, "name"))
    comp_street = safe_str(get_attr(comp, "street"))
    comp_city = f"{safe_str(get_attr(comp, 'postal_code'))} {safe_str(get_attr(comp, 'city'))}".strip()
    f_addr = [comp_name]
    if comp_street:
        f_addr.append(comp_street)
    if comp_city:
        f_addr.append(comp_city)
    f_addr.append(safe_str(get_attr(comp, "email")))
    f_addr.append(safe_str(get_attr(comp, "phone")))
    f_bank = [
        safe_str(get_attr(comp, "bank_name")),
        prefixed_value("IBAN: ", get_attr(comp, "iban")),
        prefixed_value("BIC: ", get_attr(comp, "bic", "swift", "swift_code")),
    ]
    f_legal = [
        prefixed_value("Steuernr.: ", company_tax_id),
        prefixed_value("USt-ID: ", company_vat_id),
        safe_str(get_attr(comp, "business_type")),
    ]

    col_w = content_w / 3
    for i, (head, lines) in enumerate(zip(["Kontakt", "Bankverbindung", "Rechtliches"], [f_addr, f_bank, f_legal])):
        tx = mx + (i * col_w)
        ty = footer_y
        c.setFont(font_b, 7)
        c.drawString(tx, ty, head)
        c.setFont(font_r, 7)
        ty -= 8
        for l in lines:
            if l:
                c.drawString(tx, ty, str(l))
                ty -= 8
