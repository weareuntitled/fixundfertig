#!/bin/bash

pip install -r app/requirements.txt
python3 app/main.py

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

def render_invoices(session, comp):
    ui.label('Rechnungen').classes('text-2xl font-bold text-slate-900 mb-6')
    invs = session.exec(select(Invoice)).all()
    
    with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
        # MANUELLE TABELLEN KOPFZEILE (Kein ui.table mehr!)
        with ui.row().classes('w-full bg-slate-50 border-b border-slate-200 p-4 gap-4'):
            ui.label('Status').classes('w-24 font-medium text-slate-500 text-sm')
            ui.label('Nr').classes('w-16 font-medium text-slate-500 text-sm')
            ui.label('Datum').classes('w-24 font-medium text-slate-500 text-sm')
            ui.label('Kunde').classes('flex-1 font-medium text-slate-500 text-sm')
            ui.label('Betrag').classes('w-24 text-right font-medium text-slate-500 text-sm')

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
EOF

echo "✅ Fertig."
