from __future__ import annotations
from ._shared import *
from styles import STYLE_TEXT_MUTED
from ui_components import ff_btn_primary, ff_card

# Auto generated page renderer

def render_customers(session, comp: Company) -> None:
    with ui.row().classes("w-full items-center justify-between mb-4 flex-col sm:flex-row gap-3"):
        ui.label("Kunden").classes(C_PAGE_TITLE)
        ff_btn_primary(
            "Neu",
            icon="add",
            on_click=lambda: (app.storage.user.__setitem__("page", "customer_new"), ui.navigate.to("/")),
        )

    customers = session.exec(
        select(Customer)
        .where(Customer.archived == False, Customer.company_id == comp.id)
        .order_by(Customer.name)
    ).all()
    with ff_card(pad="p-0", classes="overflow-hidden"):
        with ui.row().classes(C_TABLE_HEADER):
            ui.label("Name").classes("flex-1")
            ui.label("Email").classes("w-64")
            ui.label("Details").classes("w-64")

        if not customers:
            with ui.row().classes(C_TABLE_ROW):
                ui.label("Noch keine Kunden vorhanden").classes(STYLE_TEXT_MUTED)
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

                with ui.row().classes(C_TABLE_ROW + " cursor-pointer hover:bg-slate-50").on(
                    "click", lambda _, x=int(c.id): open_detail(x)
                ):
                    ui.label(c.display_name).classes("flex-1 font-medium text-slate-900")
                    ui.label(c.email or "-").classes("w-64 text-slate-600")
                    ui.label(" · ".join(details) if details else "-").classes("w-64 text-slate-600")
