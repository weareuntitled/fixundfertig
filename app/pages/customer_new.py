from __future__ import annotations
from ._shared import *

# Auto generated page renderer

def render_customer_new(session, comp: Company) -> None:
    ui.label("Neuer Kunde").classes(C_PAGE_TITLE)

    with settings_card(classes="max-w-2xl"):
        with settings_grid():
            name = ui.input("Firma").classes(C_INPUT)
            first = ui.input("Vorname").classes(C_INPUT)
            last = ui.input("Nachname").classes(C_INPUT)
            with ui.element("div").classes("relative w-full"):
                street = ui.input("Straße").classes(C_INPUT)
                street_dropdown = ui.element("div").classes(
                    "absolute left-0 right-0 mt-1 z-10 bg-white border border-slate-200 rounded-lg shadow-sm"
                )
            plz = ui.input("PLZ").classes(C_INPUT)
            city = ui.input("Ort").classes(C_INPUT)
            country = ui.input("Land", value=comp.country or "DE").classes(C_INPUT)
            email = ui.input("Email").classes(C_INPUT)

        use_address_autocomplete(
            street,
            plz,
            city,
            country,
            street_dropdown,
        )

        use_address_autocomplete(
            street,
            plz,
            city,
            country,
            street_dropdown,
        )

        def save():
            with get_session() as s:
                c = Customer(
                    company_id=int(comp.id),
                    kdnr=0,
                    name=name.value or "",
                    vorname=first.value or "",
                    nachname=last.value or "",
                    email=email.value or "",
                    strasse=street.value or "",
                    plz=plz.value or "",
                    ort=city.value or "",
                    country=country.value or "",
                )
                s.add(c)
                s.commit()
            app.storage.user["page"] = "customers"
            ui.navigate.to("/")

        ui.button("Speichern", on_click=save).classes(C_BTN_PRIM)
