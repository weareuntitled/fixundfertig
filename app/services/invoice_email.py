"""The email that carries an invoice: subject, plain text and HTML.

Personal in tone, but the customer is addressed formally (Sie). The subject always
names the kind of document and its number (#496).
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape

from .invoice_pdf_draw import deduction_label, uses_artist_wordmark
from .invoice_pdf_layout import (
    LAYOUT, format_amount, format_date, get_attr, is_quote, payment_due_date, safe_float, safe_str,
)

INK = "#14161a"
MUTED = "#6b6f78"
SOFT = "#e9e5dd"
PAPER = "#f6f3ee"
FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"


@dataclass
class InvoiceEmail:
    subject: str
    text: str
    html: str


def _money(value: float) -> str:
    return f"{format_amount(value)} €"


def document_label(invoice) -> str:
    """Angebot, Schlussrechnung, Abschlagsrechnung or Rechnung."""
    if is_quote(invoice):
        return "Angebot"
    if bool(get_attr(invoice, "is_final_invoice", default=False)):
        return "Schlussrechnung"
    if get_attr(invoice, "down_payment_index", default=None) is not None:
        return "Abschlagsrechnung"
    return "Rechnung"


def build_invoice_email(*, company, customer, invoice, message: str = "",
                        down_payments: list[dict] | None = None) -> InvoiceEmail:
    """``down_payments`` are the deductions of a Schlussrechnung (rows with nr, date, net, tax, total)."""
    company_name = safe_str(get_attr(company, "name")) or "FixundFertig"
    wordmark = uses_artist_wordmark(company)
    profession = safe_str(get_attr(company, "business_type")) if wordmark else ""
    # An artist signs with their first name, a company with its name.
    sign_off_name = (safe_str(get_attr(company, "first_name")) if wordmark else "") or company_name

    # An Angebot names its validity instead of asking for payment.
    quote = is_quote(invoice)
    is_final_invoice = bool(get_attr(invoice, "is_final_invoice", default=False))
    label = document_label(invoice)
    number = safe_str(get_attr(invoice, "nr"))
    inv_date_raw = safe_str(get_attr(invoice, "date"))
    inv_date = format_date(inv_date_raw)
    due = "" if quote else payment_due_date(inv_date_raw)
    valid_until = format_date(safe_str(get_attr(invoice, "valid_until"))) if quote else ""
    subject_line = safe_str(get_attr(invoice, "subject"))
    gross = float(get_attr(invoice, "total_brutto", default=0) or 0)

    small_business = bool(get_attr(company, "is_small_business", default=False))
    items = []
    for item in get_attr(invoice, "items", default=None) or []:
        quantity = float(get_attr(item, "quantity", default=1) or 1)
        price = float(get_attr(item, "unit_price", default=0) or 0)
        items.append((safe_str(get_attr(item, "description")), quantity, price))

    # VAT is whatever the total adds on top of the positions.
    net = sum(quantity * price for _, quantity, price in items) if items else gross
    vat = gross - net
    # A final invoice's total is already the rest after the down payments, so its
    # position total is not the tax base shown in this summary.
    show_vat = vat > 0.005 and net > 0 and not is_final_invoice
    vat_rate = f"{round(vat / net * 100, 1):g}".replace(".", ",") if show_vat else ""
    vat_label = f"MwSt. {vat_rate} %"

    # Schlussrechnung: Gesamtleistung, one line per deducted down payment, Restbetrag —
    # in the same order and with the same words as the PDF.
    final_rows: list[tuple[str, float]] = []
    if is_final_invoice:
        percent = 0.0 if small_business else safe_float(get_attr(invoice, "vat_rate", default=0))
        if percent > 0 and percent <= 1:
            percent *= 100
        tax = round(net * percent / 100.0, 2) if percent > 0 else 0.0
        final_rows.append(("Gesamtleistung", round(net + tax, 2)))
        for row in down_payments or []:
            final_rows.append((
                deduction_label({"nr": safe_str(row.get("nr")), "date": format_date(row.get("date") or "")}),
                safe_float(row.get("total")),
            ))
    total_label = "Restbetrag" if is_final_invoice else "Gesamtbetrag"

    recipient = safe_str(get_attr(customer, "display_name", "name"))
    greeting = f"Hallo {recipient}," if recipient else "Hallo,"
    # Every subject names kind and number; a custom subject is added, not replacing them.
    if subject_line:
        subject = f"{label} {number} — {subject_line}"
    else:
        subject = f"{label} {number} von {company_name} — {format_amount(gross)} €"
    message = message.replace("\r\n", "\n").strip()
    # A personal message replaces the standard intro; the PDF hint stays.
    document = f"{'Das' if quote else 'Die'} {label}"
    if quote:
        standard_intro = "vielen Dank für Ihre Anfrage. Das Angebot hängt als PDF an, hier das Wichtigste auf einen Blick."
    elif label == "Abschlagsrechnung":
        standard_intro = (
            "wie vereinbart erhalten Sie die Abschlagsrechnung als PDF im Anhang, "
            "hier das Wichtigste auf einen Blick."
        )
    elif is_final_invoice:
        standard_intro = (
            "vielen Dank für Ihren Auftrag. Die Schlussrechnung hängt als PDF an; "
            "Ihre Abschlagszahlungen sind darin bereits abgezogen."
        )
    else:
        standard_intro = (
            "vielen Dank für Ihren Auftrag. Die Rechnung hängt als PDF an, hier das Wichtigste auf einen Blick."
        )
    intro = message or standard_intro
    attachment_hint = f"{document} hängt als PDF an." if message else ""
    pay_line = f"Bitte überweisen Sie den Betrag bis zum {due}." if due else ""
    valid_line = f"Das Angebot ist gültig bis {valid_until}." if valid_until else ""

    # ---- plain text
    lines = [greeting, "", intro] + (["", attachment_hint] if attachment_hint else []) + [""]
    if subject_line:
        lines.append(subject_line)
    lines.append(f"{label} {number}" + (f" vom {inv_date}" if inv_date else ""))
    lines.append("")
    for description, quantity, price in items:
        detail = f" ({quantity:g} x {_money(price)})" if quantity != 1 else ""
        lines.append(f"  {description}{detail}: {_money(quantity * price)}")
    lines.append("")
    if show_vat:
        lines += [f"Zwischensumme: {_money(net)}", f"{vat_label}: {_money(vat)}"]
    lines += [f"{row_label}: {_money(amount)}" for row_label, amount in final_rows]
    lines.append(f"{total_label}: {_money(gross)}")
    if pay_line:
        lines.append(pay_line)
    if valid_line:
        lines.append(valid_line)
    if small_business:
        lines += ["", LAYOUT["txt_small_biz"]]
    lines += ["", "Liebe Grüße", sign_off_name]
    text = "\n".join(lines) + "\n"

    # ---- HTML
    def item_row(description: str, detail: str, amount: str) -> str:
        sub = f'<div style="font-size:12px;color:{MUTED};padding-top:2px;">{escape(detail)}</div>' if detail else ""
        return (
            f'<tr><td style="padding:11px 0;border-bottom:1px solid {SOFT};font-size:15px;color:{INK};">'
            f"{escape(description)}{sub}</td>"
            f'<td align="right" valign="top" style="padding:11px 0;border-bottom:1px solid {SOFT};'
            f'font-size:15px;color:{INK};white-space:nowrap;">{amount}</td></tr>'
        )

    def small_row(label: str, value: str) -> str:
        return (
            f'<tr><td style="padding:2px 0;font-size:13px;color:{MUTED};">{escape(label)}</td>'
            f'<td align="right" style="padding:2px 0;font-size:13px;color:{MUTED};">{value}</td></tr>'
        )

    item_rows = "".join(
        item_row(description, f"{quantity:g} × {_money(price)}" if quantity != 1 else "", _money(quantity * price))
        for description, quantity, price in items
    )
    extras = small_row("Zwischensumme", _money(net)) + small_row(vat_label, _money(vat)) if show_vat else ""
    extras += "".join(small_row(row_label, _money(amount)) for row_label, amount in final_rows)

    subject_html = (
        f'<p style="margin:0 0 4px;font-size:15px;font-weight:700;color:{INK};">{escape(subject_line)}</p>'
        if subject_line else ""
    )
    profession_html = (
        f'<div style="padding-top:2px;font-size:13px;color:{MUTED};">{escape(profession)}</div>' if profession else ""
    )
    due_html = (
        f'<div style="padding-top:6px;font-size:14px;color:{MUTED};">Bitte überweisen Sie den Betrag bis zum '
        f'<strong style="color:{INK};">{escape(due)}</strong>.</div>' if due else ""
    )
    valid_html = (
        f'<div style="padding-top:6px;font-size:14px;color:{MUTED};">{escape(valid_line)}</div>' if valid_line else ""
    )
    small_html = (
        f'<p style="margin:18px 0 0;font-size:12px;line-height:1.5;color:{MUTED};">{escape(LAYOUT["txt_small_biz"])}</p>'
        if small_business else ""
    )
    attachment_html = (
        f'<p style="margin:12px 0 0;font-size:13px;color:{MUTED};">{escape(attachment_hint)}</p>' if attachment_hint else ""
    )
    preheader = f"{_money(gross)}" + (f" · bitte bis {due}" if due else "") + (
        f" · gültig bis {valid_until}" if valid_until else ""
    )
    html = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(subject)}</title></head>
<body style="margin:0;padding:0;background:{PAPER};font-family:{FONT};color:{INK};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PAPER};"><tr><td align="center" style="padding:28px 14px;">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="width:100%;max-width:560px;background:#ffffff;border-radius:18px;">
<tr><td style="padding:34px 36px 0;">
<div style="font-size:30px;font-weight:300;letter-spacing:-0.035em;line-height:1.1;color:{INK};">{escape(company_name)}</div>
{profession_html}
</td></tr>
<tr><td style="padding:26px 36px 0;font-size:16px;line-height:1.55;color:{INK};">
<p style="margin:0 0 12px;">{escape(greeting)}</p>
<p style="margin:0;">{escape(intro).replace(chr(10), "<br>")}</p>
{attachment_html}
</td></tr>
<tr><td style="padding:26px 36px 0;">
<div style="background:{PAPER};border-radius:14px;padding:22px 24px;">
{subject_html}
<div style="font-size:13px;color:{MUTED};">{label} {escape(number)}{escape(" vom " + inv_date) if inv_date else ""}</div>
<div style="padding-top:16px;font-size:14px;color:{MUTED};">{total_label}</div>
<div style="font-size:40px;font-weight:300;letter-spacing:-0.03em;line-height:1.15;color:{INK};">{_money(gross)}</div>
{due_html}{valid_html}
</div>
</td></tr>
<tr><td style="padding:22px 36px 0;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
{item_rows}
</table>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px;">
{extras}
</table>
{small_html}
</td></tr>
<tr><td style="padding:30px 36px 34px;font-size:16px;line-height:1.5;color:{INK};">
<p style="margin:0;">Liebe Grüße</p>
<p style="margin:0;font-weight:700;">{escape(sign_off_name)}</p>
</td></tr>
</table>
<div style="padding-top:14px;font-size:11px;color:{MUTED};">verschickt mit FixundFertig</div>
</td></tr></table>
</body>
</html>"""
    return InvoiceEmail(subject=subject, text=text, html=html)
