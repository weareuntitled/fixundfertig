from __future__ import annotations
from ._shared import *

# Auto generated page renderer

def render_customer_new(session, comp: Company) -> None:
    ui.label("Neuer Kunde").classes(C_PAGE_TITLE)

    with ui.card().classes(C_CARD + " p-6 w-full max-w-2xl"):
        name = ui.input("Firma").classes(C_INPUT)
        first = ui.input("Vorname").classes(C_INPUT)
        last = ui.input("Nachname").classes(C_INPUT)
        with ui.column().classes("w-full gap-1"):
            street = ui.input("Straße").classes(C_INPUT)
            street_dropdown = ui.column().classes(
                "w-full border border-slate-200 rounded-lg bg-white shadow-lg max-h-56 overflow-auto"
            ).props("role=listbox aria-label=Adressvorschläge")
        plz = ui.input("PLZ").classes(C_INPUT)
        city = ui.input("Ort").classes(C_INPUT)
        country = ui.input("Land").classes(C_INPUT)
        email = ui.input("Email").classes(C_INPUT)

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
