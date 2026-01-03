from __future__ import annotations
from ._shared import *

# Auto generated page renderer

def render_settings(session, comp: Company) -> None:
    with ui.column().classes(C_CONTAINER):
        ui.label("Einstellungen").classes(C_PAGE_TITLE + " mb-2")

        with ui.element("div").classes("w-full grid grid-cols-1 lg:grid-cols-3 gap-4"):
            with ui.column().classes("w-full gap-4 lg:col-span-2"):
                business_fields = render_business_meta_card(comp)
                contact_fields = render_contact_card(comp)
                address_fields = render_address_card(comp)

                with ui.row().classes("w-full justify-end"):
                    def save():
                        with get_session() as s:
                            c = s.get(Company, int(comp.id))
                            c.name = business_fields["name"].value or ""
                            c.iban = business_fields["iban"].value or ""
                            c.tax_id = business_fields["tax_id"].value or ""
                            c.vat_id = business_fields["vat_id"].value or ""
                            c.first_name = contact_fields["first_name"].value or ""
                            c.last_name = contact_fields["last_name"].value or ""
                            c.email = contact_fields["email"].value or ""
                            c.phone = contact_fields["phone"].value or ""
                            c.street = address_fields["street"].value or ""
                            c.postal_code = address_fields["postal_code"].value or ""
                            c.city = address_fields["city"].value or ""
                            s.add(c)
                            s.commit()
                        ui.notify("Gespeichert", color="green")

                    ui.button("Speichern", on_click=save).classes(C_BTN_PRIM)

            with ui.column().classes("w-full gap-4"):
                render_logo_card()
                render_integrations_card()
