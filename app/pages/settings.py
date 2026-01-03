from __future__ import annotations
from ._shared import *

# Auto generated page renderer

def render_settings(session, comp: Company) -> None:
    ui.label("Einstellungen").classes(C_PAGE_TITLE + " mb-6")

    with settings_card("Logo", classes="mb-4"):

        def on_up(e):
            os.makedirs("./storage", exist_ok=True)
            with open("./storage/logo.png", "wb") as f:
                f.write(e.content.read())
            ui.notify("Hochgeladen", color="green")

        ui.upload(on_upload=on_up, auto_upload=True, label="Bild wählen").props("flat dense").classes("w-full")

    with settings_card():
        with settings_grid():
            name = ui.input("Firma", value=comp.name).classes(C_INPUT)
            first_name = ui.input("Vorname", value=comp.first_name).classes(C_INPUT)
            last_name = ui.input("Nachname", value=comp.last_name).classes(C_INPUT)
            street = ui.input("Straße", value=comp.street).classes(C_INPUT)
            plz = ui.input("PLZ", value=comp.postal_code).classes(C_INPUT)
            city = ui.input("Ort", value=comp.city).classes(C_INPUT)
            email = ui.input("Email", value=comp.email).classes(C_INPUT)
            phone = ui.input("Telefon", value=comp.phone).classes(C_INPUT)
            iban = ui.input("IBAN", value=comp.iban).classes(C_INPUT)
            tax = ui.input("Steuernummer", value=comp.tax_id).classes(C_INPUT)
            vat = ui.input("USt-ID", value=comp.vat_id).classes(C_INPUT)

        def save():
            with get_session() as s:
                c = s.get(Company, int(comp.id))
                c.name = name.value or ""
                c.first_name = first_name.value or ""
                c.last_name = last_name.value or ""
                c.street = street.value or ""
                c.postal_code = plz.value or ""
                c.city = city.value or ""
                c.country = country.value or ""
                c.email = email.value or ""
                c.phone = phone.value or ""
                c.iban = iban.value or ""
                c.tax_id = tax.value or ""
                c.vat_id = vat.value or ""
                s.add(c)
                s.commit()
            ui.notify("Gespeichert", color="green")

        use_address_autocomplete(
            street,
            plz,
            city,
            country,
            street_dropdown,
        )

        ui.button("Speichern", on_click=save).classes(C_BTN_PRIM)
