from nicegui import ui, app
from sqlmodel import Session, select

from data import Company, engine
from styles import C_BG, C_CONTAINER, C_HEADER, C_BRAND_BADGE, C_NAV_ITEM, C_NAV_ITEM_ACTIVE
from pages import render_dashboard, render_customers, render_invoices, render_expenses, render_settings

# --- UI LOGIC ---

def layout_wrapper(content_func):
    # HEADER
    with ui.header().classes(C_HEADER):
        with ui.row().classes('items-center gap-3'):
            with ui.element('div').classes(C_BRAND_BADGE):
                ui.icon('bolt', size='xs')
            ui.label('FixundFertig').classes('font-bold text-slate-900 tracking-tight')
        
        with ui.row().classes('gap-1'):
            def nav_item(label, target, icon):
                active = app.storage.user.get('page', 'dashboard') == target
                color = C_NAV_ITEM_ACTIVE if active else C_NAV_ITEM
                with ui.link(label, '#').on('click', lambda e: set_page(target)).classes(color):
                    with ui.row().classes('items-center gap-2'):
                        ui.label(label).classes('text-sm font-semibold normal-case')

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
            elif page == 'invoices': render_invoices(session, comp)
            elif page == 'expenses': render_expenses(session, comp)
            elif page == 'settings': render_settings(session, comp)

    layout_wrapper(content)

ui.run(title='FixundFertig Ultimate', port=8080, language='de', storage_secret='secret2026')
