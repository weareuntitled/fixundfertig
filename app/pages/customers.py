from __future__ import annotations
from ._shared import *

# Auto generated page renderer

def render_customers(session, comp: Company) -> None:
    ui.label("Kunden").classes(C_PAGE_TITLE)

    with ui.row().classes("gap-3 mb-4"):
        ui.button("Neu", icon="add", on_click=lambda: (app.storage.user.__setitem__("page", "customer_new"), ui.navigate.to("/"))).classes(C_BTN_PRIM)

    customers = session.exec(select(Customer).where(Customer.archived == False)).all()
    with ui.grid(columns=3).classes("w-full gap-4"):
        for c in customers:
            def open_detail(customer_id: int = int(c.id)):
                app.storage.user["customer_detail_id"] = customer_id
                app.storage.user["page"] = "customer_detail"
                ui.navigate.to("/")

            with ui.card().classes(C_CARD + " p-4 cursor-pointer " + C_CARD_HOVER).on("click", lambda _, x=int(c.id): open_detail(x)):
                ui.label(c.display_name).classes("font-bold")
                if c.email:
                    ui.label(c.email).classes("text-xs text-slate-500")
