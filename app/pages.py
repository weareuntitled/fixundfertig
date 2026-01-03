from nicegui import ui, app, events
from sqlmodel import Session, select
from sqlalchemy import literal, case, union_all, func
from datetime import datetime, timedelta
import os
import base64
import json
import time
from urllib.parse import urlencode

# Imports
from data import (
    Company, Customer, Invoice, InvoiceItem, InvoiceItemTemplate, Expense, 
    process_customer_import, process_expense_import, 
    log_audit_action, InvoiceStatus, get_session
)
from renderer import render_invoice_to_pdf_bytes
from actions import cancel_invoice, create_correction, delete_draft, update_status_logic
from styles import C_CARD, C_CARD_HOVER, C_BTN_PRIM, C_BTN_SEC, C_INPUT, C_PAGE_TITLE, C_SECTION_TITLE, C_TABLE_HEADER, C_TABLE_ROW, C_BADGE_GREEN
from ui_components import format_invoice_status, invoice_status_badge, kpi_card, sticky_header
from logic import finalize_invoice_logic, export_invoices_pdf_zip, export_invoices_csv, export_invoice_items_csv, export_customers_csv, export_database_backup

# Helper
def log_invoice_action(action, invoice_id):
    with get_session() as s:
        log_audit_action(s, action, invoice_id=invoice_id)
        s.commit()

def download_invoice_file(invoice):
    if invoice and invoice.id: log_invoice_action("EXPORT_CREATED", invoice.id)
    pdf_path = invoice.pdf_filename
    if not pdf_path:
        pdf_bytes = render_invoice_to_pdf_bytes(invoice)
        if isinstance(pdf_bytes, bytearray): pdf_bytes = bytes(pdf_bytes)
        if not isinstance(pdf_bytes, bytes): raise TypeError("PDF output must be bytes")
        filename = f"rechnung_{invoice.nr}.pdf" if invoice.nr else "rechnung.pdf"
        pdf_path = f"storage/invoices/{filename}"
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        invoice.pdf_filename = filename
        invoice.pdf_storage = "local"
        with get_session() as s:
            inv = s.get(Invoice, invoice.id)
            if inv:
                inv.pdf_filename = filename
                inv.pdf_storage = "local"
                s.add(inv)
                s.commit()
        ui.download(pdf_path)
        return
    if not os.path.isabs(pdf_path) and not pdf_path.startswith("storage/"):
        pdf_path = f"storage/invoices/{pdf_path}"
    if os.path.exists(pdf_path): ui.download(pdf_path)
    else:
        pdf_bytes = render_invoice_to_pdf_bytes(invoice)
        if isinstance(pdf_bytes, bytearray): pdf_bytes = bytes(pdf_bytes)
        if not isinstance(pdf_bytes, bytes): raise TypeError("PDF output must be bytes")
        filename = os.path.basename(invoice.pdf_filename) if invoice.pdf_filename else f"rechnung_{invoice.nr}.pdf" if invoice.nr else "rechnung.pdf"
        pdf_path = f"storage/invoices/{filename}"
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        invoice.pdf_filename = filename
        invoice.pdf_storage = "local"
        with get_session() as s:
            inv = s.get(Invoice, invoice.id)
            if inv:
                inv.pdf_filename = filename
                inv.pdf_storage = "local"
                s.add(inv)
                s.commit()
        ui.download(pdf_path)

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
    
    umsatz = sum(i.total_brutto for i in invs if i.status in (InvoiceStatus.PAID, InvoiceStatus.FINALIZED))
    kosten = sum(e.amount for e in exps)
    offen = sum(i.total_brutto for i in invs if i.status in (InvoiceStatus.OPEN, InvoiceStatus.SENT, InvoiceStatus.FINALIZED))
    
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

    blocked_statuses = {InvoiceStatus.FINALIZED, "OPEN", "SENT", "PAID", "Bezahlt"}
    if draft and draft.status in blocked_statuses:
        def create_revision_and_edit(reason):
            with get_session() as inner:
                original = inner.get(Invoice, draft.id)
                if not original: return None
                new_inv = Invoice(
                    customer_id=original.customer_id,
                    nr=None,
                    title=original.title,
                    date=original.date,
                    delivery_date=original.delivery_date,
                    recipient_name=original.recipient_name,
                    recipient_street=original.recipient_street,
                    recipient_postal_code=original.recipient_postal_code,
                    recipient_city=original.recipient_city,
                    total_brutto=original.total_brutto,
                    status=InvoiceStatus.DRAFT
                )
                inner.add(new_inv)
                inner.commit()
                inner.refresh(new_inv)
                items = inner.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == original.id)).all()
                for item in items:
                    inner.add(InvoiceItem(
                        invoice_id=new_inv.id,
                        description=item.description,
                        quantity=item.quantity,
                        unit_price=item.unit_price
                    ))
                log_audit_action(inner, f"RISK_EDIT: {reason}", invoice_id=original.id)
                inner.commit()
                return new_inv.id

        sticky_header('Rechnungs-Editor', on_cancel=lambda: ui.navigate.to('/'))

        with ui.column().classes('w-full h-[calc(100vh-64px)] p-0 m-0'):
            with ui.column().classes('w-full p-4 gap-4'):
                with ui.card().classes(C_CARD + " p-4 w-full"):
                    ui.label('Ändern auf Risiko').classes(C_SECTION_TITLE)
                    ui.label('Diese Rechnung ist nicht mehr direkt editierbar.').classes('text-sm text-slate-600')

                    with ui.dialog() as risk_dialog:
                        with ui.card().classes(C_CARD + " p-4 w-full"):
                            ui.label('Ändern auf Risiko').classes(C_SECTION_TITLE)
                            reason_input = ui.textarea('Grund', placeholder='Grund der Änderung').classes(C_INPUT)
                            risk_checkbox = ui.checkbox('Ich verstehe das Risiko und möchte eine Revision erstellen.')
                            with ui.row().classes('justify-end w-full'):
                                action_button = ui.button('Revision erstellen und ändern', on_click=lambda: on_risk_confirm()).classes(C_BTN_PRIM)
                                action_button.disable()

                            def validate_risk():
                                if risk_checkbox.value and reason_input.value:
                                    action_button.enable()
                                else:
                                    action_button.disable()

                            reason_input.on('update:model-value', lambda e: validate_risk())
                            risk_checkbox.on('update:model-value', lambda e: validate_risk())

                    def on_risk_confirm():
                        if not risk_checkbox.value or not reason_input.value: return
                        new_id = create_revision_and_edit(reason_input.value)
                        if not new_id:
                            ui.notify('Revision konnte nicht erstellt werden', color='red')
                            return
                        app.storage.user['invoice_draft_id'] = new_id
                        app.storage.user['page'] = 'invoice_create'
                        risk_dialog.close()
                        ui.navigate.to('/')

                    ui.button('Ändern auf Risiko', on_click=lambda: risk_dialog.open()).classes(C_BTN_PRIM)
        return
    
    # Iframe Preview
    preview_html = None

    autosave_state = {'dirty': False, 'last_change': 0.0, 'saving': False}
    preview_state = {'pending': False, 'last_change': 0.0}

    def mark_dirty():
        autosave_state['dirty'] = True
        autosave_state['last_change'] = time.monotonic()

    def request_preview_update():
        preview_state['pending'] = True
        preview_state['last_change'] = time.monotonic()

    def update_preview():
        cust_id = state['customer_id']
        rec_n, rec_s, rec_z, rec_c = "", "", "", ""
        if cust_id:
            with get_session() as s:
                c = s.get(Customer, int(cust_id))
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
            if isinstance(pdf, bytearray): pdf = bytes(pdf)
            if not isinstance(pdf, bytes): raise TypeError("PDF output must be bytes")
            b64 = base64.b64encode(pdf).decode('utf-8')
            # Iframe 100% height fix
            if preview_html:
                preview_html.content = f'<iframe src="data:application/pdf;base64,{b64}" style="width:100%; height:100%; border:none;"></iframe>'
        except Exception as e: print(e)

    def debounce_preview():
        if preview_state['pending'] and time.monotonic() - preview_state['last_change'] >= 0.3:
            preview_state['pending'] = False
            update_preview()

    def on_finalize():
        if not state['customer_id']: return ui.notify('Kunde fehlt', color='red')
        with get_session() as inner:
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

    def save_draft():
        nonlocal draft_id
        with get_session() as inner:
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
            action = "INVOICE_UPDATED_DRAFT" if draft_id else "INVOICE_CREATED_DRAFT"
            log_audit_action(inner, action, invoice_id=inv.id)
            inner.commit()
            if not draft_id:
                draft_id = inv.id
                app.storage.user['invoice_draft_id'] = inv.id
        return draft_id

    def on_save_draft():
        save_draft()
        ui.notify('Gespeichert', color='green')
        ui.navigate.to('/')

    def on_autosave():
        save_draft()

    def autosave_tick():
        if autosave_state['dirty'] and not autosave_state['saving']:
            if time.monotonic() - autosave_state['last_change'] >= 3.0:
                autosave_state['saving'] = True
                on_autosave()
                autosave_state['dirty'] = False
                autosave_state['saving'] = False

    ui.timer(0.1, debounce_preview)
    ui.timer(3.0, autosave_tick)

    sticky_header('Rechnungs-Editor', on_cancel=lambda: ui.navigate.to('/'), on_save=on_save_draft, on_finalize=on_finalize)

    with ui.column().classes('w-full h-[calc(100vh-64px)] p-0 m-0'):
        with ui.grid().classes('w-full flex-grow grid-cols-1 md:grid-cols-2'):
            # LINKS
            with ui.column().classes('w-full p-4 gap-4 h-full overflow-y-auto'):
                with ui.card().classes(C_CARD + " p-4 w-full"):
                    ui.label('Kopfdaten').classes(C_SECTION_TITLE)
                    cust_select = ui.select(cust_opts, label='Kunde', value=state['customer_id'], with_input=True).classes(C_INPUT)
                    def on_cust(e):
                        state['customer_id'] = e.value
                        mark_dirty()
                        if e.value:
                            with get_session() as s:
                                c = s.get(Customer, int(e.value))
                                if c: rec_name.value = c.display_name; rec_street.value = c.strasse; rec_zip.value = c.plz; rec_city.value = c.ort
                        request_preview_update()
                    cust_select.on('update:model-value', on_cust)
                    
                    with ui.grid(columns=2).classes('w-full gap-2'):
                         ui.input('Titel', value=state['title'], on_change=lambda e: (state.update({'title': e.value}), mark_dirty(), request_preview_update())).classes(C_INPUT)
                         ui.input('Rechnung', value=state['date'], on_change=lambda e: (state.update({'date': e.value}), mark_dirty(), request_preview_update())).classes(C_INPUT)
                         ui.input('Lieferung', value=state['delivery_date'], on_change=lambda e: (state.update({'delivery_date': e.value}), mark_dirty(), request_preview_update())).classes(C_INPUT)

                with ui.expansion('Anschrift anpassen').classes('w-full border border-slate-200 rounded bg-white text-sm'):
                    with ui.column().classes('p-3 gap-2 w-full'):
                        rec_name = ui.input('Name', on_change=request_preview_update).classes(C_INPUT+" dense")
                        rec_street = ui.input('Straße', on_change=request_preview_update).classes(C_INPUT+" dense")
                        with ui.row().classes('w-full gap-2'):
                            rec_zip = ui.input('PLZ', on_change=request_preview_update).classes(C_INPUT+" w-20 dense")
                            rec_city = ui.input('Ort', on_change=request_preview_update).classes(C_INPUT+" flex-1 dense")

                with ui.card().classes(C_CARD + " p-4 w-full"):
                    with ui.row().classes('justify-between w-full'):
                        ui.label('Posten').classes(C_SECTION_TITLE)
                        ust_switch = ui.switch('19% MwSt', value=state['ust'], on_change=lambda e: (state.update({'ust': e.value}), mark_dirty(), request_preview_update())).props('dense color=grey-8')
                    
                    if template_items:
                        item_template_select = ui.select({str(t.id): t.title for t in template_items}, label='Vorlage', with_input=True).classes(C_INPUT + " mb-2 dense")

                    items_col = ui.column().classes('w-full gap-2')
                    def render_list():
                        items_col.clear()
                        with items_col:
                            for item in state['items']:
                                with ui.row().classes('w-full gap-1 items-start bg-slate-50 p-2 rounded border'):
                                    ui.textarea(value=item['desc'], on_change=lambda e, i=item: (i.update({'desc': e.value}), mark_dirty(), request_preview_update())).classes('flex-1 dense text-sm').props('rows=1 placeholder="Text" auto-grow')
                                    with ui.column().classes('gap-1'):
                                        ui.number(value=item['qty'], on_change=lambda e, i=item: (i.update({'qty': float(e.value or 0)}), mark_dirty(), request_preview_update())).classes('w-16 dense')
                                        ui.number(value=item['price'], on_change=lambda e, i=item: (i.update({'price': float(e.value or 0)}), mark_dirty(), request_preview_update())).classes('w-20 dense')
                                    ui.button(icon='close', on_click=lambda i=item: (state['items'].remove(i), mark_dirty(), render_list(), request_preview_update())).classes('flat dense text-red')
                    render_list()
                    
                    def add_new(): state['items'].append({'desc':'', 'qty':1.0, 'price':0.0, 'is_brutto':False}); mark_dirty(); render_list(); request_preview_update()
                    def add_tmpl():
                         if not item_template_select.value: return
                         t = next((x for x in template_items if str(x.id)==item_template_select.value),None)
                         if t: state['items'].append({'desc':t.description,'qty':t.quantity,'price':t.unit_price,'is_brutto':False}); mark_dirty(); render_list(); request_preview_update(); item_template_select.value=None

                    with ui.row().classes('gap-2 mt-2'):
                        ui.button('Posten', icon='add', on_click=add_new).props('flat dense').classes('text-slate-600')
                        if template_items: ui.button('Vorlage', icon='playlist_add', on_click=add_tmpl).props('flat dense').classes('text-slate-600')

            # RECHTS
            with ui.column().classes('w-full h-full min-h-[70vh] bg-slate-200 p-0 m-0 overflow-hidden'):
                preview_html = ui.html('', sanitize=False).classes('w-full h-full min-h-[70vh] bg-slate-300')
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
                    if i.status != InvoiceStatus.CANCELLED:
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
                                         def on_download(x=i):
                                             ui.notify('Wird vorbereitet…')
                                             set_loading(True)
                                             try:
                                                 download_invoice_file(x)
                                             except Exception as e:
                                                 ui.notify(f"Fehler: {e}", color='red')
                                             set_loading(False)

                                         def on_send(x=i):
                                             ui.notify('Wird vorbereitet…')
                                             set_loading(True)
                                             try:
                                                 with get_session() as s:
                                                     c = s.get(Customer, x.customer_id) if x.customer_id else None
                                                 send_invoice_email(comp, c, x)
                                             except Exception as e:
                                                 ui.notify(f"Fehler: {e}", color='red')
                                             set_loading(False)

                                         def on_status_change(target_status, x=i):
                                             ui.notify('Wird vorbereitet…')
                                             set_loading(True)
                                             try:
                                                 with get_session() as s:
                                                     with s.begin():
                                                         _, err = update_status_logic(s, x.id, target_status)
                                                 if err:
                                                     ui.notify(err, color='red')
                                                 else:
                                                     ui.notify('Status aktualisiert', color='green')
                                             except Exception as e:
                                                 ui.notify(f"Fehler: {e}", color='red')
                                             set_loading(False)
                                             ui.navigate.to('/')

                                         def on_cancel(x=i):
                                             ui.notify('Wird vorbereitet…')
                                             set_loading(True)
                                             try:
                                                 ok, err = cancel_invoice(x.id)
                                                 if not ok:
                                                     ui.notify(err, color='red')
                                                 else:
                                                     ui.notify('Storniert', color='green')
                                             except Exception as e:
                                                 ui.notify(f"Fehler: {e}", color='red')
                                             set_loading(False)
                                             ui.navigate.to('/')

                                         def on_delete(x=i):
                                             ui.notify('Wird vorbereitet…')
                                             set_loading(True)
                                             try:
                                                 ok, err = delete_draft(x.id)
                                                 if not ok:
                                                     ui.notify(err, color='red')
                                                 else:
                                                     ui.notify('Gelöscht', color='green')
                                             except Exception as e:
                                                 ui.notify(f"Fehler: {e}", color='red')
                                             set_loading(False)
                                             ui.navigate.to('/')

                                         if i.status in (InvoiceStatus.OPEN, InvoiceStatus.SENT, InvoiceStatus.PAID, InvoiceStatus.FINALIZED):
                                             ui.menu_item('Download', on_click=on_download)
                                             ui.menu_item('Senden', on_click=on_send)
                                         if i.status in (InvoiceStatus.OPEN, InvoiceStatus.FINALIZED):
                                             ui.menu_item('Als gesendet markieren', on_click=lambda x=i: on_status_change(InvoiceStatus.SENT, x))
                                         if i.status == InvoiceStatus.SENT:
                                             ui.menu_item('Als bezahlt markieren', on_click=lambda x=i: on_status_change(InvoiceStatus.PAID, x))
                                         if i.status == InvoiceStatus.DRAFT:
                                             ui.menu_item('Entwurf löschen', on_click=on_delete)
                                         elif i.status != InvoiceStatus.CANCELLED:
                                             ui.menu_item('Stornieren', on_click=on_cancel)

def render_ledger(session, comp):
    ui.label('Finanzen').classes(C_PAGE_TITLE + " mb-4")

    def parse_date(value):
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return datetime.min

    customer_name = func.coalesce(
        func.nullif(Customer.name, ''),
        func.trim(func.coalesce(Customer.vorname, '') + literal(' ') + func.coalesce(Customer.nachname, ''))
    )

    invoice_query = select(
        Invoice.id.label('id'),
        Invoice.date.label('date'),
        Invoice.total_brutto.label('amount'),
        literal('INCOME').label('type'),
        case(
            (Invoice.status == InvoiceStatus.DRAFT, 'Draft'),
            (Invoice.status == InvoiceStatus.OPEN, 'Open'),
            (Invoice.status == InvoiceStatus.SENT, 'Sent'),
            (Invoice.status == InvoiceStatus.PAID, 'Paid'),
            (Invoice.status == InvoiceStatus.FINALIZED, 'Open'),
            (Invoice.status == InvoiceStatus.CANCELLED, 'Cancelled'),
            else_='Overdue',
        ).label('status'),
        func.coalesce(customer_name, literal('?')).label('party'),
        Invoice.title.label('description'),
        Invoice.status.label('invoice_status'),
        Invoice.id.label('invoice_id'),
        literal(None).label('expense_id'),
    ).select_from(Invoice).outerjoin(Customer, Invoice.customer_id == Customer.id)

    expense_query = select(
        Expense.id.label('id'),
        Expense.date.label('date'),
        Expense.amount.label('amount'),
        literal('EXPENSE').label('type'),
        literal('Paid').label('status'),
        func.coalesce(Expense.source, Expense.category, Expense.description, literal('-')).label('party'),
        Expense.description.label('description'),
        literal(None).label('invoice_status'),
        literal(None).label('invoice_id'),
        Expense.id.label('expense_id'),
    )

    rows = session.exec(union_all(invoice_query, expense_query)).all()
    items = []
    for row in rows:
        data = row._mapping if hasattr(row, '_mapping') else row
        items.append({
            'id': data['id'],
            'date': data['date'],
            'amount': data['amount'],
            'type': data['type'],
            'status': data['status'],
            'party': data['party'],
            'description': data['description'] or '',
            'invoice_status': data['invoice_status'],
            'invoice_id': data['invoice_id'],
            'expense_id': data['expense_id'],
            'sort_date': parse_date(data['date']),
        })
    items.sort(key=lambda x: x['sort_date'], reverse=True)

    state = {
        'type': 'ALL',
        'status': 'ALL',
        'date_from': '',
        'date_to': '',
        'search': '',
    }

    def apply_filters(data):
        filtered = []
        for item in data:
            if state['type'] != 'ALL' and item['type'] != state['type']: continue
            if state['status'] != 'ALL' and item['status'] != state['status']: continue
            if state['date_from']:
                if item['sort_date'] < parse_date(state['date_from']): continue
            if state['date_to']:
                if item['sort_date'] > parse_date(state['date_to']): continue
            if state['search']:
                haystack = f"{item['party']} {item.get('description','')}".lower()
                if state['search'].lower() not in haystack: continue
            filtered.append(item)
        return filtered

    def set_type(e):
        state['type'] = e.value or 'ALL'
        render_list.refresh()

    def set_status(e):
        state['status'] = e.value or 'ALL'
        render_list.refresh()

    def set_date_from(e):
        state['date_from'] = e.value or ''
        render_list.refresh()

    def set_date_to(e):
        state['date_to'] = e.value or ''
        render_list.refresh()

    def set_search(e):
        state['search'] = e.value or ''
        render_list.refresh()

    with ui.card().classes(C_CARD + " p-4 mb-4 sticky top-0 z-30"):
        with ui.row().classes('gap-4 w-full items-end flex-wrap'):
            ui.select({'ALL': 'Alle', 'INCOME': 'Income', 'EXPENSE': 'Expense'}, label='Typ', value=state['type'], on_change=set_type).classes(C_INPUT)
            ui.select({'ALL': 'Alle', 'Draft': 'Draft', 'Open': 'Open', 'Sent': 'Sent', 'Paid': 'Paid', 'Cancelled': 'Cancelled'}, label='Status', value=state['status'], on_change=set_status).classes(C_INPUT)
            ui.input('Von', on_change=set_date_from).props('type=date').classes(C_INPUT)
            ui.input('Bis', on_change=set_date_to).props('type=date').classes(C_INPUT)
            ui.input('Suche', placeholder='Party oder Beschreibung', on_change=set_search).classes(C_INPUT + " min-w-[220px]")

    @ui.refreshable
    def render_list():
        data = apply_filters(items)
        if len(data) == 0:
            with ui.card().classes(C_CARD + " p-4"):
                with ui.row().classes('w-full justify-center'):
                    ui.label('Keine Ergebnisse gefunden').classes('text-sm text-slate-500')
            return
        with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
            with ui.element('div').classes(C_TABLE_HEADER + " hidden sm:grid sm:grid-cols-[110px_110px_110px_1fr_120px_120px] items-center"):
                ui.label('Datum').classes('font-bold')
                ui.label('Typ').classes('font-bold')
                ui.label('Status').classes('font-bold')
                ui.label('Kunde/Lieferant').classes('font-bold')
                ui.label('Betrag').classes('font-bold text-right')
                ui.label('').classes('font-bold text-right')
            for item in data:
                with ui.element('div').classes(C_TABLE_ROW + " group grid grid-cols-1 sm:grid-cols-[110px_110px_110px_1fr_120px_120px] gap-2 sm:gap-0 items-start sm:items-center"):
                    with ui.column().classes('gap-1'):
                        ui.label('Datum').classes('sm:hidden text-[10px] uppercase text-slate-400')
                        ui.label(item['date']).classes('text-xs font-mono')
                    with ui.column().classes('gap-1'):
                        ui.label('Typ').classes('sm:hidden text-[10px] uppercase text-slate-400')
                        badge_class = C_BADGE_GREEN if item['type'] == 'INCOME' else "bg-rose-50 text-rose-700 border border-rose-100 px-2 py-0.5 rounded-full text-xs font-medium text-center"
                        badge_label = "Income" if item['type'] == 'INCOME' else "Expense"
                        ui.label(badge_label).classes(badge_class + " w-20")
                    with ui.column().classes('gap-1'):
                        ui.label('Status').classes('sm:hidden text-[10px] uppercase text-slate-400')
                        ui.label(item['status']).classes('text-xs')
                    with ui.column().classes('gap-1'):
                        ui.label('Kunde/Lieferant').classes('sm:hidden text-[10px] uppercase text-slate-400')
                        ui.label(item['party']).classes('text-sm')
                        if item.get('description'):
                            ui.label(item['description']).classes('text-xs text-slate-500')
                    with ui.column().classes('gap-1 sm:items-end'):
                        ui.label('Betrag').classes('sm:hidden text-[10px] uppercase text-slate-400')
                        amount_label = f"{item['amount']:,.2f} €" if item['type'] == 'INCOME' else f"-{item['amount']:,.2f} €"
                        amount_class = 'text-right text-sm text-emerald-600' if item['type'] == 'INCOME' else 'text-right text-sm text-rose-600'
                        ui.label(amount_label).classes(amount_class)
                    with ui.row().classes('justify-end gap-1 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition'):
                        if item['invoice_id']:
                            i = session.get(Invoice, item['invoice_id'])
                            if i and i.status == InvoiceStatus.DRAFT:
                                def edit(x=i):
                                    app.storage.user['invoice_draft_id'] = x.id
                                    app.storage.user['page'] = 'invoice_create'
                                    ui.navigate.to('/')
                                ui.button(icon='edit', on_click=lambda x=i: edit(x)).props('flat dense').classes('text-slate-500')
                            if i and i.status in (InvoiceStatus.OPEN, InvoiceStatus.SENT, InvoiceStatus.PAID, InvoiceStatus.FINALIZED):
                                f = f"storage/invoices/{i.pdf_filename or f'rechnung_{i.nr}.pdf'}"
                                ui.button(icon='download', on_click=lambda p=i: download_invoice_file(p)).props('flat dense').classes('text-slate-500')
                                ui.button(icon='mail', on_click=lambda x=i: send_invoice_email(comp, session.get(Customer, x.customer_id) if x.customer_id else None, x)).props('flat dense').classes('text-slate-500')
                        else:
                            ui.label('-').classes('text-xs text-slate-400')

    render_list()

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
            with get_session() as s:
                c = Customer(company_id=comp.id, kdnr=0, name=name.value, vorname=first.value, nachname=last.value, email=email.value, strasse=street.value, plz=plz.value, ort=city.value)
                s.add(c); s.commit()
            ui.navigate.to('/')
        ui.button('Speichern', on_click=save).classes(C_BTN_PRIM)

def render_exports(session, comp):
    ui.label('Exporte').classes(C_PAGE_TITLE + " mb-4")

    def run_export(action, label):
        ui.notify('Wird vorbereitet…')
        try:
            with get_session() as s:
                path = action(s)
            if path and os.path.exists(path):
                ui.download(path)
                ui.notify(f"{label} bereit", color='green')
            else:
                ui.notify('Export fehlgeschlagen', color='red')
        except Exception as e:
            ui.notify(f"Fehler: {e}", color='red')

    def export_card(title, description, action):
        with ui.card().classes(C_CARD + " p-5 " + C_CARD_HOVER + " w-full"):
            ui.label(title).classes('font-semibold text-slate-900')
            ui.label(description).classes('text-sm text-slate-500 mb-2')
            ui.button('Download', icon='download', on_click=action).classes(C_BTN_SEC)

    with ui.grid(columns=2).classes('w-full gap-4'):
        export_card('PDF ZIP', 'Alle Rechnungs-PDFs als ZIP-Datei', lambda: run_export(export_invoices_pdf_zip, 'PDF ZIP'))
        export_card('Rechnungen CSV', 'Alle Rechnungen als CSV-Datei', lambda: run_export(export_invoices_csv, 'Rechnungen CSV'))
        export_card('Positionen CSV', 'Alle Rechnungspositionen als CSV-Datei', lambda: run_export(export_invoice_items_csv, 'Positionen CSV'))
        export_card('Kunden CSV', 'Alle Kunden als CSV-Datei', lambda: run_export(export_customers_csv, 'Kunden CSV'))

    with ui.expansion('Erweitert').classes('w-full mt-4'):
        with ui.column().classes('w-full gap-2 p-2'):
            export_card('DB-Backup', 'SQLite Datenbank sichern', lambda: run_export(export_database_backup, 'DB-Backup'))

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
            with get_session() as s:
                c = s.get(Company, comp.id)
                c.name = name.value; c.first_name = first_name.value; c.last_name = last_name.value
                c.street = street.value; c.postal_code = plz.value; c.city = city.value
                c.email = email.value; c.phone = phone.value; c.iban = iban.value; c.tax_id = tax.value; c.vat_id = vat.value
                s.add(c); s.commit()
            ui.notify('Gespeichert')
        ui.button('Speichern', on_click=save).classes(C_BTN_PRIM)

def render_automations(session, comp):
    ui.label('Automationen').classes(C_PAGE_TITLE + " mb-6")

    status_state = {
        'value': 'connected' if comp.n8n_webhook_url and comp.n8n_secret else 'not_connected'
    }
    status_labels = {
        'not_connected': ('Nicht verbunden', C_BADGE_GRAY),
        'connected': ('Verbunden', C_BADGE_GREEN),
        'error': ('Fehler', 'bg-rose-50 text-rose-700 border border-rose-100 px-2 py-0.5 rounded-full text-xs font-medium text-center')
    }

    @ui.refreshable
    def render_status():
        label, classes = status_labels[status_state['value']]
        ui.label(label).classes(classes)

    with ui.card().classes(C_CARD + " p-6 w-full"):
        ui.label('n8n Verbindung').classes(C_SECTION_TITLE + " mb-4")
        with ui.row().classes('items-center gap-2 mb-6'):
            ui.label('Status').classes('text-sm text-slate-600')
            render_status()

        n8n_webhook_url = ui.input('n8n Webhook URL', value=comp.n8n_webhook_url).classes(C_INPUT)
        n8n_secret = ui.input('n8n Secret', value=comp.n8n_secret).classes(C_INPUT)
        google_drive_folder_id = ui.input('Google Drive Ordner-ID (optional)', value=comp.google_drive_folder_id).classes(C_INPUT)

        def save():
            with get_session() as s:
                c = s.get(Company, comp.id)
                c.n8n_webhook_url = n8n_webhook_url.value
                c.n8n_secret = n8n_secret.value
                c.google_drive_folder_id = google_drive_folder_id.value
                s.add(c); s.commit()
            comp.n8n_webhook_url = n8n_webhook_url.value
            comp.n8n_secret = n8n_secret.value
            comp.google_drive_folder_id = google_drive_folder_id.value
            status_state['value'] = 'connected' if comp.n8n_webhook_url and comp.n8n_secret else 'not_connected'
            render_status.refresh()
            ui.notify('Gespeichert')

        def send_test_event():
            payload = {
                'event': 'test',
                'company_id': comp.id,
                'timestamp': datetime.now().isoformat()
            }
            ok = send_n8n_event(comp, payload)
            status_state['value'] = 'connected' if ok else 'error'
            render_status.refresh()
            if ok: ui.notify('Test Event gesendet', color='green')

        with ui.row().classes('gap-3 mt-4'):
            ui.button('Speichern', on_click=save).classes(C_BTN_PRIM)
            ui.button('Test Event senden', on_click=send_test_event).classes(C_BTN_SEC)

def render_expenses(session, comp):
    ui.label('Ausgaben').classes(C_PAGE_TITLE)
    # Placeholder implementation
    with ui.row().classes('gap-2'):
        ui.button('Neu', icon='add').classes(C_BTN_PRIM)
