from nicegui import ui, app, events
from sqlmodel import Session, select
from datetime import datetime
import os
import base64
import json
from urllib.parse import urlencode

# Imports
from data import (
    Company, Customer, Invoice, InvoiceItem, InvoiceItemTemplate, Expense, 
    engine, process_customer_import, process_expense_import, 
    log_audit_action, InvoiceStatus
)
from renderer import render_invoice_to_pdf_bytes
from actions import create_correction
from styles import C_CARD, C_BTN_PRIM, C_BTN_SEC, C_INPUT, C_PAGE_TITLE, C_SECTION_TITLE, C_TABLE_HEADER, C_TABLE_ROW, C_BADGE_GREEN
from ui_components import format_invoice_status, invoice_status_badge, kpi_card, sticky_header
from logic import finalize_invoice_logic

# Helper
def log_invoice_action(action, invoice_id):
    with Session(engine) as s:
        log_audit_action(s, action, invoice_id=invoice_id)
        s.commit()

def download_invoice_file(invoice):
    if invoice and invoice.id: log_invoice_action("PRINT", invoice.id)
    if not invoice.pdf_filename:
        pdf_bytes = render_invoice_to_pdf_bytes(invoice)
        filename = f"rechnung_{invoice.nr}.pdf" if invoice.nr else "rechnung.pdf"
        ui.download(pdf_bytes, filename=filename)
        return
    pdf_path = invoice.pdf_filename
    if not os.path.isabs(pdf_path) and not pdf_path.startswith("storage/"):
        pdf_path = f"storage/invoices/{pdf_path}"
    if os.path.exists(pdf_path): ui.download(pdf_path)
    else: ui.notify(f"PDF Datei fehlt: {pdf_path}", color="red")

def build_invoice_mailto(comp, customer, invoice):
    subject = f"Rechnung {invoice.nr or ''}".strip()
    amount = f"{invoice.total_brutto:,.2f} EUR"
    body_lines = [
        f"Guten Tag {customer.display_name if customer else ''},".strip(),
        "",
        f"im Anhang finden Sie Ihre Rechnung {invoice.nr or ''} vom {invoice.date} über {amount}.",
        "",
        "Viele Grüße",
        comp.name if comp else ""
    ]
    params = urlencode({
        "subject": subject,
        "body": "\n".join(line for line in body_lines if line is not None),
    })
    recipient = customer.email if customer and customer.email else ""
    return f"mailto:{recipient}?{params}"

def send_invoice_email(comp, customer, invoice):
    if not customer or not customer.email:
        ui.notify("Keine Email-Adresse beim Kunden hinterlegt", color="red")
        return
    mailto = build_invoice_mailto(comp, customer, invoice)
    ui.run_javascript(f"window.location.href = {json.dumps(mailto)}")

# --- DASHBOARD ---
def render_dashboard(session, comp):
    ui.label('Dashboard').classes(C_PAGE_TITLE + " mb-4")
    invs = session.exec(select(Invoice)).all()
    exps = session.exec(select(Expense)).all()
    
    umsatz = sum(i.total_brutto for i in invs if i.status == InvoiceStatus.FINALIZED)
    kosten = sum(e.amount for e in exps)
    offen = sum(i.total_brutto for i in invs if i.status == InvoiceStatus.FINALIZED)
    
    with ui.grid(columns=3).classes('w-full gap-4 mb-6'):
        kpi_card("Umsatz", f"{umsatz:,.2f} €", "trending_up", "text-emerald-500")
        kpi_card("Ausgaben", f"{kosten:,.2f} €", "trending_down", "text-rose-500")
        kpi_card("Offen", f"{offen:,.2f} €", "schedule", "text-blue-500")

    ui.label('Neueste Rechnungen').classes(C_SECTION_TITLE + " mb-2")
    with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
        with ui.row().classes(C_TABLE_HEADER):
            ui.label('Nr.').classes('w-20 font-bold text-xs text-slate-500')
            ui.label('Kunde').classes('flex-1 font-bold text-xs text-slate-500')
            ui.label('Betrag').classes('w-24 text-right font-bold text-xs text-slate-500')
            ui.label('Status').classes('w-24 text-right font-bold text-xs text-slate-500')
        
        for inv in sorted(invs, key=lambda x: x.id, reverse=True)[:5]:
             def go(i=inv):
                if i.status == InvoiceStatus.DRAFT:
                    app.storage.user['invoice_draft_id'] = i.id
                    app.storage.user['page'] = 'invoice_create'
                else:
                    app.storage.user['page'] = 'invoices'
                ui.navigate.to('/')

             with ui.row().classes(C_TABLE_ROW + " cursor-pointer hover:bg-slate-50").on('click', lambda _, x=inv: go(x)):
                ui.label(f"#{inv.nr}" if inv.nr else "-").classes('w-20 font-mono text-xs')
                c = session.get(Customer, inv.customer_id) if inv.customer_id else None
                ui.label(c.display_name if c else "?").classes('flex-1 text-sm')
                ui.label(f"{inv.total_brutto:,.2f} €").classes('w-24 text-right font-mono text-sm')
                ui.label(format_invoice_status(inv.status)).classes(invoice_status_badge(inv.status) + " ml-auto")

# --- EDITOR ---
def render_invoice_create(session, comp):
    draft_id = app.storage.user.get('invoice_draft_id')
    draft = session.get(Invoice, draft_id) if draft_id else None
    customers = session.exec(select(Customer)).all()
    cust_opts = {str(c.id): c.display_name for c in customers}
    template_items = session.exec(select(InvoiceItemTemplate).where(InvoiceItemTemplate.company_id == comp.id)).all()

    init_items = []
    if draft:
        db_items = session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == draft.id)).all()
        for i in db_items:
             init_items.append({'desc': i.description, 'qty': i.quantity, 'price': i.unit_price, 'is_brutto': False})
    if not init_items: init_items.append({'desc': '', 'qty': 1.0, 'price': 0.0, 'is_brutto': False})

    state = {
        'items': init_items,
        'customer_id': str(draft.customer_id) if draft else None,
        'date': draft.date if draft else datetime.now().strftime('%Y-%m-%d'),
        'delivery_date': draft.delivery_date if draft else datetime.now().strftime('%Y-%m-%d'),
        'title': draft.title if draft else 'Rechnung',
        'ust': True
    }
    
    # Iframe Preview
    preview_html = None

    def update_preview():
        cust_id = state['customer_id']
        rec_n, rec_s, rec_z, rec_c = "", "", "", ""
        if cust_id:
            c = session.get(Customer, int(cust_id))
            if c: rec_n, rec_s, rec_z, rec_c = c.display_name, c.strasse, c.plz, c.ort
        
        final_n = rec_name.value if rec_name.value else rec_n
        final_s = rec_street.value if rec_street.value else rec_s
        final_z = rec_zip.value if rec_zip.value else rec_z
        final_c = rec_city.value if rec_city.value else rec_c

        inv = Invoice(
            nr=comp.next_invoice_nr, title=state['title'], date=state['date'], delivery_date=state['delivery_date'],
            recipient_name=final_n, recipient_street=final_s, recipient_postal_code=final_z, recipient_city=final_c
        )
        inv.__dict__['line_items'] = state['items']
        inv.__dict__['tax_rate'] = 0.19 if ust_switch.value else 0.0
        
        try:
            pdf = render_invoice_to_pdf_bytes(inv)
            b64 = base64.b64encode(pdf).decode('utf-8')
            # Iframe 100% height fix
            if preview_html:
                preview_html.content = f'<iframe src="data:application/pdf;base64,{b64}" style="width:100%; height:100%; border:none;"></iframe>'
        except Exception as e: print(e)

    def on_finalize():
        if not state['customer_id']: return ui.notify('Kunde fehlt', color='red')
        with Session(engine) as inner:
            with inner.begin():
                finalize_invoice_logic(
                    inner, comp.id, int(state['customer_id']),
                    state['title'], state['date'], state['delivery_date'],
                    {'name': rec_name.value, 'street': rec_street.value, 'zip': rec_zip.value, 'city': rec_city.value},
                    state['items'], ust_switch.value
                )
        ui.notify('Erstellt', color='green')
        app.storage.user['invoice_draft_id'] = None
        ui.navigate.to('/')

    def on_save_draft():
        with Session(engine) as inner:
            if draft_id: inv = inner.get(Invoice, draft_id)
            else: inv = Invoice(status=InvoiceStatus.DRAFT)
            
            if state['customer_id']: inv.customer_id = int(state['customer_id'])
            inv.title = state['title']
            inv.date = state['date']
            inv.delivery_date = state['delivery_date']
            inv.total_brutto = 0
            inner.add(inv)
            inner.commit()
            
            exist = inner.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == inv.id)).all()
            for x in exist: inner.delete(x)
            for i in state['items']:
                 inner.add(InvoiceItem(invoice_id=inv.id, description=i['desc'], quantity=float(i['qty']), unit_price=float(i['price'])))
            inner.commit()
        ui.notify('Gespeichert', color='green')
        ui.navigate.to('/')

    sticky_header('Rechnungs-Editor', on_cancel=lambda: ui.navigate.to('/'), on_save=on_save_draft, on_finalize=on_finalize)

    with ui.column().classes('w-full h-[calc(100vh-64px)] p-0 m-0'):
        with ui.splitter(value=40).props('horizontal').classes('w-full flex-grow') as splitter:
            # LINKS
            with splitter.before:
                with ui.column().classes('w-full p-4 gap-4 h-full overflow-y-auto'):
                    with ui.card().classes(C_CARD + " p-4 w-full"):
                        ui.label('Kopfdaten').classes(C_SECTION_TITLE)
                        cust_select = ui.select(cust_opts, label='Kunde', value=state['customer_id'], with_input=True).classes(C_INPUT)
                        def on_cust(e):
                            state['customer_id'] = e.value
                            if e.value:
                                c = session.get(Customer, int(e.value))
                                if c: rec_name.value = c.display_name; rec_street.value = c.strasse; rec_zip.value = c.plz; rec_city.value = c.ort
                            update_preview()
                        cust_select.on('update:model-value', on_cust)
                        
                        with ui.grid(columns=2).classes('w-full gap-2'):
                             ui.input('Titel', value=state['title'], on_change=lambda e: (state.update({'title': e.value}), update_preview())).classes(C_INPUT)
                             ui.input('Rechnung', value=state['date'], on_change=lambda e: (state.update({'date': e.value}), update_preview())).classes(C_INPUT)
                             ui.input('Lieferung', value=state['delivery_date'], on_change=lambda e: (state.update({'delivery_date': e.value}), update_preview())).classes(C_INPUT)

                    with ui.expansion('Anschrift anpassen').classes('w-full border border-slate-200 rounded bg-white text-sm'):
                        with ui.column().classes('p-3 gap-2 w-full'):
                            rec_name = ui.input('Name', on_change=update_preview).classes(C_INPUT+" dense")
                            rec_street = ui.input('Straße', on_change=update_preview).classes(C_INPUT+" dense")
                            with ui.row().classes('w-full gap-2'):
                                rec_zip = ui.input('PLZ', on_change=update_preview).classes(C_INPUT+" w-20 dense")
                                rec_city = ui.input('Ort', on_change=update_preview).classes(C_INPUT+" flex-1 dense")

                    with ui.card().classes(C_CARD + " p-4 w-full"):
                        with ui.row().classes('justify-between w-full'):
                            ui.label('Posten').classes(C_SECTION_TITLE)
                            ust_switch = ui.switch('19% MwSt', value=state['ust'], on_change=lambda e: (state.update({'ust': e.value}), update_preview())).props('dense color=grey-8')
                        
                        if template_items:
                            item_template_select = ui.select({str(t.id): t.title for t in template_items}, label='Vorlage', with_input=True).classes(C_INPUT + " mb-2 dense")

                        items_col = ui.column().classes('w-full gap-2')
                        def render_list():
                            items_col.clear()
                            with items_col:
                                for item in state['items']:
                                    with ui.row().classes('w-full gap-1 items-start bg-slate-50 p-2 rounded border'):
                                        ui.textarea(value=item['desc'], on_change=lambda e, i=item: (i.update({'desc': e.value}), update_preview())).classes('flex-1 dense text-sm').props('rows=1 placeholder="Text" auto-grow')
                                        with ui.column().classes('gap-1'):
                                            ui.number(value=item['qty'], on_change=lambda e, i=item: (i.update({'qty': float(e.value or 0)}), update_preview())).classes('w-16 dense')
                                            ui.number(value=item['price'], on_change=lambda e, i=item: (i.update({'price': float(e.value or 0)}), update_preview())).classes('w-20 dense')
                                        ui.button(icon='close', on_click=lambda i=item: (state['items'].remove(i), render_list(), update_preview())).classes('flat dense text-red')
                        render_list()
                        
                        def add_new(): state['items'].append({'desc':'', 'qty':1.0, 'price':0.0, 'is_brutto':False}); render_list()
                        def add_tmpl():
                             if not item_template_select.value: return
                             t = next((x for x in template_items if str(x.id)==item_template_select.value),None)
                             if t: state['items'].append({'desc':t.description,'qty':t.quantity,'price':t.unit_price,'is_brutto':False}); render_list(); update_preview(); item_template_select.value=None

                        with ui.row().classes('gap-2 mt-2'):
                            ui.button('Posten', icon='add', on_click=add_new).props('flat dense').classes('text-slate-600')
                            if template_items: ui.button('Vorlage', icon='playlist_add', on_click=add_tmpl).props('flat dense').classes('text-slate-600')

            # RECHTS
            with splitter.after:
                with ui.column().classes('w-full h-full bg-slate-200 p-0 m-0 overflow-hidden'):
                    preview_html = ui.html('', sanitize=False).classes('w-full h-full bg-slate-300')
    update_preview()

# --- OTHER PAGES (Settings, Customers, Expenses) ---
def render_invoices(session, comp):
    ui.label('Rechnungen').classes(C_PAGE_TITLE + " mb-4")
    with ui.row().classes('mb-4'):
        ui.button('Neue Rechnung', icon='add', on_click=lambda: (app.storage.user.__setitem__('invoice_draft_id', None), app.storage.user.__setitem__('page', 'invoice_create'), ui.navigate.to('/'))).classes(C_BTN_PRIM)
    invs = session.exec(select(Invoice).order_by(Invoice.id.desc())).all()
    with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
        with ui.row().classes(C_TABLE_HEADER):
            ui.label('Nr').classes('w-20 font-bold'); ui.label('Kunde').classes('flex-1 font-bold'); ui.label('Betrag').classes('w-24 text-right'); ui.label('').classes('w-32')
        for i in invs:
            def go(x=i):
                if x.status == InvoiceStatus.DRAFT: app.storage.user['invoice_draft_id']=x.id; app.storage.user['page']='invoice_create'
                ui.navigate.to('/')
            with ui.row().classes(C_TABLE_ROW + " cursor-pointer hover:bg-slate-50").on('click', lambda _, x=i: go(x)):
                ui.label(f"#{i.nr}" if i.nr else "-").classes('w-20 text-xs font-mono')
                c = session.get(Customer, i.customer_id) if i.customer_id else None
                ui.label(c.display_name if c else "?").classes('flex-1 text-sm')
                ui.label(f"{i.total_brutto:,.2f}").classes('w-24 text-right text-sm')
                with ui.row().classes('w-32 justify-end gap-1'):
                    if i.status == InvoiceStatus.FINALIZED:
                         with ui.element('div'):
                             with ui.row().classes('items-center gap-1'):
                                 loading_spinner = ui.spinner(size='sm').classes('text-slate-400')
                                 loading_label = ui.label('Wird vorbereitet…').classes('text-xs text-slate-500')
                                 loading_spinner.visible = False
                                 loading_label.visible = False

                                 def set_loading(active):
                                     loading_spinner.visible = active
                                     loading_label.visible = active
                                     if active: action_button.disable()
                                     else: action_button.enable()

                                 with ui.button(icon='more_vert').props('no-parent-event').classes('flat round dense text-slate-500') as action_button:
                                     with ui.menu().props('auto-close no-parent-event'):
                                         def on_download(p=f):
                                             ui.notify('Wird vorbereitet…')
                                             set_loading(True)
                                             try:
                                                 download_invoice(p)
                                             except Exception as e:
                                                 ui.notify(f"Fehler: {e}", color='red')
                                             set_loading(False)

                                         def on_send(x=i):
                                             ui.notify('Wird vorbereitet…')
                                             set_loading(True)
                                             try:
                                                 send_invoice_email(comp, session.get(Customer, x.customer_id) if x.customer_id else None, x)
                                             except Exception as e:
                                                 ui.notify(f"Fehler: {e}", color='red')
                                             set_loading(False)

                                         ui.menu_item('Download', on_click=on_download)
                                         ui.menu_item('Senden', on_click=on_send)

def render_ledger(session, comp):
    ui.label('Finanzen').classes(C_PAGE_TITLE + " mb-4")
    invs = session.exec(select(Invoice)).all()
    exps = session.exec(select(Expense)).all()

    def parse_date(value):
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return datetime.min

    items = []
    for i in invs:
        c = session.get(Customer, i.customer_id) if i.customer_id else None
        status = "Paid" if i.status == "Bezahlt" else "Draft" if i.status == InvoiceStatus.DRAFT or i.status == "Entwurf" else "Overdue"
        amount_label = f"{i.total_brutto:,.2f} €"
        items.append({
            'id': f"inv-{i.id}",
            'date': i.date,
            'type': 'INCOME',
            'type_label': 'Income',
            'type_class': C_BADGE_GREEN + " w-20",
            'amount': i.total_brutto,
            'amount_label': amount_label,
            'amount_class': 'w-24 text-right text-sm text-emerald-600',
            'status': status,
            'party': c.display_name if c else "?",
            'row_type': 'INVOICE',
            'invoice_id': i.id,
            'invoice_status': i.status,
            'customer_id': i.customer_id,
            'pdf_filename': i.pdf_filename,
            'nr': i.nr,
            'sort_date': parse_date(i.date),
        })
    for e in exps:
        vendor = e.source or e.category or e.description or "-"
        amount_label = f"-{e.amount:,.2f} €"
        items.append({
            'id': f"exp-{e.id}",
            'date': e.date,
            'type': 'EXPENSE',
            'type_label': 'Expense',
            'type_class': "bg-rose-50 text-rose-700 border border-rose-100 px-2 py-0.5 rounded-full text-xs font-medium text-center w-20",
            'amount': e.amount,
            'amount_label': amount_label,
            'amount_class': 'w-24 text-right text-sm text-rose-600',
            'status': 'Paid',
            'party': vendor,
            'row_type': 'EXPENSE',
            'expense_id': e.id,
            'sort_date': parse_date(e.date),
        })
    items.sort(key=lambda x: x['sort_date'], reverse=True)

    def on_edit(e):
        row = e.args[0]
        invoice_id = row.get('invoice_id')
        if not invoice_id: return
        app.storage.user['invoice_draft_id'] = invoice_id
        app.storage.user['page'] = 'invoice_create'
        ui.navigate.to('/')

    def on_download(e):
        row = e.args[0]
        filename = row.get('pdf_filename') or f"rechnung_{row.get('nr')}.pdf"
        download_invoice(f"storage/invoices/{filename}")

    def on_send(e):
        row = e.args[0]
        invoice_id = row.get('invoice_id')
        if not invoice_id: return
        i = session.get(Invoice, invoice_id)
        if not i: return
        c = session.get(Customer, i.customer_id) if i.customer_id else None
        send_invoice_email(comp, c, i)

    columns = [
        {'name': 'date', 'label': 'Datum', 'field': 'date', 'sortable': True, 'align': 'left'},
        {'name': 'type', 'label': 'Typ', 'field': 'type', 'sortable': True, 'align': 'left'},
        {'name': 'status', 'label': 'Status', 'field': 'status', 'sortable': True, 'align': 'left'},
        {'name': 'party', 'label': 'Kunde/Lieferant', 'field': 'party', 'sortable': True, 'align': 'left'},
        {'name': 'amount', 'label': 'Betrag', 'field': 'amount', 'sortable': True, 'align': 'right'},
        {'name': 'actions', 'label': '', 'field': 'id', 'sortable': False, 'align': 'right'},
    ]

    with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
        table = ui.table(columns=columns, rows=items, row_key='id').props('filter="filter" sort-by="date" sort-desc')
        table.classes('w-full')
        table.add_slot('top', r'''
            <div class="row items-center q-gutter-sm full-width">
                <q-input borderless dense debounce="300" color="primary" v-model="filter" placeholder="Filter...">
                    <template v-slot:append>
                        <q-icon name="search" />
                    </template>
                </q-input>
            </div>
        ''')
        table.add_slot('body-cell-type', r'''
            <q-td :props="props">
                <span :class="props.row.type_class">{{ props.row.type_label }}</span>
            </q-td>
        ''')
        table.add_slot('body-cell-amount', r'''
            <q-td :props="props" class="text-right">
                <span :class="props.row.amount_class">{{ props.row.amount_label }}</span>
            </q-td>
        ''')
        table.add_slot('body-cell-actions', r'''
            <q-td :props="props">
                <div class="row justify-end no-wrap q-gutter-xs">
                    <q-btn v-if="props.row.row_type === 'INVOICE' && (props.row.invoice_status === 'DRAFT' || props.row.invoice_status === 'Entwurf')" icon="edit" flat dense @click="$emit('edit', props.row)" />
                    <q-btn v-if="props.row.row_type === 'INVOICE' && (props.row.invoice_status === 'FINALIZED' || props.row.invoice_status === 'Bezahlt')" icon="download" flat dense @click="$emit('download', props.row)" />
                    <q-btn v-if="props.row.row_type === 'INVOICE' && (props.row.invoice_status === 'FINALIZED' || props.row.invoice_status === 'Bezahlt')" icon="send" flat dense @click="$emit('send', props.row)" />
                    <span v-if="props.row.row_type === 'EXPENSE'" class="text-xs text-slate-400">-</span>
                </div>
            </q-td>
        ''')
        table.on('edit', on_edit)
        table.on('download', on_download)
        table.on('send', on_send)

def render_customers(session, comp):
    ui.label('Kunden').classes(C_PAGE_TITLE)
    with ui.row().classes('gap-3 mb-4'):
        ui.button('Neu', icon='add', on_click=lambda: (app.storage.user.__setitem__('page', 'customer_new'), ui.navigate.to('/'))).classes(C_BTN_PRIM)
    customers = session.exec(select(Customer)).all()
    with ui.grid(columns=3).classes('w-full gap-4'):
        for c in customers:
            with ui.card().classes(C_CARD + " p-4"):
                ui.label(c.display_name).classes('font-bold')

def render_customer_new(session, comp):
    ui.label('Neuer Kunde').classes(C_PAGE_TITLE)
    with ui.card().classes(C_CARD + " p-6 w-full max-w-2xl"):
        name = ui.input('Firma').classes(C_INPUT)
        first = ui.input('Vorname').classes(C_INPUT); last = ui.input('Nachname').classes(C_INPUT)
        street = ui.input('Straße').classes(C_INPUT); plz = ui.input('PLZ').classes(C_INPUT); city = ui.input('Ort').classes(C_INPUT)
        email = ui.input('Email').classes(C_INPUT)
        def save():
            with Session(engine) as s:
                c = Customer(company_id=comp.id, kdnr=0, name=name.value, vorname=first.value, nachname=last.value, email=email.value, strasse=street.value, plz=plz.value, ort=city.value)
                s.add(c); s.commit()
            ui.navigate.to('/')
        ui.button('Speichern', on_click=save).classes(C_BTN_PRIM)

def render_settings(session, comp):
    ui.label('Einstellungen').classes(C_PAGE_TITLE + " mb-6")
    with ui.card().classes(C_CARD + " p-6 w-full mb-4"):
        ui.label('Logo').classes(C_SECTION_TITLE)
        def on_up(e):
            with open('./storage/logo.png', 'wb') as f: f.write(e.content.read())
            ui.notify('Hochgeladen', color='green')
        ui.upload(on_upload=on_up, auto_upload=True, label="Bild wählen").props('flat dense').classes('w-full')

    with ui.card().classes(C_CARD + " p-6 w-full"):
        name = ui.input('Firma', value=comp.name).classes(C_INPUT)
        first_name = ui.input('Vorname', value=comp.first_name).classes(C_INPUT)
        last_name = ui.input('Nachname', value=comp.last_name).classes(C_INPUT)
        street = ui.input('Straße', value=comp.street).classes(C_INPUT)
        plz = ui.input('PLZ', value=comp.postal_code).classes(C_INPUT)
        city = ui.input('Ort', value=comp.city).classes(C_INPUT)
        email = ui.input('Email', value=comp.email).classes(C_INPUT)
        phone = ui.input('Telefon', value=comp.phone).classes(C_INPUT)
        iban = ui.input('IBAN', value=comp.iban).classes(C_INPUT)
        tax = ui.input('Steuernummer', value=comp.tax_id).classes(C_INPUT)
        vat = ui.input('USt-ID', value=comp.vat_id).classes(C_INPUT)
        
        def save():
            with Session(engine) as s:
                c = s.get(Company, comp.id)
                c.name = name.value; c.first_name = first_name.value; c.last_name = last_name.value
                c.street = street.value; c.postal_code = plz.value; c.city = city.value
                c.email = email.value; c.phone = phone.value; c.iban = iban.value; c.tax_id = tax.value; c.vat_id = vat.value
                s.add(c); s.commit()
            ui.notify('Gespeichert')
        ui.button('Speichern', on_click=save).classes(C_BTN_PRIM)

def render_expenses(session, comp):
    ui.label('Ausgaben').classes(C_PAGE_TITLE)
    # Placeholder implementation
    with ui.row().classes('gap-2'):
        ui.button('Neu', icon='add').classes(C_BTN_PRIM)
