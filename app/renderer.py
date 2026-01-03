from fpdf import FPDF
from sqlmodel import Session, select

from data import Company, Customer, Invoice, InvoiceItem, engine


def _sanitize_pdf_text(value: str) -> str:
    return value.replace("€", "EUR")


class PDFInvoice(FPDF):
    def __init__(self, company: Company | None):
        super().__init__(format="A4", unit="mm")
        self.company = company
        self.set_auto_page_break(auto=True, margin=25)
        self.set_margins(20, 20, 20)

    def header(self):
        self.set_draw_color(60, 60, 60)
        self.line(0, 105, 5, 105)
        self.line(0, 210, 5, 210)

        self.set_draw_color(200, 200, 200)
        self.rect(20, 45, 85, 45)

        if not self.company:
            return

        self.set_font("Helvetica", size=9)
        self.set_xy(120, 20)
        header_lines = [
            _sanitize_pdf_text(f"{self.company.name}"),
            _sanitize_pdf_text(f"{self.company.first_name} {self.company.last_name}".strip()),
            _sanitize_pdf_text(f"{self.company.street}"),
            _sanitize_pdf_text(f"{self.company.postal_code} {self.company.city}".strip()),
        ]
        if self.company.email:
            header_lines.append(_sanitize_pdf_text(self.company.email))
        if self.company.phone:
            header_lines.append(_sanitize_pdf_text(self.company.phone))
        if self.company.iban:
            header_lines.append(_sanitize_pdf_text(f"IBAN: {self.company.iban}"))
        if self.company.tax_id:
            header_lines.append(_sanitize_pdf_text(f"St-Nr: {self.company.tax_id}"))
        if self.company.vat_id:
            header_lines.append(_sanitize_pdf_text(f"USt-IdNr: {self.company.vat_id}"))

        header_text = "\n".join(line for line in header_lines if line)
        self.multi_cell(0, 4, _sanitize_pdf_text(header_text), align="R")

    def footer(self):
        self.set_y(-25)
        self.set_font("Helvetica", size=8)

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


def _load_company_customer(invoice: Invoice):
    with Session(engine) as session:
        company = session.exec(select(Company)).first()
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


def _prepare_items(invoice: Invoice):
    raw_items = _collect_line_items(invoice)
    tax_rate = _derive_tax_rate(invoice, raw_items)
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

    brutto = float(invoice.total_brutto or 0) or (net_total * (1 + tax_rate))
    tax_amount = brutto - net_total
    return prepared, {'netto': net_total, 'brutto': brutto, 'tax_rate': tax_rate, 'tax_amount': tax_amount}


def render_invoice_to_pdf_bytes(invoice: Invoice) -> bytes:
    company, customer = _load_company_customer(invoice)
    line_items, totals = _prepare_items(invoice)

    recipient_name = _sanitize_pdf_text(invoice.recipient_name or (customer.display_name if customer else ''))
    recipient_street = _sanitize_pdf_text(invoice.recipient_street or (customer.strasse if customer else ''))
    recipient_postal = _sanitize_pdf_text(invoice.recipient_postal_code or (customer.plz if customer else ''))
    recipient_city = _sanitize_pdf_text(invoice.recipient_city or (customer.ort if customer else ''))

    pdf = PDFInvoice(company)
    pdf.add_page()

    return_address = ''
    if company:
        return_address = _sanitize_pdf_text(
            f"{company.name} · {company.street} · {company.postal_code} {company.city}".strip()
        )

    pdf.set_xy(20, 45)
    pdf.set_font("Helvetica", size=8, style="U")
    pdf.cell(85, 4, _sanitize_pdf_text(return_address))

    pdf.set_xy(20, 50)
    pdf.set_font("Helvetica", size=10)
    recipient_lines = [
        recipient_name,
        recipient_street,
        f"{recipient_postal} {recipient_city}".strip(),
    ]
    pdf.multi_cell(85, 5, _sanitize_pdf_text("\n".join(line for line in recipient_lines if line)))

    pdf.set_xy(125, 65)
    pdf.set_font("Helvetica", size=9)
    info_lines = [
        _sanitize_pdf_text(f"Datum: {invoice.date}"),
        _sanitize_pdf_text(f"Rechnung Nr: {invoice.nr or ''}"),
    ]
    if customer and customer.kdnr:
        info_lines.append(_sanitize_pdf_text(f"Kundennr: {customer.kdnr}"))
    pdf.multi_cell(60, 4.5, _sanitize_pdf_text("\n".join(info_lines)))

    pdf.set_xy(20, 105)
    pdf.set_font("Helvetica", size=14, style="B")
    pdf.cell(0, 8, _sanitize_pdf_text(invoice.title or "Rechnung"), ln=1)
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(0, 5, _sanitize_pdf_text("Vielen Dank für Ihren Auftrag. Nachfolgend finden Sie die Rechnung."))

    pdf.ln(3)
    table_start_x = 20
    table_widths = [80, 20, 35, 35]
    pdf.set_x(table_start_x)
    pdf.set_font("Helvetica", size=9, style="B")
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(table_widths[0], 7, "Beschreibung", fill=True)
    pdf.cell(table_widths[1], 7, "Menge", align="R", fill=True)
    pdf.cell(table_widths[2], 7, "Einzelpreis", align="R", fill=True)
    pdf.cell(table_widths[3], 7, "Gesamt", align="R", fill=True, ln=1)

    pdf.set_font("Helvetica", size=9)
    for item in line_items:
        pdf.set_x(table_start_x)
        pdf.cell(table_widths[0], 6, _sanitize_pdf_text(item['description']))
        pdf.cell(table_widths[1], 6, f"{item['quantity']:.2f}", align="R")
        pdf.cell(table_widths[2], 6, _sanitize_pdf_text(f"{item['unit_price']:.2f} EUR"), align="R")
        pdf.cell(table_widths[3], 6, _sanitize_pdf_text(f"{item['total']:.2f} EUR"), align="R", ln=1)

    pdf.ln(4)
    totals_label_x = 120
    totals_value_x = 170
    pdf.set_font("Helvetica", size=10)
    pdf.set_xy(totals_label_x, pdf.get_y())
    pdf.cell(40, 5, "Zwischensumme", align="R")
    pdf.set_xy(totals_value_x, pdf.get_y())
    pdf.cell(30, 5, _sanitize_pdf_text(f"{totals['netto']:.2f} EUR"), align="R", ln=1)

    pdf.set_xy(totals_label_x, pdf.get_y())
    pdf.cell(40, 5, f"USt. ({totals['tax_rate'] * 100:.0f}%)", align="R")
    pdf.set_xy(totals_value_x, pdf.get_y())
    pdf.cell(30, 5, _sanitize_pdf_text(f"{totals['tax_amount']:.2f} EUR"), align="R", ln=1)

    pdf.set_font("Helvetica", size=10, style="B")
    pdf.set_xy(totals_label_x, pdf.get_y())
    pdf.cell(40, 6, "Gesamt", align="R")
    pdf.set_xy(totals_value_x, pdf.get_y())
    pdf.cell(30, 6, _sanitize_pdf_text(f"{totals['brutto']:.2f} EUR"), align="R", ln=1)

    output = pdf.output(dest="S")
    if isinstance(output, bytearray):
        return bytes(output)
    if isinstance(output, str):
        return output.encode("latin-1")
    return output
