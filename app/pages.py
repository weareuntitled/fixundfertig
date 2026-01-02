from nicegui import ui, app, events
from sqlmodel import Session, select
from datetime import datetime
from email.message import EmailMessage
import smtplib
from fpdf import FPDF
import os

from data import Company, Customer, Invoice, InvoiceItem, Expense, engine, load_customer_import_dataframe, load_expense_import_dataframe, load_invoice_import_dataframe, process_customer_import, process_expense_import, process_invoice_import
from services import create_correction
from styles import (
    C_BG, C_CONTAINER, C_CARD, C_CARD_HOVER, C_BTN_PRIM, C_BTN_SEC, C_INPUT,
    C_BADGE_GREEN, C_BADGE_BLUE, C_BADGE_GRAY, C_PAGE_TITLE, C_SECTION_TITLE,
    C_TABLE_HEADER, C_TABLE_ROW
)

def render_dashboard(session, comp):
    ui.label('Dashboard').classes(C_PAGE_TITLE + " mb-2")
    invs = session.exec(select(Invoice)).all()
    exps = session.exec(select(Expense)).all()
    umsatz = sum(i.total_brutto for i in invs if i.status != 'Entwurf')
    kosten = sum(e.amount for e in exps)
    offen = sum(i.total_brutto for i in invs if i.status == 'Offen')
    latest_invoice = max(invs, key=lambda i: i.date or "") if invs else None
    latest_customer = session.get(Customer, latest_invoice.customer_id) if latest_invoice else None
    status_badge = C_BADGE_GRAY
    if latest_invoice:
        if latest_invoice.status == 'Bezahlt':
            status_badge = C_BADGE_GREEN
        elif latest_invoice.status == 'Offen':
            status_badge = C_BADGE_BLUE

    with ui.grid(columns=3).classes('w-full gap-6 mb-8'):
        def stat_card(title, val, icon, col):
            with ui.card().classes(C_CARD + " p-6 " + C_CARD_HOVER):
                with ui.row().classes('justify-between items-start w-full mb-4'):
                    ui.label(title).classes('text-sm font-medium text-slate-500')
                    with ui.element('div').classes(f"p-2 rounded-lg {col} bg-opacity-10"):
                        ui.icon(icon, size='xs').classes(col)
                ui.label(val).classes('text-2xl font-semibold text-slate-900')

        stat_card("Gesamtumsatz", f"{umsatz:,.2f} €", "trending_up", "text-emerald-600")
        stat_card("Ausgaben", f"{kosten:,.2f} €", "trending_down", "text-red-600")
        stat_card("Offen", f"{offen:,.2f} €", "hourglass_empty", "text-blue-600")

    with ui.grid(columns=3).classes('w-full gap-6 mb-8'):
        with ui.card().classes(C_CARD + " p-6 col-span-2"):
            ui.label('Letzte Aktivität').classes(C_SECTION_TITLE + " mb-4")
            if latest_invoice:
                with ui.row().classes('justify-between items-start w-full'):
                    with ui.column().classes('gap-2'):
                        ui.label(f"Rechnung Nr. {latest_invoice.nr}").classes('text-sm font-semibold text-slate-900')
                        ui.label(f"Kunde: {latest_customer.display_name if latest_customer else 'Unbekannt'}").classes('text-xs text-slate-500')
                        ui.label(f"Datum: {latest_invoice.date}").classes('text-xs text-slate-500')
                    with ui.column().classes('items-end gap-2'):
                        ui.label(f"{latest_invoice.total_brutto:,.2f} €").classes('text-lg font-semibold text-slate-900')
                        ui.label(latest_invoice.status).classes(status_badge)
            else:
                ui.label('Noch keine Rechnungen vorhanden.').classes('text-sm text-slate-500')
        with ui.card().classes(C_CARD + " p-6 col-span-1"):
            ui.label('Neue E-Mails / NADN-Status').classes(C_SECTION_TITLE + " mb-4")
            with ui.column().classes('gap-3'):
                with ui.row().classes('justify-between items-center'):
                    ui.label('Neue E-Mails').classes('text-sm text-slate-600')
                    ui.label('0').classes('text-sm font-semibold text-slate-900')
                with ui.row().classes('justify-between items-center'):
                    ui.label('NADN-Status').classes('text-sm text-slate-600')
                    ui.label('Inaktiv').classes(C_BADGE_GRAY)

def render_customers(session, comp):
    with ui.row().classes('w-full justify-between items-center mb-6'):
        ui.label('Kundenverwaltung').classes(C_PAGE_TITLE)
        with ui.row().classes('gap-3'):
            with ui.dialog() as d, ui.card().classes(C_CARD + " p-5"):
                ui.label('CSV Import').classes(C_SECTION_TITLE + " mb-4")
                import_payload = {'content': None, 'filename': '', 'rows_total': 0}
                preview_container = ui.column().classes('w-full gap-3')
                stats_label = ui.label('').classes('text-xs text-slate-500')
                progress = ui.linear_progress(value=0).classes('w-full')
                
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

                    filename = getattr(e, 'name', '') or getattr(getattr(e, 'file', None), 'name', '')
                    progress.value = 0.3
                    df, err = load_customer_import_dataframe(content, filename)
                    preview_container.clear()
                    stats_label.set_text('')
                    confirm_btn.disable()
                    if err: 
                        ui.notify(err, color='red')
                        return
                    progress.value = 0.6

                    import_payload['content'] = content
                    import_payload['filename'] = filename
                    import_payload['rows_total'] = len(df.index)

                    with preview_container:
                        ui.label('Vorschau').classes(C_SECTION_TITLE + " mt-4")
                        preview_df = df.head(20).fillna('')
                        rows = []
                        for i, row in preview_df.iterrows():
                            row_data = {'_row': str(i + 1)}
                            for col in preview_df.columns:
                                row_data[col] = str(row[col])
                            rows.append(row_data)
                        columns = [{'name': '_row', 'label': '#', 'field': '_row'}]
                        columns += [{'name': col, 'label': col, 'field': col} for col in preview_df.columns]
                        ui.table(columns=columns, rows=rows, row_key='_row').classes('w-full')
                    stats_label.set_text(f"Zeilen gesamt: {import_payload['rows_total']}")
                    progress.value = 0.8
                    confirm_btn.enable()

                def confirm_import():
                    if not import_payload['content']:
                        ui.notify('Bitte zuerst eine Datei hochladen.', color='red')
                        return
                    progress.value = 0.9
                    c, err = process_customer_import(import_payload['content'], session, comp.id, import_payload['filename'])
                    if err: ui.notify(err, color='red')
                    else: 
                        ui.notify(f"{c} Importiert ({c}/{import_payload['rows_total']})", color='green')
                        progress.value = 1.0
                        d.close()
                        ui.navigate.to('/')
                
                def cancel_import():
                    import_payload['content'] = None
                    import_payload['filename'] = ''
                    import_payload['rows_total'] = 0
                    preview_container.clear()
                    stats_label.set_text('')
                    progress.value = 0
                    confirm_btn.disable()
                    d.close()

                ui.upload(on_upload=handle, auto_upload=True).classes('w-full').props('accept=.csv,.xls,.xlsx')
                with ui.row().classes('w-full justify-between items-center mt-3'):
                    confirm_btn = ui.button('Import bestätigen', icon='check', on_click=confirm_import).classes(C_BTN_PRIM + " w-fit")
                    ui.button('Abbrechen', on_click=cancel_import).classes(C_BTN_SEC + " w-fit")
                confirm_btn.disable()
            
            ui.button('Import', icon='upload', on_click=d.open).classes(C_BTN_SEC)
            ui.button('Kunde anlegen', icon='add', on_click=lambda: (app.storage.user.__setitem__('page', 'customer_new'), ui.navigate.to('/'))).classes(C_BTN_PRIM)

    search_input = ui.input('Suche', value='').classes(C_INPUT + " w-64 mb-4")

    @ui.refreshable
    def customer_grid():
        term = (search_input.value or '').strip().lower()
        customers = session.exec(select(Customer)).all()
        if term:
            customers = [
                c for c in customers
                if term in (c.display_name or '').lower()
                or term in str(c.kdnr or '')
                or term in (c.email or '').lower()
                or term in (c.ort or '').lower()
            ]
        with ui.grid(columns=3).classes('w-full gap-4'):
            for c in customers:
                with ui.card().classes(C_CARD + " p-5 cursor-pointer group " + C_CARD_HOVER):
                    with ui.row().classes('justify-between w-full mb-3'):
                        with ui.row().classes('gap-3 items-center'):
                            with ui.element('div').classes('w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-600 font-bold'):
                                ui.label(c.name[:1] if c.name else "?")
                            with ui.column().classes('gap-0'):
                                ui.label(c.display_name).classes('font-semibold text-slate-900 text-sm')
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

    search_input.on('input', lambda _: customer_grid.refresh())
    customer_grid()

def render_customer_new(session, comp):
    ui.label('Kunde anlegen').classes(C_PAGE_TITLE + " mb-6")
    last_kdnr = session.exec(select(Customer.kdnr).order_by(Customer.kdnr.desc())).first()
    next_kdnr = int(last_kdnr or 0) + 1

    with ui.card().classes(C_CARD + " p-6 w-full"):
        with ui.column().classes('w-full gap-4'):
            ui.label('Kundendaten').classes(C_SECTION_TITLE)
            kdnr_input = ui.input('Kundennummer', value=str(next_kdnr)).props('readonly').classes(C_INPUT + " w-40")
            name_input = ui.input('Firmenname', value='').classes(C_INPUT)
            with ui.row().classes('w-full gap-4'):
                vorname_input = ui.input('Vorname', value='').classes(C_INPUT + " w-1/2")
                nachname_input = ui.input('Nachname', value='').classes(C_INPUT + " w-1/2")
            email_input = ui.input('E-Mail', value='').classes(C_INPUT + " w-1/2")
            with ui.row().classes('w-full gap-4'):
                strasse_input = ui.input('Straße', value='').classes(C_INPUT + " w-2/3")
                plz_input = ui.input('PLZ', value='').classes(C_INPUT + " w-1/6")
                ort_input = ui.input('Ort', value='').classes(C_INPUT + " w-1/6")

            def save_customer():
                try:
                    kdnr_value = int(kdnr_input.value or next_kdnr)
                except ValueError:
                    ui.notify('Kundennummer ist ungültig', color='red')
                    return
                with Session(engine) as inner:
                    customer = Customer(
                        company_id=comp.id,
                        kdnr=kdnr_value,
                        name=name_input.value or '',
                        vorname=vorname_input.value or '',
                        nachname=nachname_input.value or '',
                        email=email_input.value or '',
                        strasse=strasse_input.value or '',
                        plz=plz_input.value or '',
                        ort=ort_input.value or '',
                        offen_eur=0.0
                    )
                    inner.add(customer)
                    inner.commit()
                ui.notify('Kunde gespeichert', color='green')
                app.storage.user['page'] = 'customers'
                ui.navigate.to('/')

            def cancel():
                app.storage.user['page'] = 'customers'
                ui.navigate.to('/')

            with ui.row().classes('gap-3'):
                ui.button('Speichern', icon='save', on_click=save_customer).classes(C_BTN_PRIM)
                ui.button('Abbrechen', icon='close', on_click=cancel).classes(C_BTN_SEC)

def generate_invoice_pdf(company, customer, invoice, items, apply_ustg19=False, template_name='', intro_text=''):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)

    pdf.cell(0, 10, f"{company.name}", ln=True)
    if company.first_name or company.last_name:
        pdf.cell(0, 8, f"{company.first_name} {company.last_name}".strip(), ln=True)
    if company.street:
        pdf.cell(0, 8, f"{company.street}", ln=True)
    if company.postal_code or company.city:
        pdf.cell(0, 8, f"{company.postal_code} {company.city}".strip(), ln=True)
    if company.email:
        pdf.cell(0, 8, f"E-Mail: {company.email}", ln=True)
    if company.phone:
        pdf.cell(0, 8, f"Tel.: {company.phone}", ln=True)
    if company.iban:
        pdf.cell(0, 8, f"IBAN: {company.iban}", ln=True)
    if company.tax_id:
        pdf.cell(0, 8, f"Steuernummer: {company.tax_id}", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, f"Rechnung Nr. {invoice.nr}", ln=True)
    pdf.cell(0, 8, f"Datum: {invoice.date}", ln=True)
    if template_name:
        pdf.cell(0, 8, f"Vorlage: {template_name}", ln=True)
    pdf.ln(6)

    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, f"Kunde: {customer.display_name}", ln=True)
    if customer.strasse:
        pdf.cell(0, 8, f"{customer.strasse}", ln=True)
    if customer.plz or customer.ort:
        pdf.cell(0, 8, f"{customer.plz} {customer.ort}", ln=True)
    pdf.ln(8)

    if intro_text:
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, intro_text)
        pdf.ln(4)

    pdf.set_font("Helvetica", style="B", size=10)
    pdf.cell(100, 8, "Beschreibung")
    pdf.cell(30, 8, "Menge", align="R")
    pdf.cell(30, 8, "Einzelpreis", align="R")
    pdf.cell(30, 8, "Gesamt", align="R", ln=True)

    pdf.set_font("Helvetica", size=10)
    netto = 0.0
    tax_rate = 0.0 if apply_ustg19 else 0.19
    ust_enabled = not apply_ustg19
    def item_value(val):
        if hasattr(val, 'value'):
            return val.value
        return val
    for item in items:
        desc = item_value(item.get('desc') or '') or ''
        qty = float(item_value(item.get('qty') or 0))
        price = float(item_value(item.get('price') or 0))
        is_brutto = bool(item_value(item.get('is_brutto') or False))
        unit_netto = price
        if ust_enabled and is_brutto:
            unit_netto = price / 1.19
        total = qty * unit_netto
        netto += total
        desc_label = f"{desc[:45]}"
        if ust_enabled and is_brutto:
            desc_label = f"{desc_label} (Brutto)"
        pdf.cell(100, 8, desc_label[:45])
        pdf.cell(30, 8, f"{qty:.2f}", align="R")
        pdf.cell(30, 8, f"{price:,.2f} €", align="R")
        pdf.cell(30, 8, f"{total:,.2f} €", align="R", ln=True)

    brutto = netto * (1 + tax_rate)
    pdf.ln(4)
    pdf.set_font("Helvetica", style="B", size=11)
    pdf.cell(160, 8, "Netto", align="R")
    pdf.cell(30, 8, f"{netto:,.2f} €", align="R", ln=True)
    pdf.cell(160, 8, "Brutto" if tax_rate == 0 else "Brutto (inkl. 19% USt)", align="R")
    pdf.cell(30, 8, f"{brutto:,.2f} €", align="R", ln=True)

    if tax_rate == 0:
        pdf.ln(6)
        pdf.set_font("Helvetica", size=9)
        pdf.multi_cell(0, 6, "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.")

    pdf_path = f"./storage/invoices/invoice_{invoice.nr}.pdf"
    pdf.output(pdf_path)
    return pdf_path

def render_settings(session, comp):
    ui.label('Einstellungen').classes(C_PAGE_TITLE + " mb-6")
    with ui.card().classes(C_CARD + " p-6 w-full"):
        with ui.column().classes('w-full gap-4'):
            ui.label('Unternehmensdaten').classes(C_SECTION_TITLE)
            name_input = ui.input('Firmenname', value=comp.name).classes(C_INPUT)
            first_name_input = ui.input('Vorname', value=comp.first_name).classes(C_INPUT)
            last_name_input = ui.input('Nachname', value=comp.last_name).classes(C_INPUT)
            street_input = ui.input('Straße', value=comp.street).classes(C_INPUT)
            postal_code_input = ui.input('PLZ', value=comp.postal_code).classes(C_INPUT)
            city_input = ui.input('Ort', value=comp.city).classes(C_INPUT)
            email_input = ui.input('E-Mail', value=comp.email).classes(C_INPUT)
            phone_input = ui.input('Telefon', value=comp.phone).classes(C_INPUT)
            iban_input = ui.input('IBAN', value=comp.iban).classes(C_INPUT)
            tax_input = ui.input('Steuernummer', value=comp.tax_id).classes(C_INPUT)

            ui.label('SMTP Einstellungen').classes(C_SECTION_TITLE + " mt-4")
            smtp_server = ui.input('SMTP Server', value=comp.smtp_server).classes(C_INPUT)
            smtp_port = ui.number('SMTP Port', value=comp.smtp_port).classes(C_INPUT)
            smtp_user = ui.input('SMTP User', value=comp.smtp_user).classes(C_INPUT)
            smtp_password = ui.input('SMTP Passwort', value=comp.smtp_password, password=True).classes(C_INPUT)

            def save_settings():
                with Session(engine) as inner:
                    company = inner.get(Company, comp.id)
                    company.name = name_input.value or ''
                    company.first_name = first_name_input.value or ''
                    company.last_name = last_name_input.value or ''
                    company.street = street_input.value or ''
                    company.postal_code = postal_code_input.value or ''
                    company.city = city_input.value or ''
                    company.email = email_input.value or ''
                    company.phone = phone_input.value or ''
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

def render_invoice_editor(session, comp, d):
    ui.label('Neue Rechnung').classes('text-lg font-semibold text-slate-900 mb-4')

    customers = session.exec(select(Customer)).all()
    customer_options = {str(c.id): c.display_name for c in customers}

    selected_customer = ui.select(customer_options, label='Kunde').classes(C_INPUT + " w-full")
    invoice_date = ui.input('Datum', value=datetime.now().strftime('%Y-%m-%d')).classes(C_INPUT + " w-full")

    items = []
    totals_netto = ui.label('0,00 €').classes('font-mono text-sm text-slate-700')
    totals_brutto = ui.label('0,00 €').classes('font-mono text-sm text-slate-900 font-semibold')

    def calc_totals():
        netto = 0.0
        for item in items:
            qty = float(item['qty'].value or 0)
            price = float(item['price'].value or 0)
            netto += qty * price
        tax_rate = 0.0 if apply_ustg19.value else 0.19
        brutto = netto * (1 + tax_rate)
        totals_netto.set_text(f"{netto:,.2f} €")
        totals_brutto.set_text(f"{brutto:,.2f} €")
        return netto, brutto

    def remove_item(item):
        items.remove(item)
        item['row'].delete()
        calc_totals()

    with ui.column().classes('w-full gap-3'):
        ui.label('Rechnungsposten').classes(C_SECTION_TITLE)
        items_container = ui.column().classes('w-full gap-3')

        def add_item():
            item = {}
            with items_container:
                with ui.row().classes('w-full gap-3 items-end flex-wrap') as row:
                    desc = ui.input('Beschreibung').classes(C_INPUT + " flex-1 min-w-[220px]")
                    qty = ui.number('Menge', value=1, format='%.2f').classes(C_INPUT + " w-28 min-w-[110px]")
                    price = ui.number('Einzelpreis', value=0, format='%.2f').classes(C_INPUT + " w-32 min-w-[140px]")
                    ui.button('Entfernen', on_click=lambda: remove_item(item)).classes(C_BTN_SEC)
            item.update({'row': row, 'desc': desc, 'qty': qty, 'price': price})
            items.append(item)
            qty.on('change', calc_totals)
            price.on('change', calc_totals)
            calc_totals()

        ui.button('Posten hinzufügen', icon='add', on_click=add_item).classes(C_BTN_SEC + " w-fit")

    with ui.row().classes('w-full justify-end gap-6 mt-4'):
        with ui.column().classes('items-end'):
            ui.label('Netto').classes('text-xs text-slate-500')
            totals_netto
        with ui.column().classes('items-end'):
            ui.label('Brutto (inkl. 19% USt)').classes('text-xs text-slate-500')
            totals_brutto

    apply_ustg19 = ui.checkbox('§ 19 UStG anwenden').classes('text-sm text-slate-600')

    def validate_finalization():
        if not selected_customer.value:
            ui.notify('Bitte Kunde auswählen', color='red')
            return False
        if not invoice_date.value:
            ui.notify('Bitte Datum angeben', color='red')
            return False
        if not items:
            ui.notify('Bitte mindestens einen Posten hinzufügen', color='red')
            return False
        for item in items:
            desc = (item['desc'].value or '').strip()
            qty = float(item['qty'].value or 0)
            price = float(item['price'].value or 0)
            if not desc:
                ui.notify('Bitte Beschreibung ausfüllen', color='red')
                return False
            if qty <= 0 or price <= 0:
                ui.notify('Bitte gültige Beträge eingeben', color='red')
                return False
        netto, _ = calc_totals()
        if netto <= 0:
            ui.notify('Bitte gültige Beträge eingeben', color='red')
            return False
        return True

    def save_draft():
        if not selected_customer.value:
            return ui.notify('Bitte Kunde auswählen', color='red')

        _, brutto = calc_totals()

        with Session(engine) as inner:
            customer = inner.get(Customer, int(selected_customer.value))
            if not customer:
                return ui.notify('Fehlende Daten', color='red')

            invoice = Invoice(
                customer_id=customer.id,
                nr=None,
                date=invoice_date.value or datetime.now().strftime('%Y-%m-%d'),
                total_brutto=brutto,
                status='Entwurf'
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

            inner.commit()

        ui.notify('Entwurf gespeichert', color='green')
        d.close()
        ui.navigate.to('/')

    def finalize_invoice():
        if not validate_finalization():
            return

        _, brutto = calc_totals()

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

            generate_invoice_pdf(company, customer, invoice, items, apply_ustg19.value)

        ui.notify('Rechnung erstellt', color='green')
        app.storage.user['page'] = 'dashboard'
        d.close()
        ui.navigate.to('/')

    def cancel_editor():
        d.close()
        ui.navigate.to('/')

    with ui.row().classes('w-full justify-end gap-2 mt-6'):
        ui.button('Abbrechen', on_click=cancel_editor).classes(C_BTN_SEC)
        ui.button('Entwurf speichern', icon='save', on_click=save_draft).classes(C_BTN_SEC)
        ui.button('Finalisieren & Buchen', icon='check', on_click=finalize_invoice).classes(C_BTN_PRIM)

    return apply_ustg19, calc_totals

def render_invoice_create(session, comp):
    ui.label('Rechnung erstellen').classes(C_PAGE_TITLE + " mb-4")
    customers = session.exec(select(Customer)).all()
    customer_options = {str(c.id): c.display_name for c in customers}
    templates = ['Standard', 'Dienstleistung', 'Beratung']

    last_pdf_path = app.storage.user.get('last_invoice_pdf')

    with ui.row().classes('w-full gap-6 items-start flex-wrap md:flex-nowrap'):
        with ui.column().classes('w-full md:w-[680px] gap-4'):
            with ui.card().classes(C_CARD + " p-6 w-full"):
                ui.label('Rechnungsdaten').classes(C_SECTION_TITLE + " mb-4")
                template_select = ui.select(templates, value=templates[0], label='Vorlage').classes(C_INPUT)
                selected_customer = ui.select(customer_options, label='Kunde').classes(C_INPUT)
                invoice_date = ui.input('Datum', value=datetime.now().strftime('%Y-%m-%d')).classes(C_INPUT)
                intro_text = ui.textarea('Einleitungstext').classes(C_INPUT)

            with ui.card().classes(C_CARD + " p-6 w-full"):
                ui.label('Rechnungsposten').classes(C_SECTION_TITLE + " mb-4")
                items = []
                totals_netto = ui.label('0,00 €').classes('font-mono text-sm text-slate-700')
                totals_brutto = ui.label('0,00 €').classes('font-mono text-sm text-slate-900 font-semibold')
                brutto_label = ui.label('Brutto (inkl. 19% USt)').classes('text-xs text-slate-500')
                ust_toggle = ui.checkbox('USt berechnen (19%)', value=True).classes('text-sm text-slate-600')
                items_container = ui.column().classes('w-full gap-3 mt-3')

                def calc_totals():
                    netto = 0.0
                    ust_enabled = bool(ust_toggle.value)
                    for item in items:
                        qty = float(item['qty'].value or 0)
                        price = float(item['price'].value or 0)
                        is_brutto = bool(item['is_brutto'].value)
                        unit_netto = price
                        if ust_enabled and is_brutto:
                            unit_netto = price / 1.19
                        netto += qty * unit_netto
                    brutto = netto * (1.19 if ust_enabled else 1.0)
                    totals_netto.set_text(f"{netto:,.2f} €")
                    totals_brutto.set_text(f"{brutto:,.2f} €")
                    brutto_label.set_text('Brutto (inkl. 19% USt)' if ust_enabled else 'Brutto')
                    return netto, brutto

                def remove_item(item):
                    items.remove(item)
                    item['row'].delete()
                    calc_totals()

                def add_item():
                    item = {}
                    with items_container:
                        with ui.row().classes('w-full gap-3 items-end flex-wrap') as row:
                            desc = ui.input('Beschreibung').classes(C_INPUT + " flex-1 min-w-[220px]")
                            qty = ui.number('Menge', value=1, format='%.2f').classes(C_INPUT + " w-28 min-w-[110px]")
                            price = ui.number('Einzelpreis', value=0, format='%.2f').classes(C_INPUT + " w-32 min-w-[140px]")
                            is_brutto = ui.checkbox('Brutto', value=False).classes('text-xs text-slate-500')
                            ui.button('Entfernen', on_click=lambda: remove_item(item)).classes(C_BTN_SEC)
                    item.update({'row': row, 'desc': desc, 'qty': qty, 'price': price, 'is_brutto': is_brutto})
                    items.append(item)
                    qty.on('change', calc_totals)
                    price.on('change', calc_totals)
                    is_brutto.on('change', calc_totals)
                    calc_totals()

                ui.button('Posten hinzufügen', icon='add', on_click=add_item).classes(C_BTN_SEC + " w-fit")
                ust_toggle.on('change', calc_totals)

                with ui.row().classes('w-full justify-end gap-6 mt-4'):
                    with ui.column().classes('items-end'):
                        ui.label('Netto').classes('text-xs text-slate-500')
                        totals_netto
                    with ui.column().classes('items-end'):
                        brutto_label
                        totals_brutto

            with ui.card().classes(C_CARD + " p-6 w-full"):
                ui.label('Aktionen').classes(C_SECTION_TITLE + " mb-4")
                send_after_finalize = ui.checkbox('E-Mail nach Finalisieren anbieten', value=True).classes('text-sm text-slate-600 mb-2')

                def validate_finalization():
                    if not selected_customer.value:
                        ui.notify('Bitte Kunde auswählen', color='red')
                        return False
                    if not invoice_date.value:
                        ui.notify('Bitte Datum angeben', color='red')
                        return False
                    if not items:
                        ui.notify('Bitte mindestens einen Posten hinzufügen', color='red')
                        return False
                    for item in items:
                        desc = (item['desc'].value or '').strip()
                        qty = float(item['qty'].value or 0)
                        price = float(item['price'].value or 0)
                        if not desc:
                            ui.notify('Bitte Beschreibung ausfüllen', color='red')
                            return False
                        if qty <= 0 or price <= 0:
                            ui.notify('Bitte gültige Beträge eingeben', color='red')
                            return False
                    netto, _ = calc_totals()
                    if netto <= 0:
                        ui.notify('Bitte gültige Beträge eingeben', color='red')
                        return False
                    return True

                with ui.dialog() as mail_dialog, ui.card().classes(C_CARD + " p-5"):
                    ui.label('Rechnung per E-Mail senden?').classes(C_SECTION_TITLE + " mb-2")
                    mail_info = ui.label('').classes('text-xs text-slate-500 mb-3')
                    send_action = {'fn': lambda: None}
                    def skip_send():
                        mail_dialog.close()
                        app.storage.user['page'] = 'invoices'
                        ui.navigate.to('/')

                    def send_invoice_email(company, customer, invoice, pdf_path):
                        if not customer.email:
                            return ui.notify('Kunde hat keine E-Mail-Adresse', color='red')
                        if not company.smtp_server or not company.smtp_user or not company.smtp_password:
                            return ui.notify('SMTP Einstellungen fehlen', color='red')
                        msg = EmailMessage()
                        msg['Subject'] = f"Rechnung {invoice.nr}"
                        msg['From'] = company.smtp_user
                        msg['To'] = customer.email
                        msg.set_content(f"Guten Tag {customer.display_name},\n\nim Anhang finden Sie Ihre Rechnung {invoice.nr}.\n\nViele Grüße\n{company.name}")
                        with open(pdf_path, 'rb') as f:
                            msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename=os.path.basename(pdf_path))
                        try:
                            with smtplib.SMTP(company.smtp_server, company.smtp_port) as server:
                                server.starttls()
                                server.login(company.smtp_user, company.smtp_password)
                                server.send_message(msg)
                            ui.notify('E-Mail versendet', color='green')
                            mail_dialog.close()
                            app.storage.user['page'] = 'invoices'
                            ui.navigate.to('/')
                        except Exception:
                            ui.notify('E-Mail Versand fehlgeschlagen', color='red')

                    ui.button('E-Mail senden', icon='mail', on_click=lambda: send_action['fn']()).classes(C_BTN_PRIM)
                    ui.button('Überspringen', on_click=skip_send).classes(C_BTN_SEC)

                def save_draft():
                    if not selected_customer.value:
                        return ui.notify('Bitte Kunde auswählen', color='red')

                    _, brutto = calc_totals()

                    with Session(engine) as inner:
                        customer = inner.get(Customer, int(selected_customer.value))
                        if not customer:
                            return ui.notify('Fehlende Daten', color='red')

                        invoice = Invoice(
                            customer_id=customer.id,
                            nr=None,
                            date=invoice_date.value or datetime.now().strftime('%Y-%m-%d'),
                            total_brutto=brutto,
                            status='Entwurf'
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

                        inner.commit()

                    ui.notify('Entwurf gespeichert', color='green')
                    app.storage.user['page'] = 'invoices'
                    ui.navigate.to('/')

                def finalize_invoice():
                    if not validate_finalization():
                        return

                    _, brutto = calc_totals()
                    ust_enabled = bool(ust_toggle.value)

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

                        pdf_items = []
                        for item in items:
                            pdf_items.append({
                                'desc': item['desc'].value or '',
                                'qty': float(item['qty'].value or 0),
                                'price': float(item['price'].value or 0),
                                'is_brutto': bool(item['is_brutto'].value),
                            })
                        pdf_path = generate_invoice_pdf(
                            company,
                            customer,
                            invoice,
                            pdf_items,
                            apply_ustg19=not ust_enabled,
                            template_name=template_select.value or '',
                            intro_text=intro_text.value or ''
                        )

                    ui.notify('Rechnung erstellt', color='green')
                    app.storage.user['last_invoice_pdf'] = pdf_path
                    render_preview(pdf_path)
                    if send_after_finalize.value:
                        mail_info.set_text(f"Empfänger: {customer.email or 'Keine E-Mail hinterlegt'}")
                        send_action['fn'] = lambda c=company, cu=customer, i=invoice, p=pdf_path: send_invoice_email(c, cu, i, p)
                        mail_dialog.open()
                    else:
                        app.storage.user['page'] = 'invoices'
                        ui.navigate.to('/')

                def cancel_editor():
                    app.storage.user['page'] = 'invoices'
                    ui.navigate.to('/')

                with ui.row().classes('w-full justify-end gap-2 mt-4'):
                    ui.button('Abbrechen', on_click=cancel_editor).classes(C_BTN_SEC)
                    ui.button('Entwurf speichern', icon='save', on_click=save_draft).classes(C_BTN_SEC)
                    ui.button('Finalisieren & Buchen', icon='check', on_click=finalize_invoice).classes(C_BTN_PRIM)

        with ui.column().classes('w-full md:flex-1 gap-4'):
            with ui.card().classes(C_CARD + " p-6 w-full"):
                ui.label('PDF Vorschau').classes(C_SECTION_TITLE + " mb-4")
                preview_container = ui.column().classes('w-full gap-3')

                def render_preview(pdf_path):
                    preview_container.clear()
                    if pdf_path and os.path.exists(pdf_path):
                        with preview_container:
                            ui.pdf(pdf_path).classes('w-full h-[650px]')
                            ui.button('Download', icon='download', on_click=lambda p=pdf_path: ui.download(p)).classes(C_BTN_SEC + " w-fit")
                    else:
                        ui.label('Keine Vorschau verfügbar').classes('text-slate-400 text-sm')

                render_preview(last_pdf_path)

def render_invoices(session, comp):
    with ui.row().classes('w-full justify-between items-center mb-6'):
        ui.label('Rechnungen').classes(C_PAGE_TITLE)
        with ui.row().classes('gap-3'):
            with ui.dialog() as d_import, ui.card().classes(C_CARD + " p-5"):
                ui.label('CSV Import').classes(C_SECTION_TITLE + " mb-4")
                import_payload = {'content': None, 'filename': '', 'rows_total': 0}
                preview_container = ui.column().classes('w-full gap-3')
                stats_label = ui.label('').classes('text-xs text-slate-500')
                progress = ui.linear_progress(value=0).classes('w-full')
                
                def handle(e: events.UploadEventArguments):
                    try:
                        content = e.content.read()
                    except:
                        ui.notify('Upload Fehler', color='red')
                        return

                    filename = getattr(e, 'name', '') or getattr(getattr(e, 'file', None), 'name', '')
                    progress.value = 0.3
                    df, err = load_invoice_import_dataframe(content, filename)
                    preview_container.clear()
                    stats_label.set_text('')
                    confirm_btn.disable()
                    if err: 
                        ui.notify(err, color='red')
                        return
                    progress.value = 0.6

                    import_payload['content'] = content
                    import_payload['filename'] = filename
                    import_payload['rows_total'] = len(df.index)

                    with preview_container:
                        ui.label('Vorschau').classes(C_SECTION_TITLE + " mt-4")
                        preview_df = df.head(20).fillna('')
                        rows = []
                        for i, row in preview_df.iterrows():
                            row_data = {'_row': str(i + 1)}
                            for col in preview_df.columns:
                                row_data[col] = str(row[col])
                            rows.append(row_data)
                        columns = [{'name': '_row', 'label': '#', 'field': '_row'}]
                        columns += [{'name': col, 'label': col, 'field': col} for col in preview_df.columns]
                        ui.table(columns=columns, rows=rows, row_key='_row').classes('w-full')
                    stats_label.set_text(f"Zeilen gesamt: {import_payload['rows_total']}")
                    progress.value = 0.8
                    confirm_btn.enable()

                def confirm_import():
                    if not import_payload['content']:
                        ui.notify('Bitte zuerst eine Datei hochladen.', color='red')
                        return
                    progress.value = 0.9
                    c, err = process_invoice_import(import_payload['content'], session, comp.id, import_payload['filename'])
                    if err: ui.notify(err, color='red')
                    else: 
                        ui.notify(f"{c} Importiert ({c}/{import_payload['rows_total']})", color='green')
                        progress.value = 1.0
                        d_import.close()
                        ui.navigate.to('/')

                def cancel_import():
                    import_payload['content'] = None
                    import_payload['filename'] = ''
                    import_payload['rows_total'] = 0
                    preview_container.clear()
                    stats_label.set_text('')
                    progress.value = 0
                    confirm_btn.disable()
                    d_import.close()

                ui.upload(on_upload=handle, auto_upload=True).classes('w-full').props('accept=.csv,.xls,.xlsx')
                with ui.row().classes('w-full justify-between items-center mt-3'):
                    confirm_btn = ui.button('Import bestätigen', icon='check', on_click=confirm_import).classes(C_BTN_PRIM + " w-fit")
                    ui.button('Abbrechen', on_click=cancel_import).classes(C_BTN_SEC + " w-fit")
                confirm_btn.disable()

            with ui.dialog() as d, ui.card().classes(C_CARD + " w-[900px] p-6"):
                apply_ustg19, calc_totals = render_invoice_editor(session, comp, d)
                apply_ustg19.on('change', calc_totals)

            ui.button('Import', icon='upload', on_click=d_import.open).classes(C_BTN_SEC)
            ui.button('Rechnung erstellen', icon='add', on_click=d.open).classes(C_BTN_PRIM)

    correction_payload = {'invoice_id': None}
    with ui.dialog() as correction_dialog, ui.card().classes(C_CARD + " p-5 w-[420px]"):
        ui.label('Korrektur erstellen').classes(C_SECTION_TITLE + " mb-2")
        ui.label('Wähle die Art der Korrektur.').classes('text-xs text-slate-500 mb-3')
        correction_mode = ui.select(
            {'negative': 'Negative Posten', 'balance': 'Ausgleichsposten'},
            value='negative',
            label='Methode'
        ).classes(C_INPUT)

        def confirm_correction():
            if not correction_payload['invoice_id']:
                return ui.notify('Keine Rechnung ausgewählt', color='red')
            use_negative = correction_mode.value == 'negative'
            correction, err = create_correction(correction_payload['invoice_id'], use_negative_items=use_negative)
            if err:
                return ui.notify(err, color='red')
            ui.notify('Korrektur-Entwurf erstellt', color='green')
            correction_dialog.close()
            ui.navigate.to('/')

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('Abbrechen', on_click=correction_dialog.close).classes(C_BTN_SEC)
            ui.button('Erstellen', icon='check', on_click=confirm_correction).classes(C_BTN_PRIM)
    invs = session.exec(select(Invoice)).all()
    with ui.card().classes(C_CARD + " p-0 overflow-hidden mt-8"):
        with ui.row().classes(C_TABLE_HEADER):
            ui.label('Status').classes('w-24 font-medium text-slate-500 text-sm')
            ui.label('Nr').classes('w-16 font-medium text-slate-500 text-sm')
            ui.label('Datum').classes('w-24 font-medium text-slate-500 text-sm')
            ui.label('Kunde').classes('flex-1 font-medium text-slate-500 text-sm')
            ui.label('Betrag').classes('w-24 text-right font-medium text-slate-500 text-sm')
            ui.label('Korr.').classes('w-28 text-right font-medium text-slate-500 text-sm')
            ui.label('PDF').classes('w-24 text-right font-medium text-slate-500 text-sm')

        with ui.column().classes('w-full gap-0'):
            for i in invs:
                with ui.row().classes(C_TABLE_ROW):
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
                    ui.label(cname).classes('flex-1 font-semibold text-slate-900 text-sm truncate')

                    ui.label(f"{i.total_brutto:,.2f} €").classes('w-24 text-right font-mono font-medium text-sm')
                    with ui.row().classes('w-28 justify-end'):
                        if i.status != 'Entwurf':
                            ui.button('Korrektur', icon='edit', on_click=lambda inv_id=i.id: (correction_payload.__setitem__('invoice_id', inv_id), correction_dialog.open())).classes(C_BTN_SEC + " w-full")
                        else:
                            ui.label('-').classes('text-slate-300 text-sm w-full text-right')
                    pdf_path = f"./storage/invoices/invoice_{i.nr}.pdf"
                    with ui.row().classes('w-24 justify-end'):
                        if i.nr and os.path.exists(pdf_path):
                            ui.button('Download', icon='download', on_click=lambda p=pdf_path: ui.download(p)).classes(C_BTN_SEC + " w-full")
                        else:
                            ui.label('-').classes('text-slate-300 text-sm w-full text-right')

def render_expenses(session, comp):
    with ui.row().classes('w-full justify-between items-center mb-6'):
        ui.label('Ausgaben').classes(C_PAGE_TITLE)
        with ui.dialog() as d, ui.card().classes(C_CARD + " p-5"):
            ui.label('CSV Import').classes(C_SECTION_TITLE + " mb-4")
            import_payload = {'content': None, 'filename': '', 'rows_total': 0}
            preview_container = ui.column().classes('w-full gap-3')
            stats_label = ui.label('').classes('text-xs text-slate-500')
            progress = ui.linear_progress(value=0).classes('w-full')

            def handle(e: events.UploadEventArguments):
                try: content = e.content.read()
                except: return ui.notify('Upload Fehler', color='red')
                filename = getattr(e, 'name', '') or getattr(getattr(e, 'file', None), 'name', '')
                progress.value = 0.3
                df, err = load_expense_import_dataframe(content, filename)
                preview_container.clear()
                stats_label.set_text('')
                confirm_btn.disable()
                if err: 
                    ui.notify(err, color='red')
                    return
                progress.value = 0.6

                import_payload['content'] = content
                import_payload['filename'] = filename
                import_payload['rows_total'] = len(df.index)

                with preview_container:
                    ui.label('Vorschau').classes(C_SECTION_TITLE + " mt-4")
                    preview_df = df.head(20).fillna('')
                    rows = []
                    for i, row in preview_df.iterrows():
                        row_data = {'_row': str(i + 1)}
                        for col in preview_df.columns:
                            row_data[col] = str(row[col])
                        rows.append(row_data)
                    columns = [{'name': '_row', 'label': '#', 'field': '_row'}]
                    columns += [{'name': col, 'label': col, 'field': col} for col in preview_df.columns]
                    ui.table(columns=columns, rows=rows, row_key='_row').classes('w-full')
                stats_label.set_text(f"Zeilen gesamt: {import_payload['rows_total']}")
                progress.value = 0.8
                confirm_btn.enable()

            def confirm_import():
                if not import_payload['content']:
                    ui.notify('Bitte zuerst eine Datei hochladen.', color='red')
                    return
                progress.value = 0.9
                c, err = process_expense_import(import_payload['content'], session, comp.id, import_payload['filename'])
                if err: ui.notify(err, color='red')
                else: 
                    ui.notify(f"{c} Importiert ({c}/{import_payload['rows_total']})", color='green')
                    progress.value = 1.0
                    d.close()
                    ui.navigate.to('/')

            def cancel_import():
                import_payload['content'] = None
                import_payload['filename'] = ''
                import_payload['rows_total'] = 0
                preview_container.clear()
                stats_label.set_text('')
                progress.value = 0
                confirm_btn.disable()
                d.close()

            ui.upload(on_upload=handle, auto_upload=True).classes('w-full').props('accept=.csv,.xls,.xlsx')
            with ui.row().classes('w-full justify-between items-center mt-3'):
                confirm_btn = ui.button('Import bestätigen', icon='check', on_click=confirm_import).classes(C_BTN_PRIM + " w-fit")
                ui.button('Abbrechen', on_click=cancel_import).classes(C_BTN_SEC + " w-fit")
            confirm_btn.disable()
        ui.button('Import', icon='upload', on_click=d.open).classes(C_BTN_PRIM)

    exps = session.exec(select(Expense)).all()
    with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
        # HEADER
        with ui.row().classes(C_TABLE_HEADER):
            ui.label('Datum').classes('w-24 font-medium text-slate-500 text-sm')
            ui.label('Beschreibung').classes('flex-1 font-medium text-slate-500 text-sm')
            ui.label('Kategorie').classes('w-32 font-medium text-slate-500 text-sm')
            ui.label('Betrag').classes('w-24 text-right font-medium text-slate-500 text-sm')
            ui.label('Aktionen').classes('w-32 text-right font-medium text-slate-500 text-sm')

        # ROWS
        with ui.column().classes('w-full gap-0'):
            for e in exps:
                with ui.row().classes(C_TABLE_ROW):
                    ui.label(e.date).classes('w-24 text-slate-500 font-mono text-xs')
                    ui.label(e.description).classes('flex-1 font-semibold text-slate-900 text-sm truncate')
                    ui.label(e.category).classes('w-32 text-slate-500 text-sm')
                    ui.label(f"- {e.amount:,.2f} €").classes('w-24 text-right text-red-600 font-mono font-medium text-sm')
                    with ui.row().classes('w-32 justify-end gap-2'):
                        with ui.dialog() as d_edit, ui.card().classes(C_CARD + " p-5"):
                            ui.label('Ausgabe bearbeiten').classes(C_SECTION_TITLE + " mb-4")
                            edit_date = ui.input('Datum', value=e.date).classes(C_INPUT)
                            edit_description = ui.input('Beschreibung', value=e.description).classes(C_INPUT)
                            edit_category = ui.input('Kategorie', value=e.category).classes(C_INPUT)
                            edit_amount = ui.number('Betrag', value=e.amount, format='%.2f').classes(C_INPUT)

                            ui.label('Integrationen').classes(C_SECTION_TITLE + " mt-4")
                            edit_integrations = ui.column().classes('w-full gap-3')
                            edit_integrations.set_visibility(bool(e.source or e.external_id or e.webhook_url))
                            with ui.row().classes('w-full justify-start'):
                                ui.button('Webhook verbinden', icon='link', on_click=lambda: edit_integrations.set_visibility(True)).classes(C_BTN_SEC)

                            with edit_integrations:
                                edit_source = ui.input('Quelle', value=e.source or '').classes(C_INPUT)
                                edit_external_id = ui.input('External ID', value=e.external_id or '').classes(C_INPUT)
                                edit_webhook_url = ui.input('Webhook URL', value=e.webhook_url or '').classes(C_INPUT)

                            def save_edit_expense(expense_id=e.id):
                                if not edit_date.value: return ui.notify('Bitte Datum angeben', color='red')
                                if not edit_description.value: return ui.notify('Bitte Beschreibung angeben', color='red')
                                try: amount_val = float(edit_amount.value or 0)
                                except: return ui.notify('Bitte gültigen Betrag angeben', color='red')
                                with Session(engine) as inner:
                                    exp = inner.get(Expense, expense_id)
                                    if not exp: return ui.notify('Ausgabe nicht gefunden', color='red')
                                    exp.date = str(edit_date.value or '')
                                    exp.description = str(edit_description.value or '')
                                    exp.category = str(edit_category.value or '')
                                    exp.amount = amount_val
                                    exp.source = str(edit_source.value or '')
                                    exp.external_id = str(edit_external_id.value or '')
                                    exp.webhook_url = str(edit_webhook_url.value or '')
                                    inner.add(exp)
                                    inner.commit()
                                ui.notify('Ausgabe aktualisiert', color='green')
                                d_edit.close()
                                ui.navigate.to('/')

                            ui.button('Speichern', icon='save', on_click=save_edit_expense).classes(C_BTN_PRIM + " w-fit mt-2")

                        def delete_expense(expense_id=e.id):
                            with Session(engine) as inner:
                                exp = inner.get(Expense, expense_id)
                                if not exp: return ui.notify('Ausgabe nicht gefunden', color='red')
                                inner.delete(exp)
                                inner.commit()
                            ui.notify('Ausgabe gelöscht', color='green')
                            ui.navigate.to('/')

                        ui.button(icon='edit', on_click=d_edit.open).classes(C_BTN_SEC)
                        ui.button(icon='delete', on_click=delete_expense).classes(C_BTN_SEC)
