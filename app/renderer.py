from fpdf import FPDF
import os
from pathlib import Path
from sqlmodel import Session, select
from data import Company, Customer, Invoice, InvoiceItem, engine


def _sanitize_pdf_text(value: str) -> str:
    return value.replace("€", "EUR")


class PDFInvoice(FPDF):
    def __init__(self, company):
        super().__init__(format="A4", unit="mm")
        self.company = company
        font_path = Path(__file__).resolve().parent / "assets" / "fonts" / "DejaVuSans.ttf"
        if not font_path.exists():
            raise FileNotFoundError(f"Missing font file: {font_path}")
        self.add_font("DejaVu", "", str(font_path), uni=True)
        self.add_font("DejaVu", "B", str(font_path), uni=True)
        self.set_auto_page_break(auto=True, margin=35)
        self.set_margins(20, 20, 20)
        self.alias_nb_pages()

    def header(self):
        # Logo Check
        logo_path = "./storage/logo.png"
        if os.path.exists(logo_path):
            try:
                # x=20 (links), y=15, w=35mm
                self.image(logo_path, x=20, y=15, w=35)
            except:
                pass # Falls Bild defekt, ignorieren
        else:
            # Fallback: Firmenname groß
            if self.company:
                self.set_font("DejaVu", size=14, style="B")
                self.set_xy(20, 20)
                self.multi_cell(80, 8, self.company.name, align="L")

    def footer(self):
        if not self.company: return
        self.set_y(-35)
        self.set_font("DejaVu", size=8)

        bank_details = []
        if self.company and self.company.iban:
            bank_details.append(_sanitize_pdf_text(f"IBAN: {self.company.iban}"))
        if self.company and self.company.tax_id:
            bank_details.append(_sanitize_pdf_text(f"St-Nr: {self.company.tax_id}"))
        if self.company and self.company.vat_id:
            bank_details.append(_sanitize_pdf_text(f"USt-IdNr: {self.company.vat_id}"))
        if bank_details:
            self.multi_cell(0, 4, _sanitize_pdf_text(" | ".join(bank_details)), align="L")
        self.cell(0, 4, _sanitize_pdf_text(f"Seite {self.page_no()}"), align="R")


def render_invoice_to_pdf_bytes(invoice: Invoice) -> bytes:
    # Daten laden
    with Session(engine) as session:
        company = session.exec(select(Company)).first() or Company()
        customer = session.get(Customer, invoice.customer_id) if invoice.customer_id else None
    return company, customer


def _load_company_customer(invoice: Invoice):
    # Daten laden
    with Session(engine) as session:
        company = session.exec(select(Company)).first() or Company()
        customer = session.get(Customer, invoice.customer_id) if invoice.customer_id else None
    return company, customer


def _collect_line_items(invoice: Invoice):
    preview_items = invoice.__dict__.get('line_items')
    if preview_items is not None:
        return preview_items
    if not invoice.id:
        return []
    with Session(engine) as session:
        return session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id)).all()


def _derive_tax_rate(invoice: Invoice, line_items):
    stored_tax_rate = invoice.__dict__.get('tax_rate')
    if stored_tax_rate is not None:
        return float(stored_tax_rate)
    return 0.19


def _prepare_items(invoice: Invoice, company: Company | None = None):
    raw_items = _collect_line_items(invoice)
    tax_rate = _derive_tax_rate(invoice, raw_items)
    if company and company.is_small_business:
        tax_rate = 0.0
    prepared = []
    net_total = 0.0
    for item in raw_items:
        if isinstance(item, dict):
            desc = item.get('desc') or item.get('description') or ''
            qty = float(item.get('qty') or item.get('quantity') or 0)
            price = float(item.get('price') or item.get('unit_price') or 0)
            is_brutto = bool(item.get('is_brutto') or False)
        else:
            desc = item.description or ''
            qty = float(item.quantity or 0)
            price = float(item.unit_price or 0)
            is_brutto = False

        unit_netto = price
        if tax_rate > 0 and is_brutto:
            unit_netto = price / (1 + tax_rate)

        total = qty * unit_netto
        net_total += total
        prepared.append({
            'description': desc,
            'quantity': qty,
            'unit_price': unit_netto,
            'total': total,
        })

    if tax_rate == 0:
        brutto = net_total
        tax_amount = 0.0
    else:
        brutto = float(invoice.total_brutto or 0) or (net_total * (1 + tax_rate))
        tax_amount = brutto - net_total
    return prepared, {'netto': net_total, 'brutto': brutto, 'tax_rate': tax_rate, 'tax_amount': tax_amount}


def render_invoice_to_pdf_bytes(invoice: Invoice) -> bytes:
    layout = {
        "totals_label_x": 95,
        "totals_value_x": 145,
    }
    company, customer = _load_company_customer(invoice)
    line_items, totals = _prepare_items(invoice, company)
    is_small_business = bool(company and company.is_small_business)
    show_vat = not is_small_business and totals["tax_rate"] > 0

    recipient_name = _sanitize_pdf_text(invoice.recipient_name or (customer.display_name if customer else ''))
    recipient_street = _sanitize_pdf_text(invoice.recipient_street or (customer.strasse if customer else ''))
    recipient_postal = _sanitize_pdf_text(invoice.recipient_postal_code or (customer.plz if customer else ''))
    recipient_city = _sanitize_pdf_text(invoice.recipient_city or (customer.ort if customer else ''))

    pdf = PDFInvoice(company)
    pdf.add_page()

    pdf.set_xy(120, 18)
    pdf.set_font("DejaVu", size=18, style="B")
    pdf.cell(70, 8, _sanitize_pdf_text(invoice.title or "Rechnung"), align="R")

    pdf.set_xy(120, 30)
    pdf.set_font("DejaVu", size=9)
    info_lines = [
        _sanitize_pdf_text(f"Rechnung Nr: {invoice.nr or ''}"),
        _sanitize_pdf_text(f"Datum: {invoice.date}"),
    ]
    if invoice.delivery_date:
        info_lines.append(_sanitize_pdf_text(f"Lieferdatum: {invoice.delivery_date}"))
    if customer and customer.kdnr:
        info_lines.append(_sanitize_pdf_text(f"Kundennr: {customer.kdnr}"))
    pdf.multi_cell(70, 4.5, _sanitize_pdf_text("\n".join(info_lines)), align="R")

    pdf.set_xy(20, 50)
    pdf.set_font("DejaVu", size=9, style="B")
    pdf.cell(0, 5, _sanitize_pdf_text("Von"))
    company_lines = []
    if company:
        company_lines = [
            _sanitize_pdf_text(company.name),
            _sanitize_pdf_text(f"{company.first_name} {company.last_name}".strip()),
            _sanitize_pdf_text(company.street),
            _sanitize_pdf_text(f"{company.postal_code} {company.city}".strip()),
        ]
        if company.email:
            company_lines.append(_sanitize_pdf_text(company.email))
        if company.phone:
            company_lines.append(_sanitize_pdf_text(company.phone))
    pdf.set_xy(20, 56)
    pdf.set_font("DejaVu", size=9)
    pdf.multi_cell(80, 4.5, _sanitize_pdf_text("\n".join(line for line in company_lines if line)))

    pdf.set_xy(120, 50)
    pdf.set_font("DejaVu", size=9, style="B")
    pdf.cell(0, 5, _sanitize_pdf_text("Rechnung an"))
    recipient_lines = [
        recipient_name,
        recipient_street,
        f"{recipient_postal} {recipient_city}".strip(),
    ]
    pdf.set_xy(120, 56)
    pdf.set_font("DejaVu", size=9)
    pdf.multi_cell(70, 4.5, _sanitize_pdf_text("\n".join(line for line in recipient_lines if line)))

    pdf.set_xy(20, 95)
    pdf.set_font("DejaVu", size=10)
    pdf.multi_cell(0, 5, _sanitize_pdf_text("Vielen Dank für Ihren Auftrag. Nachfolgend finden Sie die Rechnung."))

    pdf.ln(2)
    table_start_x = 20
    table_widths = [80, 20, 35, 35]
    pdf.set_x(table_start_x)
    pdf.set_font("DejaVu", size=9, style="B")
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(table_widths[0], 7, "Beschreibung", fill=True)
    pdf.cell(table_widths[1], 7, "Menge", align="R", fill=True)
    pdf.cell(table_widths[2], 7, "Einzelpreis", align="R", fill=True)
    pdf.cell(table_widths[3], 7, "Gesamt", align="R", fill=True, ln=1)

    pdf.set_font("DejaVu", size=9)
    for item in line_items:
        pdf.set_x(table_start_x)
        pdf.cell(table_widths[0], 6, _sanitize_pdf_text(item['description']))
        pdf.cell(table_widths[1], 6, f"{item['quantity']:.2f}", align="R")
        pdf.cell(table_widths[2], 6, _sanitize_pdf_text(f"{item['unit_price']:.2f} EUR"), align="R")
        pdf.cell(table_widths[3], 6, _sanitize_pdf_text(f"{item['total']:.2f} EUR"), align="R", ln=1)

    pdf.ln(4)
    totals_label_x = layout["totals_label_x"]
    totals_value_x = layout["totals_value_x"]
    pdf.set_font("DejaVu", size=10)
    pdf.set_xy(totals_label_x, pdf.get_y())
    pdf.cell(40, 5, "Zwischensumme", align="R")
    pdf.set_xy(totals_value_x, pdf.get_y())
    pdf.cell(30, 5, _sanitize_pdf_text(f"{totals['netto']:.2f} EUR"), align="R", ln=1)

    if show_vat:
        pdf.set_xy(totals_label_x, pdf.get_y())
        pdf.cell(40, 5, f"USt. ({totals['tax_rate'] * 100:.0f}%)", align="R")
        pdf.set_xy(totals_value_x, pdf.get_y())
        pdf.cell(30, 5, _sanitize_pdf_text(f"{totals['tax_amount']:.2f} EUR"), align="R", ln=1)

    pdf.set_font("DejaVu", size=10, style="B")
    pdf.set_xy(totals_label_x, pdf.get_y())
    pdf.cell(40, 6, "Gesamt", align="R")
    pdf.set_xy(totals_value_x, pdf.get_y())
    pdf.cell(30, 6, _sanitize_pdf_text(f"{totals['brutto']:.2f} EUR"), align="R", ln=1)

    if is_small_business:
        pdf.ln(2)
        pdf.set_font("DejaVu", size=9)
        pdf.multi_cell(0, 4, _sanitize_pdf_text("Kleinunternehmerregelung gemäß § 19 UStG."))

    output = pdf.output(dest="S")
    if isinstance(output, str):
        output = output.encode("latin-1")
    elif isinstance(output, bytearray):
        output = bytes(output)
    return output
