from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from fpdf import FPDF


def _sanitize_text(s: Any) -> str:
    """Make text safe for core PDF fonts by replacing unsupported characters."""
    if s is None:
        return ""
    txt = str(s)
    txt = txt.replace("\u00a0", " ")  # nbsp
    txt = txt.replace("€", "EUR")
    txt = txt.replace("–", "-").replace("—", "-")
    return txt.encode("latin-1", "replace").decode("latin-1")


def _wrap_lines(pdf: FPDF, text: str, max_width: float) -> List[str]:
    """Simple word wrap based on current font metrics."""
    text = _sanitize_text(text).strip()
    if not text:
        return [""]

    words = text.split()
    lines: List[str] = []
    cur = ""

    for w in words:
        trial = (cur + " " + w).strip()
        if pdf.get_string_width(trial) <= max_width:
            cur = trial
            continue

        if cur:
            lines.append(cur)

        # If a single word is longer than max width, hard-split it
        if pdf.get_string_width(w) <= max_width:
            cur = w
        else:
            chunk = ""
            for ch in w:
                trial2 = chunk + ch
                if pdf.get_string_width(trial2) <= max_width:
                    chunk = trial2
                else:
                    if chunk:
                        lines.append(chunk)
                    chunk = ch
            cur = chunk

    if cur:
        lines.append(cur)

    return lines


def _fmt_date_de(date_str: str) -> str:
    """Accepts YYYY-MM-DD or DD.MM.YYYY and returns DD.MM.YYYY when possible."""
    s = (date_str or "").strip()
    if not s:
        return ""
    if "." in s and len(s) >= 8:
        return s
    try:
        dt = datetime.fromisoformat(s)
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return s


def _fmt_money_eur(amount: float) -> str:
    s = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} EUR"


class InvoicePDF(FPDF):
    def __init__(self, *, company: Any, invoice: Any) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.company = company
        self.invoice = invoice
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(left=20, top=20, right=20)

    @property
    def usable_w(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def header(self) -> None:
        comp = self.company

        self.set_font("Helvetica", "B", 12)
        self.cell(0, 6, _sanitize_text(getattr(comp, "name", "")), ln=1)

        self.set_font("Helvetica", "", 9)
        addr_parts = [
            getattr(comp, "street", ""),
            f"{getattr(comp, 'zip', '')} {getattr(comp, 'city', '')}".strip(),
            getattr(comp, "country", ""),
        ]
        addr = ", ".join([str(p).strip() for p in addr_parts if str(p).strip()])
        if addr:
            self.multi_cell(0, 4.5, _sanitize_text(addr))
        if getattr(comp, "email", ""):
            self.cell(0, 4.5, _sanitize_text(getattr(comp, "email", "")), ln=1)

        self.ln(2)
        self.set_draw_color(220, 220, 220)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(6)

    def footer(self) -> None:
        comp = self.company

        self.set_y(-18)
        self.set_draw_color(220, 220, 220)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)

        self.set_font("Helvetica", "", 8)

        bank_name = getattr(comp, "bank_name", "") or ""
        iban = getattr(comp, "iban", "") or ""
        bic = getattr(comp, "bic", "") or ""
        tax_id = getattr(comp, "tax_id", "") or ""
        vat_id = getattr(comp, "vat_id", "") or ""

        left = []
        if bank_name:
            left.append(f"Bank: {bank_name}")
        if iban:
            left.append(f"IBAN: {iban}")
        if bic:
            left.append(f"BIC: {bic}")

        right = []
        if tax_id:
            right.append(f"Steuernr.: {tax_id}")
        if vat_id:
            right.append(f"USt-IdNr.: {vat_id}")

        self.set_x(self.l_margin)
        self.cell(self.usable_w * 0.64, 4, _sanitize_text(" | ".join(left)), border=0)
        self.cell(self.usable_w * 0.36, 4, _sanitize_text(" | ".join(right)), border=0, ln=1)


def render_invoice_to_pdf_bytes(invoice: Any) -> bytes:
    """Render an invoice PDF. Requires invoice.company and invoice.customer."""
    company = getattr(invoice, "company", None)
    customer = getattr(invoice, "customer", None)
    if company is None or customer is None:
        raise ValueError("Invoice must have .company and .customer set for rendering")

    pdf = InvoicePDF(company=company, invoice=invoice)
    pdf.add_page()

    # Recipient block (left)
    pdf.set_font("Helvetica", "", 10)

    recipient_lines = [
        getattr(invoice, "address_name", "") or getattr(customer, "name", ""),
        getattr(invoice, "address_street", "") or getattr(customer, "street", ""),
        f"{getattr(invoice, 'address_zip', '') or getattr(customer, 'zip', '')} "
        f"{getattr(invoice, 'address_city', '') or getattr(customer, 'city', '')}".strip(),
        getattr(invoice, "address_country", "") or getattr(customer, "country", ""),
    ]
    recipient_lines = [str(x).strip() for x in recipient_lines if str(x).strip()]

    start_y = pdf.get_y()
    pdf.set_xy(pdf.l_margin, start_y)
    pdf.multi_cell(pdf.usable_w * 0.55, 5, _sanitize_text("\n".join(recipient_lines)))
    recipient_end_y = pdf.get_y()

    # Invoice info (right)
    right_x = pdf.l_margin + pdf.usable_w * 0.60
    pdf.set_xy(right_x, start_y)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 6, _sanitize_text(getattr(invoice, "title", "Rechnung")), ln=1)
    pdf.set_font("Helvetica", "", 10)

    inv_no = getattr(invoice, "invoice_number", "") or ""
    inv_date = _fmt_date_de(getattr(invoice, "date", "") or "")
    delivery = (getattr(invoice, "delivery_date", "") or "").strip()

    pdf.set_x(right_x)
    if inv_no:
        pdf.cell(0, 5, _sanitize_text(f"Rechnungsnummer: {inv_no}"), ln=1)
    if inv_date:
        pdf.set_x(right_x)
        pdf.cell(0, 5, _sanitize_text(f"Rechnungsdatum: {inv_date}"), ln=1)
    if delivery:
        pdf.set_x(right_x)
        delivery_out = delivery if "bis" in delivery else _fmt_date_de(delivery)
        pdf.multi_cell(0, 5, _sanitize_text(f"Leistungszeitraum: {delivery_out}"))

    # Continue below the lower of both blocks
    pdf.set_y(max(recipient_end_y, pdf.get_y()) + 6)

    # Intro text (editable)
    intro_text = ""
    if hasattr(invoice, "intro_text") and getattr(invoice, "intro_text"):
        intro_text = str(getattr(invoice, "intro_text"))
    else:
        intro_text = str(invoice.__dict__.get("intro_text", "") or "")
    intro_text = intro_text.strip()
    if intro_text:
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, _sanitize_text(intro_text))
        pdf.ln(2)

    # Items
    items: List[Dict[str, Any]] = []
    if invoice.__dict__.get("line_items"):
        items = list(invoice.__dict__["line_items"])
    elif hasattr(invoice, "items") and getattr(invoice, "items"):
        items = [i.__dict__ for i in getattr(invoice, "items")]
    else:
        items = []

    # Table columns (sum == usable width)
    col_desc = pdf.usable_w * 0.56
    col_qty = pdf.usable_w * 0.12
    col_unit = pdf.usable_w * 0.14
    col_tax = pdf.usable_w * 0.08
    col_total = pdf.usable_w - (col_desc + col_qty + col_unit + col_tax)

    def table_header() -> None:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(245, 245, 245)
        pdf.set_draw_color(220, 220, 220)
        pdf.cell(col_desc, 7, _sanitize_text("Beschreibung"), border=1, fill=True)
        pdf.cell(col_qty, 7, _sanitize_text("Menge"), border=1, fill=True, align="R")
        pdf.cell(col_unit, 7, _sanitize_text("Preis"), border=1, fill=True, align="R")
        pdf.cell(col_tax, 7, _sanitize_text("USt"), border=1, fill=True, align="R")
        pdf.cell(col_total, 7, _sanitize_text("Summe"), border=1, fill=True, align="R", ln=1)
        pdf.set_font("Helvetica", "", 9)

    table_header()

    line_h = 5.0
    for it in items:
        desc = str(it.get("description", "") or "")
        qty = float(it.get("quantity", 0) or 0)
        unit_price = float(it.get("unit_price", 0) or 0)
        tax_rate = float(it.get("tax_rate", 0) or 0)
        total = qty * unit_price

        # Wrap description, compute row height
        lines = _wrap_lines(pdf, desc, col_desc - 2.0)
        row_h = max(line_h * len(lines) + 2.0, 8.0)

        # Manual page break handling (because we draw rectangles)
        if pdf.get_y() + row_h > pdf.page_break_trigger:
            pdf.add_page()
            table_header()

        x0 = pdf.get_x()
        y0 = pdf.get_y()

        # Draw borders
        pdf.set_draw_color(220, 220, 220)
        pdf.rect(x0, y0, col_desc, row_h)
        pdf.rect(x0 + col_desc, y0, col_qty, row_h)
        pdf.rect(x0 + col_desc + col_qty, y0, col_unit, row_h)
        pdf.rect(x0 + col_desc + col_qty + col_unit, y0, col_tax, row_h)
        pdf.rect(x0 + col_desc + col_qty + col_unit + col_tax, y0, col_total, row_h)

        # Description text (top padding)
        pdf.set_xy(x0 + 1.0, y0 + 1.5)
        for ln in lines:
            pdf.cell(col_desc - 2.0, line_h, _sanitize_text(ln), ln=1)
            pdf.set_x(x0 + 1.0)

        # Numeric columns (top padding)
        top_y = y0 + 1.5
        pdf.set_xy(x0 + col_desc, top_y)
        pdf.cell(col_qty - 1.5, line_h, _sanitize_text(f"{qty:g}"), align="R")

        pdf.set_xy(x0 + col_desc + col_qty, top_y)
        pdf.cell(col_unit - 1.5, line_h, _sanitize_text(_fmt_money_eur(unit_price)), align="R")

        pdf.set_xy(x0 + col_desc + col_qty + col_unit, top_y)
        pdf.cell(col_tax - 1.5, line_h, _sanitize_text(f"{tax_rate:.0f}%"), align="R")

        pdf.set_xy(x0 + col_desc + col_qty + col_unit + col_tax, top_y)
        pdf.cell(col_total - 1.5, line_h, _sanitize_text(_fmt_money_eur(total)), align="R")

        pdf.set_xy(x0, y0 + row_h)

    pdf.ln(4)

    # Totals
    totals = invoice.__dict__.get("totals")
    if not totals:
        net = sum(float(i.get("quantity", 0) or 0) * float(i.get("unit_price", 0) or 0) for i in items)
        tax = sum(
            (float(i.get("quantity", 0) or 0) * float(i.get("unit_price", 0) or 0)) * (float(i.get("tax_rate", 0) or 0) / 100.0)
            for i in items
        )
        gross = net + tax
        totals = {"net": net, "tax": tax, "gross": gross}

    is_small = bool(getattr(company, "is_small_business", False))

    label_w = pdf.usable_w * 0.70
    value_w = pdf.usable_w * 0.30

    if is_small:
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, _sanitize_text("Gemäß § 19 UStG wird keine Umsatzsteuer berechnet."))
        pdf.ln(1)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(label_w, 6, _sanitize_text("Gesamt"), align="R")
        pdf.cell(value_w, 6, _sanitize_text(_fmt_money_eur(float(totals["net"]))), align="R", ln=1)
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(label_w, 6, _sanitize_text("Zwischensumme"), align="R")
        pdf.cell(value_w, 6, _sanitize_text(_fmt_money_eur(float(totals["net"]))), align="R", ln=1)
        pdf.cell(label_w, 6, _sanitize_text("Umsatzsteuer"), align="R")
        pdf.cell(value_w, 6, _sanitize_text(_fmt_money_eur(float(totals["tax"]))), align="R", ln=1)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(label_w, 7, _sanitize_text("Gesamt"), align="R")
        pdf.cell(value_w, 7, _sanitize_text(_fmt_money_eur(float(totals["gross"]))), align="R", ln=1)

    payment_terms = str(getattr(invoice, "payment_terms", "") or "").strip()
    if payment_terms:
        pdf.ln(6)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, _sanitize_text(payment_terms))

    return bytes(pdf.output(dest="S"))
