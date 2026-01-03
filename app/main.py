# =========================
# APP/MAIN.PY (REPLACE FULL FILE)
# =========================

import os
from nicegui import ui, app
from sqlmodel import select

from data import Company, get_session
from styles import C_BG, C_CONTAINER, C_NAV_ITEM, C_NAV_ITEM_ACTIVE
from pages import (
    render_dashboard,
    render_customers,
    render_customer_new,
    render_customer_detail,
    render_invoices,
    render_invoice_create,
    render_invoice_detail,
    render_expenses,
    render_settings,
    render_ledger,
    render_exports,
)

def set_page(name: str):
    app.storage.user["page"] = name
    ui.navigate.to("/")

def layout_wrapper(content_func):
    # App shell with left sidebar (screenshot style)
    with ui.element("div").classes(C_BG + " w-full"):
        with ui.row().classes("w-full min-h-screen"):
            # Sidebar
            with ui.column().classes("w-[260px] bg-white border-r border-slate-200 p-4 gap-6 sticky top-0 h-screen overflow-y-auto"):
                # Brand
                with ui.row().classes("items-center gap-2 px-2"):
                    ui.label("FixundFertig").classes("text-lg font-bold text-slate-900")
                ui.separator().classes("opacity-60")

                def nav_section(title: str, items: list[tuple[str, str]]):
                    ui.label(title).classes("text-xs font-semibold text-slate-400 uppercase tracking-wider px-2 mt-1")
                    with ui.column().classes("gap-1 mt-1"):
                        for label, target in items:
                            active = app.storage.user.get("page", "invoices") == target
                            cls = C_NAV_ITEM_ACTIVE if active else C_NAV_ITEM
                            ui.button(label, on_click=lambda t=target: set_page(t)).props("flat").classes(f"w-full justify-start normal-case {cls}")

                nav_section("Workspace", [
                    ("Dashboard", "dashboard"),
                ])
                nav_section("Billing", [
                    ("Rechnungen", "invoices"),
                    ("Finanzen", "ledger"),
                    ("Exporte", "exports"),
                ])
                nav_section("CRM", [
                    ("Kunden", "customers"),
                ])
                nav_section("Settings", [
                    ("Einstellungen", "settings"),
                ])

            # Main content
            with ui.column().classes("flex-1 w-full"):
                content_func()

@ui.page("/")
def index():
    app.add_static_files("/storage", "storage")

    # Ensure company exists
    with get_session() as session:
        if not session.exec(select(Company)).first():
            session.add(Company())
            session.commit()

    page = app.storage.user.get("page", "invoices")

    def content():
        with get_session() as session:
            comp = session.exec(select(Company)).first()

            # Full-width flows (editor / detail)
            if page == "invoice_create":
                render_invoice_create(session, comp)
                return
            if page == "invoice_detail":
                render_invoice_detail(session, comp)
                return
            if page == "settings":
                render_settings(session, comp)
                return

            # Normal pages in container
            with ui.column().classes(C_CONTAINER):
                if page == "dashboard":
                    render_dashboard(session, comp)
                elif page == "customers":
                    render_customers(session, comp)
                elif page == "customer_new":
                    render_customer_new(session, comp)
                elif page == "customer_detail":
                    customer_id = app.storage.user.get("customer_detail_id")
                    render_customer_detail(session, comp, customer_id)
                elif page == "invoices":
                    render_invoices(session, comp)
                elif page == "expenses":
                    render_expenses(session, comp)
                elif page == "ledger":
                    render_ledger(session, comp)
                elif page == "exports":
                    render_exports(session, comp)
                else:
                    # fallback
                    render_invoices(session, comp)

    layout_wrapper(content)

ui.run(title="FixundFertig", port=8080, language="de", storage_secret="secret2026", favicon="🚀")
