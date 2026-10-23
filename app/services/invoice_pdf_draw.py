from __future__ import annotations

import os

from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from .invoice_pdf_layout import (
    LAYOUT, InvItem, format_amount, format_money, get_attr, group_iban, prefixed_value, safe_str, wrap_text,
)


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


def draw_header(c: Canvas, w: float, mx: float, top_y: float, content_w: float, comp,
                fonts: dict[str, str]) -> float:
    """Draw wordmark, logo or company name and the rule below it; return the y under the rule."""
    ink = LAYOUT["col_ink"]
    block_h = 0.0
    if comp is not None and uses_artist_wordmark(comp):
        c.setFillColorRGB(*ink)
        draw_tracked(c, mx, top_y - 11, safe_str(get_attr(comp, "name")).upper(), fonts["bold"], 15, 2.4)
        profession = safe_str(get_attr(comp, "business_type")).upper()
        c.setFillColorRGB(*LAYOUT["col_muted"])
        draw_tracked(c, mx, top_y - 24, profession, fonts["medium"], 7.5, 1.6)
        block_h = 32
    else:
        logo_h = draw_logo(c, mx, top_y, comp)
        if logo_h:
            block_h = logo_h
        else:
            name = safe_str(get_attr(comp, "name")) if comp is not None else ""
            if name:
                c.setFillColorRGB(*ink)
                c.setFont(fonts["bold"], 15)
                c.drawString(mx, top_y - 11, name)
                block_h = 18
    rule_y = top_y - block_h - 30
    c.setStrokeColorRGB(*ink)
    c.setLineWidth(0.75)
    c.line(mx, rule_y, w - mx, rule_y)
    c.setLineWidth(LAYOUT["line_width"])
    return rule_y


def draw_logo(c: Canvas, mx: float, top_y: float, comp) -> float:
    """Draw the uploaded company logo; return the occupied height in pt (0 when there is none)."""
    cid = getattr(comp, "id", None) if comp is not None else None
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
        scale = min(LAYOUT["logo_max_w"] / iw, LAYOUT["logo_max_h"] / ih, 1.0)
        dw, dh = iw * scale, ih * scale
        c.drawImage(img, mx, top_y - dh, width=dw, height=dh, preserveAspectRatio=True, mask="auto")
        return dh
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"draw_logo failed: {e}")
        return 0.0


def draw_recipient(c: Canvas, mx: float, rule_y: float, content_w: float,
                   rec_name: str, rec_street: str, rec_zip: str, rec_city: str, rec_country: str,
                   fonts: dict[str, str]) -> float:
    y = rule_y - 24
    c.setFillColorRGB(*LAYOUT["col_muted"])
    draw_tracked(c, mx, y, "RECHNUNG AN", fonts["medium"], 7, 1.0)
    y -= 15

    lines = [line for line in [rec_name, rec_street, f"{rec_zip} {rec_city}".strip(), rec_country] if line]
    if not lines:
        lines = ["(Kein Empfänger hinterlegt)"]
    c.setFillColorRGB(*LAYOUT["col_ink"])
    for index, base_line in enumerate(lines):
        font = fonts["bold"] if index == 0 else fonts["regular"]
        for line in wrap_text(base_line, font, 9, content_w * 0.6):
            c.setFont(font, 9)
            c.drawString(mx, y, line)
            y -= 13.5
    return y


def draw_title_block(c: Canvas, w: float, mx: float, y: float, content_w: float, invoice, comp,
                     nr: str, inv_date: str, service_date: str,
                     fonts: dict[str, str]) -> float:
    """Invoice number, subject and intro on the left, the dates on the right."""
    right = w - mx
    left_w = content_w - 160
    ink, muted = LAYOUT["col_ink"], LAYOUT["col_muted"]

    c.setFillColorRGB(*LAYOUT["col_accent"])
    draw_tracked(c, mx, y, "RECHNUNG", fonts["medium"], 7.5, 1.6)
    y -= 13
    if nr:
        c.setFillColorRGB(*ink)
        c.setFont(fonts["mono_medium"], 11)
        c.drawString(mx, y, f"Nr. {nr}")
        y -= 13.5
    y -= 10.5

    subject = safe_str(get_attr(invoice, "subject", default=""))
    if subject:
        c.setFillColorRGB(*ink)
        c.setFont(fonts["bold"], 12.75)
        for line in wrap_text(subject, fonts["bold"], 12.75, left_w):
            c.drawString(mx, y, line)
            y -= 16.5
        y -= 1

    intro = safe_str(get_attr(invoice, "intro_text", "intro", default=""))
    if not intro:
        intro = safe_str(get_attr(comp, "invoice_intro", default="")) if comp is not None else ""
    if not intro:
        intro = "Vielen Dank für den Auftrag. Hiermit stelle ich folgende Leistungen in Rechnung."
    c.setFillColorRGB(0.235, 0.251, 0.282)
    c.setFont(fonts["regular"], 9)
    for line in wrap_text(intro, fonts["regular"], 9, left_w):
        c.drawString(mx, y, line)
        y -= 13.5

    # Dates sit on the right, level with the last line of the intro.
    dates = [("Leistungsdatum:", service_date), ("Rechnungsdatum:", inv_date)]
    dates = [(label, value) for label, value in dates if value]
    date_y = y + 13.5 + (len(dates) - 1) * 13.5
    for label, value in dates:
        c.setFont(fonts["regular"], 9)
        c.setFillColorRGB(*muted)
        c.drawRightString(right - stringWidth(value, fonts["regular"], 9) - 4, date_y, label)
        c.setFillColorRGB(*ink)
        c.drawRightString(right, date_y, value)
        date_y -= 13.5
    return y


def draw_identity_line(c: Canvas, mx: float, y: float, text: str, set_font) -> float:
    set_font(bold=False, size=LAYOUT["fs_text"])
    c.drawString(mx, y, text)
    return y - 16


def draw_table(c: Canvas, w: float, mx: float, y: float, content_w: float, my_bot: float,
               items: list[InvItem], new_page, fonts: dict[str, str]) -> float:
    gap = 9
    right = w - mx
    amount_right = right
    price_right = amount_right - 66 - gap
    qty_right = price_right - 66 - gap
    desc_x = mx + 24 + gap
    desc_w = qty_right - 48 - gap - desc_x
    floor = my_bot + 20 * mm
    muted, ink, hair = LAYOUT["col_muted"], LAYOUT["col_ink"], LAYOUT["col_hair"]

    def draw_header_row(top: float) -> float:
        c.setStrokeColorRGB(*ink)
        c.setLineWidth(0.75)
        c.line(mx, top, right, top)
        c.setFillColorRGB(*muted)
        base = top - 13
        draw_tracked(c, mx, base, "POS.", fonts["medium"], 7, 1.0)
        draw_tracked(c, desc_x, base, "BESCHREIBUNG", fonts["medium"], 7, 1.0)
        draw_tracked(c, qty_right, base, "MENGE", fonts["medium"], 7, 1.0, align="right")
        draw_tracked(c, price_right, base, "EINZELPREIS", fonts["medium"], 7, 1.0, align="right")
        draw_tracked(c, amount_right, base, "BETRAG", fonts["medium"], 7, 1.0, align="right")
        c.setStrokeColorRGB(*hair)
        c.line(mx, top - 22.5, right, top - 22.5)
        c.setLineWidth(LAYOUT["line_width"])
        return top - 22.5

    y = draw_header_row(y)

    for number, it in enumerate(items, start=1):
        desc_lines = wrap_text(it.description, fonts["regular"], 9, desc_w)
        row_h = 21 + 13.5 * len(desc_lines)

        if y - row_h < floor:
            y = draw_header_row(new_page())

        base = y - 20.5
        c.setFont(fonts["regular"], 9)
        c.setFillColorRGB(*muted)
        c.drawString(mx, base, str(number))
        c.setFillColorRGB(*ink)
        ty = base
        for line in desc_lines:
            c.drawString(desc_x, ty, line)
            ty -= 13.5
        c.drawRightString(qty_right, base, format_amount(it.quantity))
        c.drawRightString(price_right, base, format_money(it.unit_price))
        c.setFont(fonts["medium"], 9)
        c.drawRightString(amount_right, base, format_money(it.quantity * it.unit_price))

        c.setStrokeColorRGB(*hair)
        c.line(mx, y - row_h, right, y - row_h)
        y -= row_h

    return y


def draw_totals(c: Canvas, w: float, mx: float, y: float, content_w: float, my_bot: float,
                net: float, tax: float, gross: float, tax_rate: float, is_small_business: bool,
                due_str: str, new_page, fonts: dict[str, str]) -> float:
    right = w - mx
    left = right - 218
    muted, ink = LAYOUT["col_muted"], LAYOUT["col_ink"]
    y -= 16.5
    if y - 130 < my_bot + 20 * mm:
        y = new_page()

    def row(label: str, value: str) -> None:
        c.setFont(fonts["regular"], 9)
        c.setFillColorRGB(*muted)
        c.drawString(left, y - 10, label)
        c.setFillColorRGB(*ink)
        c.drawRightString(right, y - 10, value)

    row("Zwischensumme", format_money(net))
    y -= 18
    if tax_rate > 0:
        row(f"Umsatzsteuer {tax_rate * 100:g} %".replace(".", ","), format_money(tax))
    elif is_small_business:
        row("Umsatzsteuer", "nicht erhoben")
    else:
        row("Umsatzsteuer 0 %", format_money(0))
    y -= 20

    c.setStrokeColorRGB(*LAYOUT["col_accent"])
    c.setLineWidth(1.5)
    c.line(left, y, right, y)
    c.setLineWidth(LAYOUT["line_width"])
    c.setFillColorRGB(*ink)
    draw_tracked(c, left, y - 22, "GESAMTBETRAG", fonts["medium"], 8, 0.7)
    c.setFont(fonts["bold"], 18)
    c.drawRightString(right, y - 22, format_money(gross))
    y -= 33

    y -= 12
    if is_small_business:
        y = draw_note(c, mx, y, content_w, LAYOUT["txt_small_biz"], fonts)
    if due_str:
        c.setFont(fonts["regular"], 7.9)
        c.setFillColorRGB(*muted)
        c.drawString(mx, y - 8, "Zahlbar bis")
        c.setFont(fonts["bold"], 7.9)
        c.setFillColorRGB(*ink)
        c.drawString(mx + stringWidth("Zahlbar bis ", fonts["regular"], 7.9), y - 8, f"{due_str}.")
        y -= 11.5
    return y


def draw_note(c: Canvas, mx: float, y: float, content_w: float, text: str, fonts: dict[str, str]) -> float:
    c.setFont(fonts["regular"], 7.9)
    c.setFillColorRGB(*LAYOUT["col_muted"])
    for line in wrap_text(text, fonts["regular"], 7.9, content_w):
        c.drawString(mx, y - 8, line)
        y -= 11.5
    return y


def account_holder_name(comp) -> str:
    return (
        safe_str(get_attr(comp, "account_holder"))
        or company_legal_name(comp)
        or safe_str(get_attr(comp, "name"))
    )


def draw_payment_box(c: Canvas, w: float, mx: float, y: float, content_w: float, my_bot: float,
                     comp, nr: str, new_page, fonts: dict[str, str]) -> float:
    iban = group_iban(get_attr(comp, "iban"))
    bank = safe_str(get_attr(comp, "bank_name"))
    if not iban and not bank:
        return y

    rows = [
        ("Kontoinhaber", account_holder_name(comp), "regular"),
        ("Bank", bank, "regular"),
        ("IBAN", iban, "mono"),
        ("BIC", safe_str(get_attr(comp, "bic", "swift", "swift_code")), "mono"),
        ("Verwendungszweck", f"Rechnung {nr}" if nr else "", "mono"),
    ]
    rows = [row for row in rows if row[1]]
    sentence = (
        "Ich bitte um Überweisung des Betrags auf das folgende Konto."
        if uses_artist_wordmark(comp)
        else "Bitte überweisen Sie den Betrag auf das folgende Konto."
    )

    pad_x, pad_y, gap = 15, 13.5, 21
    inner_w = content_w - 2 * pad_x
    left_w = (inner_w - gap) / 2.5
    right_x = mx + pad_x + left_w + gap
    right = mx + content_w - pad_x

    def row_font(kind: str) -> tuple[str, float]:
        return (fonts["mono"], 8.6) if kind == "mono" else (fonts["regular"], 9)

    laid_out = []
    for label, value, kind in rows:
        font, size = row_font(kind)
        value_w = right - right_x - stringWidth(label, fonts["regular"], 9) - 10
        laid_out.append((label, wrap_text(value, font, size, value_w), kind))
    row_heights = [13.5 * len(lines) + 7.5 for _, lines, _ in laid_out]

    sentence_lines = wrap_text(sentence, fonts["regular"], 9, left_w)
    left_h = 20 + 13.5 * len(sentence_lines)
    right_h = sum(row_heights) - 7.5
    box_h = 2 * pad_y + max(left_h, right_h)

    y -= 21
    if y - box_h < my_bot + 20 * mm:
        y = new_page()
    c.setFillColorRGB(*LAYOUT["col_surface"])
    c.roundRect(mx, y - box_h, content_w, box_h, 1.5, stroke=0, fill=1)

    c.setFillColorRGB(*LAYOUT["col_muted"])
    draw_tracked(c, mx + pad_x, y - pad_y - 6, "ZAHLUNGSINFORMATIONEN", fonts["medium"], 7, 1.0)
    c.setFillColorRGB(*LAYOUT["col_ink"])
    c.setFont(fonts["regular"], 9)
    ty = y - pad_y - 20
    for line in sentence_lines:
        c.drawString(mx + pad_x, ty, line)
        ty -= 13.5

    top = y - pad_y
    for index, (label, lines, kind) in enumerate(laid_out):
        base = top - 10
        c.setFont(fonts["regular"], 9)
        c.setFillColorRGB(*LAYOUT["col_muted"])
        c.drawString(right_x, base, label)
        font, size = row_font(kind)
        c.setFont(font, size)
        c.setFillColorRGB(*LAYOUT["col_ink"])
        for line in lines:
            c.drawRightString(right, base, line)
            base -= 13.5
        if index < len(laid_out) - 1:
            c.setStrokeColorRGB(*LAYOUT["col_hair"])
            c.line(right_x, top - row_heights[index] + 1.5, right, top - row_heights[index] + 1.5)
        top -= row_heights[index]
    return y - box_h


def draw_tracked(c: Canvas, x: float, y: float, text: str, font: str, size: float,
                 tracking: float, align: str = "left") -> None:
    if align == "right":
        x -= stringWidth(text, font, size) + tracking * len(text)
    t = c.beginText(x, y)
    t.setFont(font, size)
    t.setCharSpace(tracking)
    t.textOut(text)
    t.setCharSpace(0)  # character spacing would otherwise carry over to later text
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

    columns = [
        (1.5, "RECHNUNGSAUSSTELLER", issuer_lines(comp)),
        (1.0, "KONTAKT", [safe_str(get_attr(comp, "email")), safe_str(get_attr(comp, "phone"))]),
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
