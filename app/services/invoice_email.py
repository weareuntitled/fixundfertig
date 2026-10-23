"""The email that carries an invoice: subject, plain text and HTML. Personal in tone, not corporate."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape

from .invoice_pdf_draw import uses_artist_wordmark
from .invoice_pdf_layout import LAYOUT, format_amount, format_date, get_attr, payment_due_date, safe_str

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


def build_invoice_email(*, company, customer, invoice) -> InvoiceEmail:
    company_name = safe_str(get_attr(company, "name")) or "FixundFertig"
    wordmark = uses_artist_wordmark(company)
    profession = safe_str(get_attr(company, "business_type")) if wordmark else ""
    # An artist signs with their first name, a company with its name.
    sign_off_name = (safe_str(get_attr(company, "first_name")) if wordmark else "") or company_name

    number = safe_str(get_attr(invoice, "nr"))
    inv_date_raw = safe_str(get_attr(invoice, "date"))
    inv_date = format_date(inv_date_raw)
    due = payment_due_date(inv_date_raw)
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
    show_vat = vat > 0.005 and net > 0
    vat_rate = f"{round(vat / net * 100, 1):g}".replace(".", ",") if show_vat else ""
    vat_label = f"MwSt. {vat_rate} %"

    recipient = safe_str(get_attr(customer, "display_name", "name"))
    greeting = f"Hallo {recipient}," if recipient else "Hallo,"
    subject = subject_line or f"Rechnung {number} von {company_name} — {format_amount(gross)} €"
    intro = "danke für den Auftrag! Die Rechnung hängt als PDF an, hier das Wichtigste auf einen Blick."
    pay_line = f"Bitte bis zum {due} überweisen." if due else ""

    # ---- plain text
    lines = [greeting, "", intro, ""]
    if subject_line:
        lines.append(subject_line)
    lines.append(f"Rechnung {number}" + (f" vom {inv_date}" if inv_date else ""))
    lines.append("")
    for description, quantity, price in items:
        detail = f" ({quantity:g} x {_money(price)})" if quantity != 1 else ""
        lines.append(f"  {description}{detail}: {_money(quantity * price)}")
    lines.append("")
    if show_vat:
        lines += [f"Zwischensumme: {_money(net)}", f"{vat_label}: {_money(vat)}"]
    lines.append(f"Das macht: {_money(gross)}")
    if pay_line:
        lines.append(pay_line)
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

    subject_html = (
        f'<p style="margin:0 0 4px;font-size:15px;font-weight:700;color:{INK};">{escape(subject_line)}</p>'
        if subject_line else ""
    )
    profession_html = (
        f'<div style="padding-top:2px;font-size:13px;color:{MUTED};">{escape(profession)}</div>' if profession else ""
    )
    due_html = (
        f'<div style="padding-top:6px;font-size:14px;color:{MUTED};">Bitte bis zum '
        f'<strong style="color:{INK};">{escape(due)}</strong> überweisen.</div>' if due else ""
    )
    small_html = (
        f'<p style="margin:18px 0 0;font-size:12px;line-height:1.5;color:{MUTED};">{escape(LAYOUT["txt_small_biz"])}</p>'
        if small_business else ""
    )
    preheader = f"{_money(gross)}" + (f" · bitte bis {due}" if due else "")
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
<p style="margin:0;">{escape(intro)}</p>
</td></tr>
<tr><td style="padding:26px 36px 0;">
<div style="background:{PAPER};border-radius:14px;padding:22px 24px;">
{subject_html}
<div style="font-size:13px;color:{MUTED};">Rechnung {escape(number)}{escape(" vom " + inv_date) if inv_date else ""}</div>
<div style="padding-top:16px;font-size:14px;color:{MUTED};">Das macht</div>
<div style="font-size:40px;font-weight:300;letter-spacing:-0.03em;line-height:1.15;color:{INK};">{_money(gross)}</div>
{due_html}
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
