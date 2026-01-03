from __future__ import annotations
from ._shared import *

# Auto generated page renderer

def render_customer_new(session, comp: Company) -> None:
    ui.label("Neuer Kunde").classes(C_PAGE_TITLE)

    with settings_two_column_layout(max_width_class="max-w-4xl"):
        contact_fields = customer_contact_card()
        address_fields = customer_address_card(country_value=comp.country or "DE")

    name = contact_fields["name"]
    first = contact_fields["first"]
    last = contact_fields["last"]
    email = contact_fields["email"]
    street = address_fields["street"]
    plz = address_fields["plz"]
    city = address_fields["city"]
    country = address_fields["country"]

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
