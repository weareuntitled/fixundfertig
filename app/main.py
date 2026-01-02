from nicegui import ui, app, events
from sqlmodel import Field, Session, SQLModel, create_engine, select, Relationship
from typing import Optional, List
from datetime import datetime
import pandas as pd
import io
import os
from fpdf import FPDF

# --- STYLE SYSTEM ---
C_BG = "bg-slate-50 min-h-screen"
C_CONTAINER = "w-full max-w-7xl mx-auto p-6 gap-6"
C_CARD = "bg-white border border-slate-200 rounded-xl shadow-[0_2px_4px_rgba(0,0,0,0.02)]"
C_BTN_PRIM = "bg-slate-900 text-white hover:bg-slate-800 rounded-lg px-4 py-2 text-sm font-medium shadow-sm transition-all"
C_BTN_SEC = "bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 rounded-lg px-4 py-2 text-sm font-medium shadow-sm transition-all"
C_INPUT = "border-slate-200 bg-white rounded-lg text-sm px-3 py-2 outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 w-full transition-all"
C_BADGE_GREEN = "bg-emerald-50 text-emerald-700 border border-emerald-100 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_BLUE = "bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_GRAY = "bg-slate-100 text-slate-600 border border-slate-200 px-2 py-0.5 rounded-full text-xs font-medium text-center"

# --- DB MODELLE ---
class Company(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = "DanEP"
    iban: str = ""
    tax_id: str = ""
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    next_invoice_nr: int = 10000

class Customer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id")
    kdnr: int
    name: str
    vorname: str = ""
    nachname: str = ""
    email: str = ""
    strasse: str = ""
    plz: str = ""
    ort: str = ""
    
    @property
    def display_name(self):
        if self.name: return self.name
        return f"{self.vorname} {self.nachname}".strip()

class Invoice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id")
    nr: Optional[int] = None 
    date: str
    total_brutto: float
    status: str = "Entwurf"

class InvoiceItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id")
    description: str
    quantity: float
    unit_price: float

class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id")
    date: str
    category: str
    description: str
    amount: float

os.makedirs('./storage', exist_ok=True)
os.makedirs('./storage/invoices', exist_ok=True)
engine = create_engine("sqlite:///storage/database.db")
SQLModel.metadata.create_all(engine)

def ensure_company_schema():
    with engine.connect() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(company)").fetchall()}
        if "tax_id" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN tax_id TEXT DEFAULT ''")
        if "smtp_server" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN smtp_server TEXT DEFAULT ''")
        if "smtp_port" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN smtp_port INTEGER DEFAULT 587")
        if "smtp_user" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN smtp_user TEXT DEFAULT ''")
        if "smtp_password" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN smtp_password TEXT DEFAULT ''")
        if "next_invoice_nr" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN next_invoice_nr INTEGER DEFAULT 10000")

ensure_company_schema()

# --- IMPORT LOGIC ---
def process_customer_import(content, session, comp_id):
    try: df = pd.read_csv(io.BytesIO(content))
    except: 
        try: df = pd.read_excel(io.BytesIO(content))
        except: return 0, "Format Error"
    count = 0
    for _, row in df.iterrows():
        try:
            kdnr = row.get('Kundennummer') or row.get('Nr') or 0
            if not kdnr: continue
            firma = str(row.get('Firmenname', ''))
            if str(firma) == 'nan': firma = ""
            
            exists = session.exec(select(Customer).where(Customer.kdnr == int(kdnr))).first()
            if not exists:
                c = Customer(
                    company_id=comp_id, kdnr=int(kdnr), 
                    name=firma,
                    vorname=str(row.get('Vorname', '')).replace('nan',''),
                    nachname=str(row.get('Nachname', '')).replace('nan',''),
                    email=str(row.get('E-Mail', '')).replace('nan',''),
                    strasse=str(row.get('1. Adresszeile', '')).replace('nan',''),
                    plz=str(row.get('Postleitzahl', '')).replace('nan',''),
                    ort=str(row.get('Ort', '')).replace('nan','')
                )
                session.add(c)
                count += 1
        except: continue
    session.commit()
    return count, ""

def process_expense_import(content, session, comp_id):
    try: df = pd.read_csv(io.BytesIO(content))
    except: return 0, "Format Error"
    count = 0
    for _, row in df.iterrows():
        try:
            desc = f"{row.get('Lieferant', '')} {row.get('Bemerkung', '')}".replace('nan','').strip()
            exp = Expense(
                company_id=comp_id, date=str(row.get('Datum', '')),
                category=str(row.get('Kategorie', 'Import')),
                description=desc, 
                amount=float(str(row.get('Betrag brutto', 0)).replace(',','.'))
            )
            session.add(exp)
            count += 1
        except: continue
    session.commit()
    return count, ""

# --- UI LOGIC ---

def layout_wrapper(content_func):
    # HEADER
    with ui.header().classes('bg-white border-b border-slate-200 h-16 px-6 flex items-center justify-between sticky top-0 z-50'):
        with ui.row().classes('items-center gap-3'):
            with ui.element('div').classes('bg-slate-900 text-white p-1.5 rounded-lg'):
                ui.icon('bolt', size='xs')
            ui.label('FixundFertig').classes('font-bold text-slate-900 tracking-tight')
        
        with ui.row().classes('gap-1'):
            def nav_item(label, target, icon):
                active = app.storage.user.get('page', 'dashboard') == target
                color = "bg-slate-100 text-slate-900" if active else "text-slate-500 hover:text-slate-700 hover:bg-slate-50"
                with ui.button(on_click=lambda: set_page(target)).classes(f"flat {color} px-3 py-1.5 rounded-md transition-all no-shadow border-0"):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon(icon, size='xs')
                        ui.label(label).classes('text-sm font-medium normal-case')

            nav_item("Dashboard", "dashboard", "dashboard")
            nav_item("Kunden", "customers", "group")
            nav_item("Rechnungen", "invoices", "receipt")
            nav_item("Ausgaben", "expenses", "credit_card")
            nav_item("Einstellungen", "settings", "settings")

    # CONTENT
    with ui.column().classes(C_BG + " w-full"):
        with ui.column().classes(C_CONTAINER):
            content_func()

def set_page(name):
    app.storage.user['page'] = name
    ui.navigate.to('/')

# --- PAGES ---

@ui.page('/')
def index():
    with Session(engine) as session:
        if not session.exec(select(Company)).first():
            session.add(Company())
            session.commit()
    
    page = app.storage.user.get('page', 'dashboard')
    
    def content():
        with Session(engine) as session:
            comp = session.exec(select(Company)).first()
            if page == 'dashboard': render_dashboard(session, comp)
            elif page == 'customers': render_customers(session, comp)
            elif page == 'invoices': render_invoice_editor(session, comp)
            elif page == 'expenses': render_expenses(session, comp)
            elif page == 'settings': render_settings(session, comp)

    layout_wrapper(content)

def render_dashboard(session, comp):
    ui.label('Dashboard').classes('text-2xl font-bold text-slate-900 mb-2')
    invs = session.exec(select(Invoice)).all()
    exps = session.exec(select(Expense)).all()
    umsatz = sum(i.total_brutto for i in invs if i.status != 'Entwurf')
    kosten = sum(e.amount for e in exps)
    offen = sum(i.total_brutto for i in invs if i.status == 'Offen')

    with ui.grid(columns=3).classes('w-full gap-6 mb-8'):
        def stat_card(title, val, icon, col):
            with ui.card().classes(C_CARD + " p-6"):
                with ui.row().classes('justify-between items-start w-full mb-4'):
                    ui.label(title).classes('text-sm font-medium text-slate-500')
                    with ui.element('div').classes(f"p-2 rounded-lg {col} bg-opacity-10"):
                        ui.icon(icon, size='xs').classes(col)
                ui.label(val).classes('text-2xl font-bold text-slate-900')

        stat_card("Gesamtumsatz", f"{umsatz:,.2f} €", "trending_up", "text-emerald-600")
        stat_card("Ausgaben", f"{kosten:,.2f} €", "trending_down", "text-red-600")
        stat_card("Offen", f"{offen:,.2f} €", "hourglass_empty", "text-blue-600")

def render_customers(session, comp):
    with ui.row().classes('w-full justify-between items-center mb-6'):
        ui.label('Kundenverwaltung').classes('text-2xl font-bold text-slate-900')
        with ui.row().classes('gap-3'):
            with ui.dialog() as d, ui.card().classes(C_CARD):
                ui.label('CSV Import').classes('font-bold mb-4')
                
                # SAFE UPLOAD HANDLER
                def handle(e: events.UploadEventArguments):
                    try:
                        # Versuch 1: Normaler Zugriff
                        content = e.content.read()
                    except AttributeError:
                        # Versuch 2: Falls Python 3.14 das Attribut versteckt
                        ui.notify('Upload-Fehler: Content Attribut fehlt. Prüfe Python-Version.', color='red')
                        print(f"DEBUG: Upload Event hat folgende Attribute: {dir(e)}")
                        return

                    c, err = process_customer_import(content, session, comp.id)
                    if err: ui.notify(err, color='red')
                    else: 
                        ui.notify(f"{c} Importiert", color='green')
                        d.close()
                        ui.navigate.to('/')
                
                ui.upload(on_upload=handle, auto_upload=True).classes('w-full')
            
            ui.button('Import', icon='upload', on_click=d.open).classes(C_BTN_SEC)
            ui.button('Kunde anlegen', icon='add').classes(C_BTN_PRIM)

    customers = session.exec(select(Customer)).all()
    with ui.grid(columns=3).classes('w-full gap-4'):
        for c in customers:
            with ui.card().classes(C_CARD + " p-5 hover:border-slate-300 transition cursor-pointer group"):
                with ui.row().classes('justify-between w-full mb-3'):
                    with ui.row().classes('gap-3 items-center'):
                        with ui.element('div').classes('w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-600 font-bold'):
                            ui.label(c.name[:1] if c.name else "?")
                        with ui.column().classes('gap-0'):
                            ui.label(c.display_name).classes('font-bold text-slate-900 text-sm')
                            ui.label(f"KdNr: {c.kdnr}").classes('text-xs text-slate-400')
                    ui.icon('more_horiz').classes('text-slate-300 group-hover:text-slate-500')
                
                if c.email:
                    with ui.row().classes('items-center gap-2 text-slate-500 text-xs mt-2'):
                        ui.icon('mail', size='xs')
                        ui.label(c.email).classes('truncate max-w-[150px]')
                if c.ort:
                    with ui.row().classes('items-center gap-2 text-slate-500 text-xs'):
                        ui.icon('place', size='xs')
                        ui.label(f"{c.plz} {c.ort}")

def generate_invoice_pdf(company, customer, invoice, items):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)

    pdf.cell(0, 10, f"{company.name}", ln=True)
    if company.iban:
        pdf.cell(0, 8, f"IBAN: {company.iban}", ln=True)
    if company.tax_id:
        pdf.cell(0, 8, f"Steuernummer: {company.tax_id}", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, f"Rechnung Nr. {invoice.nr}", ln=True)
    pdf.cell(0, 8, f"Datum: {invoice.date}", ln=True)
    pdf.ln(6)

    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, f"Kunde: {customer.display_name}", ln=True)
    pdf.ln(6)

    pdf.set_font("Helvetica", style="B", size=10)
    pdf.cell(100, 8, "Beschreibung")
    pdf.cell(30, 8, "Menge", align="R")
    pdf.cell(30, 8, "Einzelpreis", align="R")
    pdf.cell(30, 8, "Gesamt", align="R", ln=True)

    pdf.set_font("Helvetica", size=10)
    netto = 0.0
    for item in items:
        desc = item['desc'].value or ''
        qty = float(item['qty'].value or 0)
        price = float(item['price'].value or 0)
        total = qty * price
        netto += total
        pdf.cell(100, 8, desc[:45])
        pdf.cell(30, 8, f"{qty:.2f}", align="R")
        pdf.cell(30, 8, f"{price:,.2f} €", align="R")
        pdf.cell(30, 8, f"{total:,.2f} €", align="R", ln=True)

    brutto = netto * 1.19
    pdf.ln(4)
    pdf.set_font("Helvetica", style="B", size=11)
    pdf.cell(160, 8, "Netto", align="R")
    pdf.cell(30, 8, f"{netto:,.2f} €", align="R", ln=True)
    pdf.cell(160, 8, "Brutto (inkl. 19% USt)", align="R")
    pdf.cell(30, 8, f"{brutto:,.2f} €", align="R", ln=True)

    pdf_path = f"./storage/invoices/invoice_{invoice.nr}.pdf"
    pdf.output(pdf_path)

def render_settings(session, comp):
    ui.label('Einstellungen').classes('text-2xl font-bold text-slate-900 mb-6')
    with ui.card().classes(C_CARD + " p-6 w-full"):
        with ui.column().classes('w-full gap-4'):
            ui.label('Unternehmensdaten').classes('text-sm font-semibold text-slate-700')
            name_input = ui.input('Firmenname', value=comp.name).classes(C_INPUT)
            iban_input = ui.input('IBAN', value=comp.iban).classes(C_INPUT)
            tax_input = ui.input('Steuernummer', value=comp.tax_id).classes(C_INPUT)

            ui.label('SMTP Einstellungen').classes('text-sm font-semibold text-slate-700 mt-4')
            smtp_server = ui.input('SMTP Server', value=comp.smtp_server).classes(C_INPUT)
            smtp_port = ui.number('SMTP Port', value=comp.smtp_port).classes(C_INPUT)
            smtp_user = ui.input('SMTP User', value=comp.smtp_user).classes(C_INPUT)
            smtp_password = ui.input('SMTP Passwort', value=comp.smtp_password, password=True).classes(C_INPUT)

            def save_settings():
                with Session(engine) as inner:
                    company = inner.get(Company, comp.id)
                    company.name = name_input.value or ''
                    company.iban = iban_input.value or ''
                    company.tax_id = tax_input.value or ''
                    company.smtp_server = smtp_server.value or ''
                    company.smtp_port = int(smtp_port.value or 0)
                    company.smtp_user = smtp_user.value or ''
                    company.smtp_password = smtp_password.value or ''
                    inner.add(company)
                    inner.commit()
                ui.notify('Einstellungen gespeichert', color='green')

            ui.button('Speichern', icon='save', on_click=save_settings).classes(C_BTN_PRIM + " w-fit")

def render_invoice_editor(session, comp):
    with ui.dialog() as d, ui.card().classes(C_CARD + " w-[1200px] max-w-[95vw]"):
        ui.label('Neue Rechnung').classes('text-lg font-bold text-slate-900 mb-4')

        customers = session.exec(select(Customer)).all()
        customer_options = {str(c.id): c.display_name for c in customers}

        items = []
        totals_netto = ui.label('0,00 €').classes('font-mono text-sm text-slate-700')
        totals_brutto = ui.label('0,00 €').classes('font-mono text-sm text-slate-900 font-bold')

        with ui.grid(columns=2).classes('w-full gap-6 items-start'):
            with ui.column().classes('w-full gap-6'):
                with ui.column().classes('w-full gap-3'):
                    ui.label('Kopfdaten').classes('text-sm font-semibold text-slate-700')
                    selected_customer = ui.select(customer_options, label='Kunde').classes(C_INPUT + " w-full")
                    invoice_date = ui.input('Datum', value=datetime.now().strftime('%Y-%m-%d')).classes(C_INPUT + " w-full")

                with ui.column().classes('w-full gap-3'):
                    ui.label('Rechtliches').classes('text-sm font-semibold text-slate-700')
                    legal_tax_id = ui.input('Steuernummer', value=comp.tax_id or '').classes(C_INPUT + " w-full")
                    legal_terms = ui.input('Zahlungsziel', value='14 Tage').classes(C_INPUT + " w-full")
                    legal_note = ui.textarea('Hinweis', value='').classes(C_INPUT + " w-full h-24")

                with ui.column().classes('w-full gap-3'):
                    ui.label('Postenliste').classes('text-sm font-semibold text-slate-700')
                    with ui.row().classes('w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-500 font-semibold'):
                        ui.label('Beschreibung').classes('flex-1')
                        ui.label('Menge').classes('w-24 text-right')
                        ui.label('Einzelpreis').classes('w-28 text-right')
                        ui.label('Aktion').classes('w-20 text-right')
                    items_container = ui.column().classes('w-full gap-2')

                    def remove_item(item):
                        items.remove(item)
                        item['row'].delete()
                        calc_totals()

                    def add_item():
                        item = {}
                        with items_container:
                            with ui.row().classes('w-full gap-3 items-end border border-slate-200 rounded-lg p-3') as row:
                                desc = ui.input('Beschreibung').classes(C_INPUT + " flex-1")
                                qty = ui.number('Menge', value=1, format='%.2f').classes(C_INPUT + " w-24")
                                price = ui.number('Einzelpreis', value=0, format='%.2f').classes(C_INPUT + " w-28")
                                ui.button('Entfernen', on_click=lambda: remove_item(item)).classes(C_BTN_SEC + " w-20")
                        item.update({'row': row, 'desc': desc, 'qty': qty, 'price': price})
                        items.append(item)
                        qty.on('change', calc_totals)
                        price.on('change', calc_totals)
                        calc_totals()

                    ui.button('Posten hinzufügen', icon='add', on_click=add_item).classes(C_BTN_SEC + " w-fit")

                with ui.row().classes('w-full justify-end gap-6'):
                    with ui.column().classes('items-end'):
                        ui.label('Netto').classes('text-xs text-slate-500')
                        totals_netto
                    with ui.column().classes('items-end'):
                        ui.label('Brutto (inkl. 19% USt)').classes('text-xs text-slate-500')
                        totals_brutto

            with ui.column().classes('w-full'):
                with ui.column().classes('bg-slate-100 rounded-xl p-4 w-full'):
                    with ui.column().classes('sticky top-6 w-full gap-3'):
                        ui.label('Vorschau').classes('text-sm font-semibold text-slate-700')
                        with ui.column().classes('bg-white shadow-xl aspect-[210/297] p-10 w-full'):
                            ui.label('Rechnungsvorschau').classes('text-base font-semibold text-slate-900')
                            with ui.column().classes('gap-2 mt-4'):
                                preview_customer = ui.label('-').classes('text-sm text-slate-700')
                                preview_date = ui.label('-').classes('text-sm text-slate-700')
                            with ui.column().classes('gap-1 mt-6'):
                                ui.label('Zwischensumme').classes('text-xs text-slate-400')
                                preview_netto = ui.label('0,00 €').classes('font-mono text-sm text-slate-700')
                                ui.label('Gesamt (inkl. 19% USt)').classes('text-xs text-slate-400 mt-2')
                                preview_brutto = ui.label('0,00 €').classes('font-mono text-sm text-slate-900 font-bold')

        def sync_preview():
            preview_customer.set_text(customer_options.get(str(selected_customer.value), '-'))
            preview_date.set_text(invoice_date.value or '-')

        def calc_totals():
            netto = 0.0
            for item in items:
                qty = float(item['qty'].value or 0)
                price = float(item['price'].value or 0)
                netto += qty * price
            brutto = netto * 1.19
            totals_netto.set_text(f"{netto:,.2f} €")
            totals_brutto.set_text(f"{brutto:,.2f} €")
            preview_netto.set_text(f"{netto:,.2f} €")
            preview_brutto.set_text(f"{brutto:,.2f} €")
            return netto, brutto

        selected_customer.on('change', sync_preview)
        invoice_date.on('change', sync_preview)
        sync_preview()

        def finalize_invoice():
            if not selected_customer.value:
                return ui.notify('Bitte Kunde auswählen', color='red')
            if not items:
                return ui.notify('Bitte mindestens einen Posten hinzufügen', color='red')

            netto, brutto = calc_totals()
            if netto <= 0:
                return ui.notify('Bitte gültige Beträge eingeben', color='red')

            with Session(engine) as inner:
                company = inner.get(Company, comp.id)
                customer = inner.get(Customer, int(selected_customer.value))
                if not company or not customer:
                    return ui.notify('Fehlende Daten', color='red')

                invoice = Invoice(
                    customer_id=customer.id,
                    nr=company.next_invoice_nr,
                    date=invoice_date.value or datetime.now().strftime('%Y-%m-%d'),
                    total_brutto=brutto,
                    status='Offen'
                )
                inner.add(invoice)
                inner.commit()
                inner.refresh(invoice)

                for item in items:
                    inner.add(InvoiceItem(
                        invoice_id=invoice.id,
                        description=item['desc'].value or '',
                        quantity=float(item['qty'].value or 0),
                        unit_price=float(item['price'].value or 0)
                    ))

                company.next_invoice_nr += 1
                inner.add(company)
                inner.commit()

                generate_invoice_pdf(company, customer, invoice, items)

            ui.notify('Rechnung erstellt', color='green')
            d.close()
            ui.navigate.to('/')

        with ui.row().classes('w-full justify-end gap-2 mt-6'):
            ui.button('Abbrechen', on_click=d.close).classes(C_BTN_SEC)
            ui.button('Finalisieren', icon='check', on_click=finalize_invoice).classes(C_BTN_PRIM)

    return d

def render_invoices(session, comp):
    with ui.row().classes('w-full justify-between items-center mb-6'):
        ui.label('Rechnungen').classes('text-2xl font-bold text-slate-900')
        d = render_invoice_editor(session, comp)
        ui.button('Rechnung erstellen', icon='add', on_click=d.open).classes(C_BTN_PRIM)
    invs = session.exec(select(Invoice)).all()
    
    with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
        # MANUELLE TABELLEN KOPFZEILE (Kein ui.table mehr!)
        with ui.row().classes('w-full bg-slate-50 border-b border-slate-200 p-4 gap-4'):
            ui.label('Status').classes('w-24 font-medium text-slate-500 text-sm')
            ui.label('Nr').classes('w-16 font-medium text-slate-500 text-sm')
            ui.label('Datum').classes('w-24 font-medium text-slate-500 text-sm')
            ui.label('Kunde').classes('flex-1 font-medium text-slate-500 text-sm')
            ui.label('Betrag').classes('w-24 text-right font-medium text-slate-500 text-sm')
            ui.label('PDF').classes('w-24 text-right font-medium text-slate-500 text-sm')

        # MANUELLE REIHEN
        with ui.column().classes('w-full gap-0'):
            for i in invs:
                with ui.row().classes('w-full p-4 border-b border-slate-50 items-center gap-4 hover:bg-slate-50'):
                    # Badge
                    style = C_BADGE_GRAY
                    if i.status == 'Offen': style = C_BADGE_BLUE
                    if i.status == 'Bezahlt': style = C_BADGE_GREEN
                    ui.label(i.status).classes(style + " w-24")
                    
                    ui.label(f"#{i.nr}" if i.nr else "-").classes('w-16 text-slate-600 font-mono text-sm')
                    ui.label(i.date).classes('w-24 text-slate-600 text-sm')
                    
                    cname = "Unbekannt"
                    if i.customer_id:
                        cust = session.get(Customer, i.customer_id)
                        if cust: cname = cust.display_name
                    ui.label(cname).classes('flex-1 font-medium text-slate-900 text-sm truncate')
                    
                    ui.label(f"{i.total_brutto:,.2f} €").classes('w-24 text-right font-mono font-medium text-sm')
                    pdf_path = f"./storage/invoices/invoice_{i.nr}.pdf"
                    with ui.row().classes('w-24 justify-end'):
                        if i.nr and os.path.exists(pdf_path):
                            ui.button('Download', icon='download', on_click=lambda p=pdf_path: ui.download(p)).classes(C_BTN_SEC + " w-full")
                        else:
                            ui.label('-').classes('text-slate-300 text-sm w-full text-right')

def render_invoice_editor(session, comp):
    ui.label('Rechnungseditor').classes('text-2xl font-bold text-slate-900 mb-6')

    customers = session.exec(select(Customer)).all()
    customer_options = {str(c.id): c.display_name for c in customers}

    items = []
    totals_netto = ui.label('0,00 €').classes('font-mono text-sm text-slate-700')
    totals_brutto = ui.label('0,00 €').classes('font-mono text-sm text-slate-900 font-bold')

    preview_customer = ui.label('Bitte Kunde wählen').classes('text-sm font-medium text-slate-900')
    preview_date = ui.label('-').classes('text-xs text-slate-500')
    preview_netto = ui.label('0,00 €').classes('font-mono text-sm text-slate-700')
    preview_brutto = ui.label('0,00 €').classes('font-mono text-sm text-slate-900 font-bold')

    def calc_totals():
        netto = 0.0
        for item in items:
            qty = float(item['qty'].value or 0)
            price = float(item['price'].value or 0)
            netto += qty * price
        brutto = netto * 1.19
        totals_netto.set_text(f"{netto:,.2f} €")
        totals_brutto.set_text(f"{brutto:,.2f} €")
        preview_netto.set_text(f"{netto:,.2f} €")
        preview_brutto.set_text(f"{brutto:,.2f} €")
        return netto, brutto

    def update_preview():
        cust_name = 'Bitte Kunde wählen'
        if selected_customer.value:
            cust = session.get(Customer, int(selected_customer.value))
            if cust:
                cust_name = cust.display_name
        preview_customer.set_text(cust_name)
        preview_date.set_text(invoice_date.value or '-')
        preview_items.clear()
        if not items:
            ui.label('Keine Posten').classes('text-xs text-slate-400').move(preview_items)
        for item in items:
            desc = item['desc'].value or ''
            qty = float(item['qty'].value or 0)
            price = float(item['price'].value or 0)
            total = qty * price
            with preview_items:
                with ui.row().classes('w-full justify-between text-xs text-slate-600'):
                    ui.label(desc if desc else '—').classes('truncate max-w-[220px]')
                    ui.label(f"{total:,.2f} €").classes('font-mono')
        calc_totals()

    with ui.row().classes('w-full gap-6 items-start'):
        with ui.card().classes(C_CARD + " p-6 w-1/2"):
            ui.label('Eingabe').classes('text-sm font-semibold text-slate-700 mb-4')

            selected_customer = ui.select(customer_options, label='Kunde').classes(C_INPUT + " w-full")
            invoice_date = ui.input('Datum', value=datetime.now().strftime('%Y-%m-%d')).classes(C_INPUT + " w-full")

            with ui.column().classes('w-full gap-3 mt-4'):
                ui.label('Rechnungsposten').classes('text-sm font-semibold text-slate-700')
                items_container = ui.column().classes('w-full gap-3')

                def remove_item(item):
                    items.remove(item)
                    item['row'].delete()
                    update_preview()

                def add_item():
                    item = {}
                    with items_container:
                        with ui.row().classes('w-full gap-3 items-end') as row:
                            desc = ui.input('Beschreibung').classes(C_INPUT + " flex-1")
                            qty = ui.number('Menge', value=1, format='%.2f').classes(C_INPUT + " w-28")
                            price = ui.number('Einzelpreis', value=0, format='%.2f').classes(C_INPUT + " w-32")
                            ui.button('Entfernen', on_click=lambda: remove_item(item)).classes(C_BTN_SEC)
                    item.update({'row': row, 'desc': desc, 'qty': qty, 'price': price})
                    items.append(item)
                    desc.on('change', update_preview)
                    qty.on('change', update_preview)
                    price.on('change', update_preview)
                    update_preview()

                ui.button('Posten hinzufügen', icon='add', on_click=add_item).classes(C_BTN_SEC + " w-fit")

            with ui.row().classes('w-full justify-end gap-6 mt-4'):
                with ui.column().classes('items-end'):
                    ui.label('Netto').classes('text-xs text-slate-500')
                    totals_netto
                with ui.column().classes('items-end'):
                    ui.label('Brutto (inkl. 19% USt)').classes('text-xs text-slate-500')
                    totals_brutto

            def finalize_invoice():
                if not selected_customer.value:
                    return ui.notify('Bitte Kunde auswählen', color='red')
                if not items:
                    return ui.notify('Bitte mindestens einen Posten hinzufügen', color='red')

                netto, brutto = calc_totals()
                if netto <= 0:
                    return ui.notify('Bitte gültige Beträge eingeben', color='red')

                with Session(engine) as inner:
                    company = inner.get(Company, comp.id)
                    customer = inner.get(Customer, int(selected_customer.value))
                    if not company or not customer:
                        return ui.notify('Fehlende Daten', color='red')

                    invoice = Invoice(
                        customer_id=customer.id,
                        nr=company.next_invoice_nr,
                        date=invoice_date.value or datetime.now().strftime('%Y-%m-%d'),
                        total_brutto=brutto,
                        status='Offen'
                    )
                    inner.add(invoice)
                    inner.commit()
                    inner.refresh(invoice)

                    for item in items:
                        inner.add(InvoiceItem(
                            invoice_id=invoice.id,
                            description=item['desc'].value or '',
                            quantity=float(item['qty'].value or 0),
                            unit_price=float(item['price'].value or 0)
                        ))

                    company.next_invoice_nr += 1
                    inner.add(company)
                    inner.commit()

                    generate_invoice_pdf(company, customer, invoice, items)

                ui.notify('Rechnung erstellt', color='green')
                ui.navigate.to('/')

            with ui.row().classes('w-full justify-end gap-2 mt-6'):
                ui.button('Finalisieren', icon='check', on_click=finalize_invoice).classes(C_BTN_PRIM)

        with ui.card().classes(C_CARD + " p-6 w-1/2"):
            ui.label('Live-Vorschau').classes('text-sm font-semibold text-slate-700 mb-4')
            with ui.column().classes('gap-1 mb-4'):
                ui.label(comp.name).classes('text-sm font-semibold text-slate-900')
                if comp.iban:
                    ui.label(f"IBAN: {comp.iban}").classes('text-xs text-slate-500')
                if comp.tax_id:
                    ui.label(f"Steuernummer: {comp.tax_id}").classes('text-xs text-slate-500')

            with ui.row().classes('justify-between items-center mb-3'):
                with ui.column().classes('gap-0'):
                    ui.label('Rechnung an').classes('text-xs text-slate-400')
                    preview_customer
                with ui.column().classes('items-end gap-0'):
                    ui.label('Datum').classes('text-xs text-slate-400')
                    preview_date

            with ui.column().classes('w-full gap-2'):
                ui.label('Positionen').classes('text-xs text-slate-400')
                preview_items = ui.column().classes('w-full gap-2')

            with ui.row().classes('w-full justify-end gap-6 mt-4'):
                with ui.column().classes('items-end'):
                    ui.label('Netto').classes('text-xs text-slate-400')
                    preview_netto
                with ui.column().classes('items-end'):
                    ui.label('Brutto').classes('text-xs text-slate-400')
                    preview_brutto

    update_preview()

    invs = session.exec(select(Invoice)).all()
    with ui.card().classes(C_CARD + " p-0 overflow-hidden mt-8"):
        with ui.row().classes('w-full bg-slate-50 border-b border-slate-200 p-4 gap-4'):
            ui.label('Status').classes('w-24 font-medium text-slate-500 text-sm')
            ui.label('Nr').classes('w-16 font-medium text-slate-500 text-sm')
            ui.label('Datum').classes('w-24 font-medium text-slate-500 text-sm')
            ui.label('Kunde').classes('flex-1 font-medium text-slate-500 text-sm')
            ui.label('Betrag').classes('w-24 text-right font-medium text-slate-500 text-sm')
            ui.label('PDF').classes('w-24 text-right font-medium text-slate-500 text-sm')

        with ui.column().classes('w-full gap-0'):
            for i in invs:
                with ui.row().classes('w-full p-4 border-b border-slate-50 items-center gap-4 hover:bg-slate-50'):
                    style = C_BADGE_GRAY
                    if i.status == 'Offen': style = C_BADGE_BLUE
                    if i.status == 'Bezahlt': style = C_BADGE_GREEN
                    ui.label(i.status).classes(style + " w-24")

                    ui.label(f"#{i.nr}" if i.nr else "-").classes('w-16 text-slate-600 font-mono text-sm')
                    ui.label(i.date).classes('w-24 text-slate-600 text-sm')

                    cname = "Unbekannt"
                    if i.customer_id:
                        cust = session.get(Customer, i.customer_id)
                        if cust: cname = cust.display_name
                    ui.label(cname).classes('flex-1 font-medium text-slate-900 text-sm truncate')

                    ui.label(f"{i.total_brutto:,.2f} €").classes('w-24 text-right font-mono font-medium text-sm')
                    pdf_path = f"./storage/invoices/invoice_{i.nr}.pdf"
                    with ui.row().classes('w-24 justify-end'):
                        if i.nr and os.path.exists(pdf_path):
                            ui.button('Download', icon='download', on_click=lambda p=pdf_path: ui.download(p)).classes(C_BTN_SEC + " w-full")
                        else:
                            ui.label('-').classes('text-slate-300 text-sm w-full text-right')

def render_expenses(session, comp):
    with ui.row().classes('w-full justify-between items-center mb-6'):
        ui.label('Ausgaben').classes('text-2xl font-bold text-slate-900')
        with ui.dialog() as d, ui.card().classes(C_CARD):
            ui.label('CSV Import').classes('font-bold mb-4')
            def handle(e: events.UploadEventArguments):
                try: content = e.content.read()
                except: return ui.notify('Upload Fehler', color='red')
                c, err = process_expense_import(content, session, comp.id)
                if err: ui.notify(err, color='red')
                else: 
                    ui.notify(f"{c} Importiert", color='green')
                    d.close()
                    ui.navigate.to('/')
            ui.upload(on_upload=handle, auto_upload=True).classes('w-full')
        ui.button('Import', icon='upload', on_click=d.open).classes(C_BTN_SEC)

    exps = session.exec(select(Expense)).all()
    with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
        # HEADER
        with ui.row().classes('w-full bg-slate-50 border-b border-slate-200 p-4 gap-4'):
            ui.label('Datum').classes('w-24 font-medium text-slate-500 text-sm')
            ui.label('Beschreibung').classes('flex-1 font-medium text-slate-500 text-sm')
            ui.label('Kategorie').classes('w-32 font-medium text-slate-500 text-sm')
            ui.label('Betrag').classes('w-24 text-right font-medium text-slate-500 text-sm')

        # ROWS
        with ui.column().classes('w-full gap-0'):
            for e in exps:
                with ui.row().classes('w-full p-4 border-b border-slate-50 items-center gap-4 hover:bg-slate-50'):
                    ui.label(e.date).classes('w-24 text-slate-500 font-mono text-xs')
                    ui.label(e.description).classes('flex-1 font-medium text-slate-900 text-sm truncate')
                    ui.label(e.category).classes('w-32 text-slate-500 text-sm')
                    ui.label(f"- {e.amount:,.2f} €").classes('w-24 text-right text-red-600 font-mono font-medium text-sm')

ui.run(title='FixundFertig Ultimate', port=8080, language='de', storage_secret='secret2026')
