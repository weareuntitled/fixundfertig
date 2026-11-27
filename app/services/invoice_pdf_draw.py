from __future__ import annotations

import os
from decimal import Decimal
from typing import TYPE_CHECKING

from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from .invoice_pdf_layout import (
    LAYOUT, InvItem, format_amount, format_date, format_money, format_vat_rate, get_attr, group_iban,
    prefixed_value, safe_str, wrap_text,
)

if TYPE_CHECKING:
    from logic.belegsummen import Belegsummen


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


QUOTE_INTRO = "Vielen Dank für Ihre Anfrage. Hiermit biete ich folgende Leistungen an."
INVOICE_INTRO = "Vielen Dank für den Auftrag. Hiermit stelle ich folgende Leistungen in Rechnung."
# Abschlagsrechnung (#496): eine Anzahlung vor der Leistung, keine erbrachte Leistung.
# Formulierung vom Steuerberater zu prüfen (§ 14 Abs. 4 Nr. 6 UStG).
DOWN_PAYMENT_INTRO = "Vereinbarungsgemäß berechne ich folgende Abschlagszahlung."


def down_payment_service_note(quote_nr: str) -> str:
    """Steht bei der Abschlagsrechnung anstelle des Leistungsdatums.

    Formulierung vom Steuerberater zu prüfen.
    """
    note = "Leistung: noch nicht erbracht – Anzahlung"
    return f"{note} gemäß Angebot {quote_nr}" if quote_nr else note


def _quote_nr(invoice) -> str:
    """Nummer des Angebots, aus dem ein Dokument entstand ('' ohne Angebot)."""
    return safe_str(get_attr(invoice, "quote_nr", default="")) or safe_str(
        get_attr(get_attr(invoice, "quote", default=None), "nr", default="")
    )


def draw_recipient(c: Canvas, mx: float, rule_y: float, content_w: float,
                   rec_name: str, rec_street: str, rec_zip: str, rec_city: str, rec_country: str,
                   fonts: dict[str, str], quote: bool = False) -> float:
    y = rule_y - 24
    c.setFillColorRGB(*LAYOUT["col_muted"])
    draw_tracked(c, mx, y, "ANGEBOT AN" if quote else "RECHNUNG AN", fonts["medium"], 7, 1.0)
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
                     fonts: dict[str, str], quote: bool = False, valid_until: str = "") -> float:
    """Document number, subject and intro on the left, the dates on the right.

    A quote is titled ANGEBOT and dated Angebotsdatum / Gültig bis instead of
    Leistungsdatum / Rechnungsdatum.
    """
    right = w - mx
    left_w = content_w - 160
    ink, muted = LAYOUT["col_ink"], LAYOUT["col_muted"]

    down_payment = not quote and get_attr(invoice, "down_payment_index", default=None) is not None
    if quote:
        heading = "ANGEBOT"
    elif bool(get_attr(invoice, "is_final_invoice", default=False)):
        heading = "SCHLUSSRECHNUNG"
    elif down_payment:
        heading = "ABSCHLAGSRECHNUNG"
    else:
        heading = "RECHNUNG"
    c.setFillColorRGB(*LAYOUT["col_accent"])
    draw_tracked(c, mx, y, heading, fonts["medium"], 7.5, 1.6)
    y -= 13
    if nr:
        c.setFillColorRGB(*ink)
        c.setFont(fonts["bold"], 11)
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
    # The company's own invoice intro speaks of rendered services: not for a down payment.
    if not intro and not quote and not down_payment:
        intro = safe_str(get_attr(comp, "invoice_intro", default="")) if comp is not None else ""
    if not intro:
        intro = QUOTE_INTRO if quote else (DOWN_PAYMENT_INTRO if down_payment else INVOICE_INTRO)
    c.setFillColorRGB(0.235, 0.251, 0.282)
    c.setFont(fonts["regular"], 9)
    for line in wrap_text(intro, fonts["regular"], 9, left_w):
        c.drawString(mx, y, line)
        y -= 13.5
    if down_payment:
        # Too long for the date column: the note gets its own line under the intro.
        y -= 4
        for line in wrap_text(down_payment_service_note(_quote_nr(invoice)), fonts["regular"], 9, left_w):
            c.drawString(mx, y, line)
            y -= 13.5

    # Dates sit on the right, level with the last line of the intro.
    # The service date is a mandatory invoice detail: without one it is the invoice date.
    # A down payment has no service date yet; the note above says so.
    if quote:
        dates = [("Angebotsdatum:", inv_date), ("Gültig bis:", valid_until)]
    elif down_payment:
        dates = [("Rechnungsdatum:", inv_date)]
    else:
        dates = [("Leistungsdatum:", service_date or ("wie Rechnungsdatum" if inv_date else "")),
                 ("Rechnungsdatum:", inv_date)]
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
        c.drawRightString(amount_right, base, format_money(it.amount))

        c.setStrokeColorRGB(*hair)
        c.line(mx, y - row_h, right, y - row_h)
        y -= row_h

    return y


def draw_due_line(c: Canvas, mx: float, y: float, due_str: str, fonts: dict[str, str]) -> float:
    """„Zahlbar bis TT.MM.JJJJ." unter den Summen."""
    if not due_str:
        return y
    c.setFont(fonts["regular"], 7.9)
    c.setFillColorRGB(*LAYOUT["col_muted"])
    c.drawString(mx, y - 8, "Zahlbar bis")
    c.setFont(fonts["bold"], 7.9)
    c.setFillColorRGB(*LAYOUT["col_ink"])
    c.drawString(mx + stringWidth("Zahlbar bis ", fonts["regular"], 7.9), y - 8, f"{due_str}.")
    return y - 11.5


def draw_totals(c: Canvas, w: float, mx: float, y: float, content_w: float, my_bot: float,
                summen: Belegsummen, is_small_business: bool,
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

    row("Zwischensumme", format_money(summen.net))
    y -= 18
    if summen.vat_rate > 0:
        row(f"Umsatzsteuer {format_vat_rate(summen.vat_rate)} %", format_money(summen.tax))
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
    c.drawRightString(right, y - 22, format_money(summen.gross))
    y -= 33

    y -= 12
    if is_small_business:
        y = draw_note(c, mx, y, content_w, LAYOUT["txt_small_biz"], fonts)
    return draw_due_line(c, mx, y, due_str, fonts)


def deduction_label(row: dict) -> str:
    """„abzüglich Abschlagsrechnung 10001 vom 26.11.2026“ (ohne Datum, wenn keins bekannt ist)."""
    label = f"abzüglich Abschlagsrechnung {row['nr']}"
    when = safe_str(row.get("date"))
    return f"{label} vom {when}" if when else label


def draw_final_totals(c: Canvas, w: float, mx: float, y: float, content_w: float, my_bot: float,
                      summen: Belegsummen, is_small_business: bool,
                      due_str: str, new_page, fonts: dict[str, str]) -> float:
    """Schlussrechnung block in reading order: Gesamtleistung, one „abzüglich“ line per
    down payment, then the Restbetrag below an accent line that touches no text.

    Kleinunternehmer get no tax column, no tax amounts and no tax sentence.
    """
    right = w - mx
    ink, muted, hair = LAYOUT["col_ink"], LAYOUT["col_muted"], LAYOUT["col_hair"]
    show_tax = not is_small_business
    total_right = right
    tax_right = right - 105
    net_right = right - 210 if show_tax else right - 110
    label_w = net_right - 70 - mx

    y -= 16.5
    block_estimate = 150 + 30 * len(summen.deductions)
    if y - block_estimate < my_bot + 20 * mm:
        y = new_page()

    c.setFillColorRGB(*LAYOUT["col_accent"])
    draw_tracked(c, mx, y, "ABRECHNUNG", fonts["medium"], 7.5, 1.6)
    c.setFillColorRGB(*muted)
    if show_tax:
        draw_tracked(c, net_right, y, "NETTO", fonts["medium"], 7, 1.0, align="right")
        draw_tracked(c, tax_right, y, "STEUER", fonts["medium"], 7, 1.0, align="right")
        draw_tracked(c, total_right, y, "GESAMT", fonts["medium"], 7, 1.0, align="right")
    else:
        draw_tracked(c, total_right, y, "BETRAG", fonts["medium"], 7, 1.0, align="right")
    y -= 18

    def amount_row(label: str, net_value: Decimal, tax_value: Decimal, total_value: Decimal,
                   rule: bool = True) -> None:
        nonlocal y
        c.setFont(fonts["regular"], 9)
        c.setFillColorRGB(*ink)
        lines = wrap_text(label, fonts["regular"], 9, label_w) or [""]
        base = y
        for line in lines:
            c.drawString(mx, base, line)
            base -= 13.5
        c.drawRightString(net_right, y, format_money(net_value))
        if show_tax:
            c.drawRightString(tax_right, y, format_money(tax_value))
        c.drawRightString(total_right, y, format_money(total_value))
        bottom = base + 13.5 - 6
        if rule:
            c.setStrokeColorRGB(*hair)
            c.line(mx, bottom, right, bottom)
        y = bottom - 12

    rows = [("Gesamtleistung", summen.net, summen.tax, summen.gross)] + [
        (deduction_label({"nr": row.nr, "date": format_date(row.date)}), row.net, row.tax, row.gross)
        for row in summen.deductions
    ]
    for index, (label, net_value, tax_value, total_value) in enumerate(rows):
        amount_row(label, net_value, tax_value, total_value, rule=index < len(rows) - 1)

    # The accent line takes the place of the last hairline, 6 pt under the row above.
    # The rest row's baseline lies 20 pt lower; its 12 pt amount reaches about 9 pt
    # above the baseline, so the line keeps clear of both rows.
    line_y = y + 12
    c.setStrokeColorRGB(*LAYOUT["col_accent"])
    c.setLineWidth(1.5)
    c.line(mx, line_y, right, line_y)
    c.setLineWidth(LAYOUT["line_width"])
    y = line_y - 20

    c.setFont(fonts["bold"], 9)
    c.setFillColorRGB(*ink)
    c.drawString(mx, y, "Restbetrag")
    c.drawRightString(net_right, y, format_money(summen.rest_net))
    if show_tax:
        c.drawRightString(tax_right, y, format_money(summen.rest_tax))
    c.setFont(fonts["bold"], 12)
    c.drawRightString(total_right, y, format_money(summen.rest_gross))
    y -= 18
    # Die Schlussrechnung ist eine Forderung: sie nennt ihr Zahlungsziel.
    return draw_due_line(c, mx, y, due_str, fonts)


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
        ("Kontoinhaber", account_holder_name(comp)),
        ("Bank", bank),
        ("IBAN", iban),
        ("BIC", safe_str(get_attr(comp, "bic", "swift", "swift_code"))),
        ("Verwendungszweck", nr),
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

    laid_out = []
    for label, value in rows:
        value_w = right - right_x - stringWidth(label, fonts["regular"], 9) - 10
        laid_out.append((label, wrap_text(value, fonts["regular"], 9, value_w)))
    row_heights = [13.5 * len(lines) + 7.5 for _, lines in laid_out]

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
    for index, (label, lines) in enumerate(laid_out):
        base = top - 10
        c.setFont(fonts["regular"], 9)
        c.setFillColorRGB(*LAYOUT["col_muted"])
        c.drawString(right_x, base, label)
        c.setFont(fonts["regular"], 9)
        c.setFillColorRGB(*LAYOUT["col_ink"])
        for line in lines:
            c.drawRightString(right, base, line)
            base -= 13.5
        if index < len(laid_out) - 1:
            c.setStrokeColorRGB(*LAYOUT["col_hair"])
            c.line(right_x, top - row_heights[index] + 1.5, right, top - row_heights[index] + 1.5)
        top -= row_heights[index]
    return y - box_h


def draw_payment_plan(c: Canvas, mx: float, y: float, content_w: float, my_bot: float,
                      rows: list[tuple[str, str, str]], new_page, fonts: dict[str, str]) -> float:
    """Quote section "ZAHLUNGSPLAN": one row per installment (percent, occasion, amount)."""
    if not rows:
        return y

    pad_x, pad_y, line_h, row_gap = 15, 13.5, 13.5, 7.5
    percent_w = 60.0
    label_x = mx + pad_x + percent_w
    right = mx + content_w - pad_x
    label_w = right - label_x - 90
    laid_out = [(percent, wrap_text(label, fonts["regular"], 9, label_w) or [""], amount)
                for percent, label, amount in rows]
    row_heights = [line_h * len(lines) + row_gap for _, lines, _ in laid_out]
    box_h = 2 * pad_y + 20 + sum(row_heights) - row_gap

    y -= 21
    if y - box_h < my_bot + 20 * mm:
        y = new_page()
    c.setFillColorRGB(*LAYOUT["col_surface"])
    c.roundRect(mx, y - box_h, content_w, box_h, 1.5, stroke=0, fill=1)

    c.setFillColorRGB(*LAYOUT["col_muted"])
    draw_tracked(c, mx + pad_x, y - pad_y - 6, "ZAHLUNGSPLAN", fonts["medium"], 7, 1.0)

    top = y - pad_y - 20
    for index, (percent, lines, amount) in enumerate(laid_out):
        base = top - 10
        c.setFont(fonts["regular"], 9)
        c.setFillColorRGB(*LAYOUT["col_ink"])
        c.drawString(mx + pad_x, base, percent)
        for line in lines:
            c.drawString(label_x, base, line)
            base -= line_h
        c.drawRightString(right, top - 10, amount)
        if index < len(laid_out) - 1:
            c.setStrokeColorRGB(*LAYOUT["col_hair"])
            c.line(mx + pad_x, top - row_heights[index] + 1.5, right, top - row_heights[index] + 1.5)
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
                fonts: dict[str, str], page_no: int, page_total: int, quote: bool = False):
    footer_y = my_bot + 16 * mm
    muted = LAYOUT["col_muted"]
    size = 7

    columns = [
        (1.5, "ANBIETER" if quote else "RECHNUNGSAUSSTELLER", issuer_lines(comp)),
        (1.0, "KONTAKT", [safe_str(get_attr(comp, "email")), safe_str(get_attr(comp, "phone"))]),
        (1.2, "STEUER", [
            prefixed_value("Steuernr.: ", company_tax_id),
            prefixed_value("USt-IdNr.: ", company_vat_id),
            "" if uses_artist_wordmark(comp) else safe_str(get_attr(comp, "business_type")),
        ]),
    ]
    columns = [column for column in columns if any(column[2])]
    page_col_w = 48
    gap = 12
    weights = sum(weight for weight, _, _ in columns)
    unit = (content_w - page_col_w - gap * len(columns)) / weights

    tx = mx
    for weight, head, lines in columns:
        col_w = weight * unit
        c.setFillColorRGB(*muted)
        draw_tracked(c, tx, footer_y, head, fonts["bold"], size, 0.6)
        c.setFont(fonts["regular"], size)
        ty = footer_y - 9
        for text in lines:
            if text:
                for line in wrap_text(text, fonts["regular"], size, col_w):
                    c.drawString(tx, ty, line)
                    ty -= 8.5
        tx += col_w + gap

    c.setFillColorRGB(*muted)
    c.setFont(fonts["regular"], size)
    c.drawRightString(w - mx, footer_y, f"Seite {page_no} / {page_total}")
