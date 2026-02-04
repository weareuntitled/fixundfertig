from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date
import re
from typing import Any
import unicodedata

from renderer_interface import InvoiceRenderer
from services.invoice_pdf import render_invoice_to_pdf_bytes as render_invoice_to_pdf_bytes_reportlab

from fpdf import FPDF


def _usable_page_width(pdf: FPDF) -> float:
    epw = getattr(pdf, "epw", None)
    if epw:
        return float(epw)
    return float(pdf.w - pdf.l_margin - pdf.r_margin)


def _sanitize_text(text: Any) -> str:
    if text is None:
        return ""
    s = unicodedata.normalize("NFC", str(text))

    replacements = {
        "\u2013": "-",    # en dash
        "\u2014": "-",    # em dash
        "\u2018": "'",    # left single quote
        "\u2019": "'",    # right single quote
        "\u201c": '"',    # left double quote
        "\u201d": '"',    # right double quote
        "\u2026": "...",  # ellipsis
        "\u00a0": " ",    # nbsp
        "€": "EUR",       # avoid core-font issues
    }
    for k, v in replacements.items():
        s = s.replace(k, v)

    # Keep FPDF core fonts stable (latin-1)
    try:
        s.encode("latin-1")
        return s
    except UnicodeEncodeError:
        return s.encode("latin-1", "ignore").decode("latin-1")


def _wrap_pdf_text(text: Any, max_word_len: int = 30) -> str:
    s = _sanitize_text(text)
    if not s:
        return s
    tokens = re.split(r"(\s+)", s)
    out: list[str] = []
    for tok in tokens:
        if not tok or tok.isspace():
            out.append(tok)
            continue
        if len(tok) <= max_word_len:
            out.append(tok)
            continue
        chunks = [tok[i : i + max_word_len] for i in range(0, len(tok), max_word_len)]
        out.append(" ".join(chunks))
    return "".join(out)


def _get(obj: Any, *names: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        for n in names:
            if n in obj and obj[n] not in (None, ""):
                return obj[n]
        return default
    for n in names:
        if hasattr(obj, n):
            v = getattr(obj, n)
            if v not in (None, ""):
                return v
    return default


def _country_label(country_or_code: str) -> str:
    if not country_or_code:
        return ""
    c = str(country_or_code).strip()
    if c.upper() == "DE":
        return "Deutschland"
    return c


def _looks_like_invoice(x: Any) -> bool:
    if x is None:
        return False
    if isinstance(x, dict):
        return any(k in x for k in ("items", "positions", "customer", "title", "invoice_date"))
    return any(hasattr(x, k) for k in ("items", "positions", "customer", "title", "invoice_date"))


def _looks_like_company(x: Any) -> bool:
    if x is None:
        return False
    if isinstance(x, dict):
        return any(k in x for k in ("iban", "tax_id", "vat_id", "street", "zip", "city", "name"))
    return any(hasattr(x, k) for k in ("iban", "tax_id", "vat_id", "street", "zip", "city", "name"))


def format_customer_address_lines(customer: Any) -> list[str]:
    # Try a lot of common field names, because your model names may differ
    name = str(_get(customer, "name", "company_name", "company", "full_name", default="")).strip()

    street = str(
        _get(
            customer,
            "street",
            "street1",
            "address",
            "address1",
            "address_line1",
            "line1",
            "street_and_number",
            default="",
        )
    ).strip()

    street2 = str(
        _get(
            customer,
            "street2",
            "street_line2",
            "address2",
            "address_line2",
            "line2",
            default="",
        )
    ).strip()

    zip_code = str(_get(customer, "zip", "plz", "postal_code", "postcode", default="")).strip()
    city = str(_get(customer, "city", "town", "place", default="")).strip()
    country = str(_get(customer, "country", "country_name", "country_code", default="")).strip()

    lines: list[str] = []
    if name:
        lines.append(name)
    if street:
        lines.append(street)
    if street2:
        lines.append(street2)

    city_line = " ".join([p for p in (zip_code, city) if p]).strip()
    if city_line:
        lines.append(city_line)

    c_lbl = _country_label(country)
    if c_lbl:
        lines.append(c_lbl)

    return [ln for ln in lines if ln]


def format_company_address_lines(company: Any) -> list[str]:
    name = str(_get(company, "name", "company_name", default="")).strip()
    street = str(_get(company, "street", "street1", "address", "address1", default="")).strip()
    zip_code = str(_get(company, "zip", "plz", "postal_code", default="")).strip()
    city = str(_get(company, "city", default="")).strip()
    country = str(_get(company, "country", "country_code", default="")).strip()

    lines: list[str] = []
    if name:
        lines.append(name)
    if street:
        lines.append(street)

    city_line = " ".join([p for p in (zip_code, city) if p]).strip()
    if city_line:
        lines.append(city_line)

    c_lbl = _country_label(country)
    if c_lbl:
        lines.append(c_lbl)

    return [ln for ln in lines if ln]


@dataclass
class InvoiceItem:
    description: str
    quantity: float
    unit_price: float
    tax_rate: float = 0.0


class InvoicePDF(FPDF):
    def __init__(self, invoice: Any, company: Any) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.invoice = invoice
        self.company = company

        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(15, 15, 15)

        self._header_lines: list[str] = format_company_address_lines(company)

    def header(self) -> None:
        # Fix for: "Not enough horizontal space to render a single character"
        usable_w = _usable_page_width(self)

        self.set_font("Helvetica", size=9)
        self.set_text_color(90, 90, 90)

        for ln in self._header_lines:
            self.set_x(self.l_margin)  # critical
            self.multi_cell(usable_w, 4.5, _wrap_pdf_text(ln))

        self.ln(2)
        self.set_text_color(0, 0, 0)

    def _section_title(self, title: str) -> None:
        self.set_font("Helvetica", style="B", size=12)
        self.cell(0, 7, _sanitize_text(title), ln=1)
        self.ln(1)

    def render(self) -> bytes:
        self.add_page()

        title = _sanitize_text(_get(self.invoice, "title", default="Rechnung"))
        self.set_font("Helvetica", style="B", size=18)
        self.cell(0, 10, title, ln=1)
        self.ln(2)

        def _date_str(d: Any) -> str:
            if isinstance(d, date):
                return d.isoformat()
            return str(d) if d else ""

        inv_date = _date_str(_get(self.invoice, "invoice_date", default=""))
        service_from = _date_str(_get(self.invoice, "service_from", default=""))
        service_to = _date_str(_get(self.invoice, "service_to", default=""))

        self.set_font("Helvetica", size=10)
        date_label_width = 40
        date_value_width = max(_usable_page_width(self) - date_label_width, 10)

        if inv_date:
            self.set_font("Helvetica", style="B", size=10)
            self.cell(date_label_width, 5.5, "Rechnungsdatum:")
            self.set_font("Helvetica", size=10)
            self.multi_cell(date_value_width, 5.5, _wrap_pdf_text(inv_date))

        if service_from and service_to:
            service_s = f"{service_from} bis {service_to}"
        else:
            service_s = service_from or ""
        if service_s:
            self.set_font("Helvetica", style="B", size=10)
            self.cell(date_label_width, 5.5, "Leistungszeitraum:")
            self.set_font("Helvetica", size=10)
            self.multi_cell(date_value_width, 5.5, _wrap_pdf_text(service_s))

        self.ln(4)

        # Customer block, fixes your "only name and DE" symptom
        customer = _get(self.invoice, "customer", default={})
        cust_lines = format_customer_address_lines(customer)

        self._section_title("Kunde")
        self.set_font("Helvetica", size=10)
        for ln in cust_lines:
            self.set_x(self.l_margin)
            self.multi_cell(_usable_page_width(self), 5.0, _wrap_pdf_text(ln))

        self.ln(4)

        intro = _sanitize_text(_get(self.invoice, "intro_text", "intro", default=""))
        if intro:
            self.set_font("Helvetica", size=10)
            self.multi_cell(_usable_page_width(self), 5.2, _wrap_pdf_text(intro))
            self.ln(3)

        # Items
        items_raw = _get(self.invoice, "items", "positions", default=[])
        items: list[InvoiceItem] = []
        if isinstance(items_raw, list):
            for r in items_raw:
                items.append(
                    InvoiceItem(
                        description=_sanitize_text(_get(r, "description", default="")),
                        quantity=float(_get(r, "quantity", default=0) or 0),
                        unit_price=float(_get(r, "unit_price", default=0) or 0),
                        tax_rate=float(_get(r, "tax_rate", default=0) or 0),
                    )
                )

        self._section_title("Positionen")

        usable_w = _usable_page_width(self)
        w_desc = usable_w * 0.58
        w_qty = usable_w * 0.12
        w_unit = usable_w * 0.15
        w_tax = usable_w * 0.15

        self.set_font("Helvetica", style="B", size=10)
        self.cell(w_desc, 7, "Beschreibung", border=1)
        self.cell(w_qty, 7, "Menge", border=1, align="R")
        self.cell(w_unit, 7, "Preis", border=1, align="R")
        self.cell(w_tax, 7, "USt", border=1, align="R")
        self.ln()

        self.set_font("Helvetica", size=10)
        subtotal = 0.0
        tax_total = 0.0

        for it in items:
            line_total = it.quantity * it.unit_price
            line_tax = line_total * (it.tax_rate / 100.0)
            subtotal += line_total
            tax_total += line_tax

            y0 = self.get_y()
            x0 = self.get_x()

            self.multi_cell(w_desc, 6, _wrap_pdf_text(it.description), border=1)
            y1 = self.get_y()
            row_h = y1 - y0

            self.set_xy(x0 + w_desc, y0)
            self.cell(w_qty, row_h, _sanitize_text(f"{it.quantity:g}"), border=1, align="R")
            self.cell(w_unit, row_h, _sanitize_text(f"{it.unit_price:.2f}"), border=1, align="R")
            self.cell(w_tax, row_h, _sanitize_text(f"{it.tax_rate:g}%"), border=1, align="R")
            self.ln(row_h)

        self.ln(4)

        show_tax = bool(_get(self.invoice, "show_tax", default=False))

        self.set_font("Helvetica", style="B", size=11)
        self.cell(0, 6, _sanitize_text(f"Zwischensumme: {subtotal:.2f} EUR"), ln=1)

        if show_tax:
            self.set_font("Helvetica", size=10)
            self.cell(0, 6, _sanitize_text(f"USt: {tax_total:.2f} EUR"), ln=1)
            total = subtotal + tax_total
        else:
            total = subtotal

        self.set_font("Helvetica", style="B", size=12)
        self.cell(0, 7, _sanitize_text(f"Gesamt: {total:.2f} EUR"), ln=1)

        if not show_tax:
            note = _sanitize_text(
                _get(
                    self.invoice,
                    "kleinunternehmer_note",
                    default="Als Kleinunternehmer im Sinne von § 19 UStG wird keine Umsatzsteuer berechnet.",
                )
            )
            if note:
                self.ln(3)
                self.set_font("Helvetica", size=9)
                self.set_text_color(90, 90, 90)
                self.multi_cell(_usable_page_width(self), 4.5, _wrap_pdf_text(note))
                self.set_text_color(0, 0, 0)

        out = self.output(dest="S")
        if isinstance(out, (bytes, bytearray)):
            return bytes(out)
        return out.encode("latin-1")


class PDFInvoiceRenderer(InvoiceRenderer):
    def render(self, invoice: Any, template_id: str | None = None) -> bytes:
        company = None
        customer = None
        if isinstance(invoice, dict):
            company = invoice.get("company")
            customer = invoice.get("customer")
        else:
            company = getattr(invoice, "company", None)

        return render_invoice_to_pdf_bytes_reportlab(invoice, company=company, customer=customer)


def render_invoice_pdf_bytes(invoice: Any, company: Any) -> bytes:
    return render_invoice_to_pdf_bytes_reportlab(invoice, company=company)


def render_invoice_pdf_base64(invoice: Any, company: Any) -> str:
    return base64.b64encode(render_invoice_pdf_bytes(invoice, company)).decode("ascii")


# Compatibility: your codebase expects these names
def render_invoice_to_pdf_bytes(*args, **kwargs) -> bytes:
    """
    Accepts (invoice, company) or (company, invoice).
    """
    if "invoice" in kwargs or "company" in kwargs or "customer" in kwargs:
        return render_invoice_to_pdf_bytes_reportlab(
            kwargs.get("invoice"),
            company=kwargs.get("company"),
            customer=kwargs.get("customer"),
        )

    if len(args) >= 2:
        a, b = args[0], args[1]
        if _looks_like_invoice(a) and _looks_like_company(b):
            return render_invoice_to_pdf_bytes_reportlab(a, company=b)
        if _looks_like_company(a) and _looks_like_invoice(b):
            return render_invoice_to_pdf_bytes_reportlab(b, company=a)
        return render_invoice_to_pdf_bytes_reportlab(a, company=b)

    if len(args) == 1:
        invoice = args[0]
        company = invoice.get("company") if isinstance(invoice, dict) else getattr(invoice, "company", None)
        customer = invoice.get("customer") if isinstance(invoice, dict) else getattr(invoice, "customer", None)
        return render_invoice_to_pdf_bytes_reportlab(invoice, company=company, customer=customer)

    raise TypeError("render_invoice_to_pdf_bytes needs at least (invoice, company)")


def render_invoice_to_pdf_base64(*args, **kwargs) -> str:
    return base64.b64encode(render_invoice_to_pdf_bytes(*args, **kwargs)).decode("ascii")
