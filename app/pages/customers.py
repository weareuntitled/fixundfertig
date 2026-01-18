from __future__ import annotations
from ._shared import *

# Auto generated page renderer

def render_customers(session, comp: Company) -> None:
    ui.label("Kunden").classes(C_PAGE_TITLE)

    with ui.row().classes("gap-3 mb-4"):
        ui.button("Neu", icon="add", on_click=lambda: (app.storage.user.__setitem__("page", "customer_new"), ui.navigate.to("/"))).classes(C_BTN_PRIM)

    customers = session.exec(
        select(Customer)
        .where(Customer.archived == False, Customer.company_id == comp.id)
        .order_by(Customer.name)
    ).all()
    with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
        with ui.row().classes(C_TABLE_HEADER):
            ui.label("Name").classes("flex-1 font-bold text-xs text-slate-500")
            ui.label("Email").classes("w-64 font-bold text-xs text-slate-500")
            ui.label("Details").classes("w-64 font-bold text-xs text-slate-500")

        if not customers:
            with ui.row().classes(C_TABLE_ROW):
                ui.label("Noch keine Kunden vorhanden").classes("text-sm text-slate-500")
        else:
            for c in customers:
                def open_detail(customer_id: int = int(c.id)):
                    app.storage.user["customer_detail_id"] = customer_id
                    app.storage.user["page"] = "customer_detail"
                    ui.navigate.to("/")

                details: list[str] = []
                if c.vorname or c.nachname:
                    details.append(f"{c.vorname} {c.nachname}".strip())
                if c.ort or c.plz:
                    details.append(" ".join([part for part in [c.plz, c.ort] if part]))
                if c.short_code:
                    details.append(f"Kürzel: {c.short_code}")

                with ui.row().classes(C_TABLE_ROW + " cursor-pointer").on("click", lambda _, x=int(c.id): open_detail(x)):
                    ui.label(c.display_name).classes("flex-1 text-sm text-slate-900")
                    ui.label(c.email or "-").classes("w-64 text-sm text-slate-600")
                    ui.label(" · ".join(details) if details else "-").classes("w-64 text-sm text-slate-600")
