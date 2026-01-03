from __future__ import annotations
from ._shared import *

# Auto generated page renderer

def render_customer_new(session, comp: Company) -> None:
    ui.label("Neuer Kunde").classes(C_PAGE_TITLE)

    with ui.card().classes(C_CARD + " p-6 w-full max-w-2xl"):
        name = ui.input("Firma").classes(C_INPUT)
        first = ui.input("Vorname").classes(C_INPUT)
        last = ui.input("Nachname").classes(C_INPUT)
        street = ui.input("Straße").classes(C_INPUT)
        plz = ui.input("PLZ").classes(C_INPUT)
        city = ui.input("Ort").classes(C_INPUT)
        email = ui.input("Email").classes(C_INPUT)

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
                )
                s.add(c)
                s.commit()
            app.storage.user["page"] = "customers"
            ui.navigate.to("/")

        ui.button("Speichern", on_click=save).classes(C_BTN_PRIM)
