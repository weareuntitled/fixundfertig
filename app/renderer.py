from fpdf import FPDF
from sqlmodel import Session, select
from data import Company, Customer, Invoice, InvoiceItem, engine
import os

class PDFInvoice(FPDF):
    def __init__(self, company):
        super().__init__(format="A4", unit="mm")
        self.company = company
        self.set_auto_page_break(auto=True, margin=35)
        self.set_margins(20, 20, 20)
        self.alias_nb_pages()

    def header(self):
        # Logo Check
        logo_path = "./storage/logo.png"
        if os.path.exists(logo_path):
            try:
                # x=150 (rechts), y=15, w=40mm
                self.image(logo_path, x=150, y=15, w=40)
            except:
                pass # Falls Bild defekt, ignorieren
        else:
            # Fallback: Firmenname groß
            if self.company:
                self.set_font("Helvetica", "B", 20)
                self.set_xy(120, 20)
                self.multi_cell(70, 8, self.company.name, align="R")

        # Falzmarken
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.1)
        self.line(0, 105, 7, 105)
        self.line(0, 148.5, 10, 148.5)
        self.line(0, 210, 7, 210)

        # Absenderzeile (Klein)
        if self.company:
            self.set_xy(20, 45)
            self.set_font("Helvetica", size=7)
            self.set_text_color(100, 100, 100)
            line = f"{self.company.name} | {self.company.street} | {self.company.postal_code} {self.company.city}"
            self.cell(85, 4, line, border="B")

    def footer(self):
        if not self.company: return
        self.set_y(-35)
        self.set_font("Helvetica", size=8)
        self.set_text_color(100, 100, 100)
        
        # 3 Spalten Layout für Footer
        # Wir nutzen feste X-Positionen
        y = self.get_y()
        
        # Spalte 1: Adresse
        self.set_xy(20, y)
        self.multi_cell(50, 4, f"{self.company.name}\n{self.company.street}\n{self.company.postal_code} {self.company.city}", align="L")
        
        # Spalte 2: Kontakt
        self.set_xy(80, y)
        c_info = []
        if self.company.phone: c_info.append(f"Tel: {self.company.phone}")
        if self.company.email: c_info.append(f"Mail: {self.company.email}")
        if self.company.vat_id: c_info.append(f"USt-Id: {self.company.vat_id}")
        self.multi_cell(60, 4, "\n".join(c_info), align="C")
        
        # Spalte 3: Bank
        self.set_xy(150, y)
        b_info = []
        if self.company.iban: b_info.append(f"IBAN: {self.company.iban}")
        if self.company.tax_id: b_info.append(f"St-Nr: {self.company.tax_id}")
        self.multi_cell(40, 4, "\n".join(b_info), align="R")

        # Seitenzahl
        self.set_y(-10)
        self.cell(0, 10, f"Seite {self.page_no()}/{{nb}}", align="C")

def render_invoice_to_pdf_bytes(invoice: Invoice) -> bytes:
    # Daten laden
    with Session(engine) as session:
        company = session.exec(select(Company)).first() or Company()
        customer = session.get(Customer, invoice.customer_id) if invoice.customer_id else None
        
        # Items laden (Memory oder DB)
        items = invoice.__dict__.get('line_items')
        if not items and invoice.id:
            db_items = session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id)).all()
            items = [{'desc': i.description, 'qty': i.quantity, 'price': i.unit_price, 'is_brutto': False} for i in db_items]
        if not items: items = []

    pdf = PDFInvoice(company)
    pdf.add_page()
    
    # 1. Empfänger
    pdf.set_xy(20, 52)
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(0, 0, 0)
    
    r_name = invoice.recipient_name or (customer.display_name if customer else '')
    r_street = invoice.recipient_street or (customer.strasse if customer else '')
    r_city = f"{invoice.recipient_postal_code} {invoice.recipient_city}".strip()
    if not r_city.strip() and customer: 
        r_city = f"{customer.plz} {customer.ort}".strip()
    
    pdf.multi_cell(85, 5, f"{r_name}\n{r_street}\n{r_city}")

    # 2. Info Block (Rechts)
    pdf.set_xy(125, 50)
    pdf.set_font("Helvetica", size=9)
    # Kleiner Trick für saubere Ausrichtung: Label fett, Wert normal
    def info_line(label, val):
        x = pdf.get_x()
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(35, 6, label)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(40, 6, str(val), align="R", ln=1)
        pdf.set_x(x)
    
    info_line("Datum:", invoice.date)
    info_line("Rechnung Nr.:", invoice.nr if invoice.nr else "ENTWURF")
    if customer and customer.kdnr:
        info_line("Kunden-Nr.:", customer.kdnr)
    info_line("Lieferdatum:", invoice.delivery_date)

    # 3. Titel
    pdf.set_xy(20, 95)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, invoice.title or "Rechnung", ln=1)
    
    pdf.set_font("Helvetica", size=10)
    pdf.ln(2)
    pdf.multi_cell(0, 5, "Vielen Dank für Ihren Auftrag. Wir stellen folgende Leistungen in Rechnung:")
    pdf.ln(8)

    # 4. Tabelle
    # Spaltenbreiten (Summe = 170mm Nutzbreite)
    # Beschreibung | Menge | Einzel | Gesamt
    w_desc = 85
    w_qty = 20
    w_price = 30
    w_total = 35
    
    # Header
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(245, 245, 245)
    pdf.cell(w_desc, 8, "Beschreibung", 0, 0, 'L', True)
    pdf.cell(w_qty, 8, "Menge", 0, 0, 'C', True)
    pdf.cell(w_price, 8, "Einzelpreis", 0, 0, 'R', True)
    pdf.cell(w_total, 8, "Gesamt", 0, 1, 'R', True)
    
    # Rows
    pdf.set_font("Helvetica", size=9)
    
    tax_rate = invoice.__dict__.get('tax_rate', 0.19)
    netto_sum = 0.0
    
    for item in items:
        # Daten Normalisieren
        desc = item.get('desc', '') if isinstance(item, dict) else item.description
        qty = float(item.get('qty', 0)) if isinstance(item, dict) else float(item.quantity)
        price = float(item.get('price', 0)) if isinstance(item, dict) else float(item.unit_price)
        is_brutto = item.get('is_brutto', False) if isinstance(item, dict) else False
        
        # Netto Berechnen
        unit_net = price
        if tax_rate > 0 and is_brutto:
            unit_net = price / (1 + tax_rate)
        
        line_total = qty * unit_net
        netto_sum += line_total
        
        # MultiCell für Beschreibung (damit sie umbricht und nicht zu breit ist)
        # Wir müssen die maximale Höhe der Zeile berechnen
        
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        # Page Break Check (grob)
        if y_start > 250:
            pdf.add_page()
            y_start = pdf.get_y()
            x_start = pdf.get_x()

        # Wir drucken die Beschreibung zuerst, um die Höhe zu kennen
        pdf.multi_cell(w_desc, 6, desc, align='L')
        y_end = pdf.get_y()
        row_height = y_end - y_start
        
        # Cursor zurück für die anderen Spalten
        pdf.set_xy(x_start + w_desc, y_start)
        
        # Menge
        pdf.cell(w_qty, row_height, f"{qty:.2f}", 0, 0, 'C')
        # Einzel
        pdf.cell(w_price, row_height, f"{unit_net:,.2f} €", 0, 0, 'R')
        # Gesamt
        pdf.cell(w_total, row_height, f"{line_total:,.2f} €", 0, 1, 'R')
        
        # Linie unten (optional, hier weggelassen für cleaner look, oder:)
        pdf.set_draw_color(240, 240, 240)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())

    # 5. Summen
    pdf.ln(5)
    # Check Page Break
    if pdf.get_y() > 240: pdf.add_page()

    x_val = 120
    w_lbl = 35
    w_res = 35
    
    pdf.set_x(x_val)
    pdf.cell(w_lbl, 6, "Netto:", 0, 0, 'R')
    pdf.cell(w_res, 6, f"{netto_sum:,.2f} EUR", 0, 1, 'R')
    
    tax_amount = netto_sum * tax_rate
    final_total = netto_sum + tax_amount
    
    if tax_rate > 0:
        pdf.set_x(x_val)
        pdf.cell(w_lbl, 6, f"USt ({tax_rate*100:.0f}%):", 0, 0, 'R')
        pdf.cell(w_res, 6, f"{tax_amount:,.2f} EUR", 0, 1, 'R')
    
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_x(x_val)
    # Strich
    pdf.line(x_val+10, pdf.get_y(), 190, pdf.get_y())
    
    pdf.cell(w_lbl, 10, "Gesamtbetrag:", 0, 0, 'R')
    pdf.cell(w_res, 10, f"{final_total:,.2f} EUR", 0, 1, 'R')
    
    # Kleinunternehmer
    if tax_rate == 0:
        pdf.ln(5)
        pdf.set_font("Helvetica", size=8)
        pdf.multi_cell(0, 5, "Es erfolgt kein Ausweis der Umsatzsteuer aufgrund der Anwendung der Kleinunternehmerregelung gem. § 19 UStG.")

    return bytes(pdf.output())