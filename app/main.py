# =========================
# APP/MAIN.PY (REPLACE FULL FILE)
# =========================

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from nicegui import ui, app

from env import load_env
from auth_guard import clear_auth_session, require_auth
from data import get_session
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
from pages._shared import get_current_user_id, get_primary_company, list_companies

load_env()


def _format_nominatim_result(item: dict) -> dict:
    address = item.get("address") or {}
    road = address.get("road") or address.get("pedestrian") or address.get("path") or ""
    house_number = address.get("house_number") or ""
    street = " ".join(part for part in [road, house_number] if part).strip()
    if not street:
        street = address.get("street") or ""
    postal_code = address.get("postcode") or ""
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("county")
        or ""
    )
    country_code = (address.get("country_code") or "").upper()
    country = address.get("country") or country_code
    label = item.get("display_name") or ", ".join(
        part for part in [street, f"{postal_code} {city}".strip(), country] if part
    )
    return {
        "label": label,
        "street": street,
        "zip": postal_code,
        "city": city,
        "country": country,
    }


@app.get("/api/address-autocomplete")
def address_autocomplete(q: str = "", country: str = "DE"):
    query = (q or "").strip()
    if len(query) < 3:
        return []

    params = {
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "limit": 6,
    }
    if country:
        params["countrycodes"] = country.lower()
    url = f"https://nominatim.openstreetmap.org/search?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "User-Agent": "FixundFertig/1.0 (autocomplete)",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    if not isinstance(payload, list):
        return []
    return [_format_nominatim_result(item) for item in payload]


def set_page(name: str):
    app.storage.user["page"] = name
    ui.navigate.to("/")


def layout_wrapper(content_func):
    # App shell with left sidebar
    with ui.element("div").classes(C_BG + " w-full"):
        with ui.row().classes("w-full min-h-screen"):
            # Sidebar
            with ui.column().classes(
                "w-[260px] bg-white border-r border-slate-200 p-4 gap-6 sticky top-0 h-screen overflow-y-auto"
            ):
                with ui.row().classes("items-center gap-2 px-2"):
                    ui.label("FixundFertig").classes("text-lg font-bold text-slate-900")
                ui.separator().classes("opacity-60")

                def nav_section(title: str, items: list[tuple[str, str]]):
                    ui.label(title).classes(
                        "text-xs font-semibold text-slate-400 uppercase tracking-wider px-2 mt-1"
                    )
                    with ui.column().classes("gap-1 mt-1"):
                        for label, target in items:
                            active = app.storage.user.get("page", "invoices") == target
                            cls = C_NAV_ITEM_ACTIVE if active else C_NAV_ITEM
                            ui.button(
                                label,
                                on_click=lambda t=target: set_page(t),
                            ).props("flat").classes(f"w-full justify-start normal-case {cls}")

                nav_section("Workspace", [("Dashboard", "dashboard")])
                nav_section(
                    "Billing",
                    [
                        ("Rechnungen", "invoices"),
                        ("Finanzen", "ledger"),
                        ("Exporte", "exports"),
                    ],
                )
                nav_section("CRM", [("Kunden", "customers")])
                nav_section("Settings", [("Einstellungen", "settings")])

            # Main content
            with ui.column().classes("flex-1 w-full"):
                with ui.row().classes("w-full justify-end px-6 py-4"):

                    def handle_logout() -> None:
                        clear_auth_session()
                        ui.navigate.to("/login")

                    ui.button("Logout", on_click=handle_logout).props("flat").classes(
                        "text-slate-500 hover:text-slate-900"
                    )
                content_func()


@ui.page("/")
def index():
    if not require_auth():
        return

    app.add_static_files("/storage", "storage")

    # Ensure company exists
    with get_session() as session:
        user_id = get_current_user_id(session)
        if user_id is None:
            clear_auth_session()
            ui.navigate.to("/login")
            return
        companies = list_companies(session, user_id)
        if not companies:
            get_primary_company(session, user_id)

    page = app.storage.user.get("page", "invoices")

    def content():
        with get_session() as session:
            user_id = get_current_user_id(session)
            if user_id is None:
                clear_auth_session()
                ui.navigate.to("/login")
                return

            companies = list_companies(session, user_id)

            # ✅ ACTIVE COMPANY SELECTION (correct indentation)
            active_id = app.storage.user.get("active_company_id")
            try:
                active_id = int(active_id) if active_id is not None else None
            except Exception:
                active_id = None

            comp = None
            if active_id:
                comp = next((c for c in companies if int(c.id or 0) == active_id), None)

            if not comp:
                comp = companies[0] if companies else get_primary_company(session, user_id)

            if comp and comp.id:
                app.storage.user["active_company_id"] = int(comp.id)

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
                    render_invoices(session, comp)

    layout_wrapper(content)


ui.run(title="FixundFertig", port=8080, language="de", storage_secret="secret2026", favicon="🚀")
