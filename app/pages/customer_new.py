from __future__ import annotations
from ._shared import *

# Auto generated page renderer

def render_customer_new(session, comp: Company) -> None:
    ui.label("Neuer Kunde").classes(C_PAGE_TITLE)

    with settings_two_column_layout(max_width_class="max-w-4xl"):
        contact_fields = customer_contact_card()
        address_fields = customer_address_card(country_value=comp.country or "DE")
        with settings_card("Rechnungsempfänger"):
            same_recipient_checkbox = ui.checkbox(
                "Rechnungsempfänger = Kontaktadresse",
                value=True,
            ).classes("mb-2")
            with settings_grid():
                recipient_name = ui.input("Rechnungsempfänger", value="").classes(C_INPUT)
                recipient_street = ui.input("Rechnungsstraße", value="").classes(C_INPUT)
                recipient_plz = ui.input("Rechnungs-PLZ", value="").classes(C_INPUT)
                recipient_city = ui.input("Rechnungs-Ort", value="").classes(C_INPUT)

    name = contact_fields["name"]
    first = contact_fields["first"]
    last = contact_fields["last"]
    email = contact_fields["email"]
    short_code = contact_fields["short_code"]
    street = address_fields["street"]
    plz = address_fields["plz"]
    city = address_fields["city"]
    country = address_fields["country"]

    def _contact_display_name() -> str:
        name_value = (name.value or "").strip()
        if name_value:
            return name_value
        return f"{first.value or ''} {last.value or ''}".strip()

    def _sync_recipient_with_contact() -> None:
        recipient_name.value = _contact_display_name()
        recipient_street.value = street.value or ""
        recipient_plz.value = plz.value or ""
        recipient_city.value = city.value or ""

    def _maybe_sync_recipient() -> None:
        if same_recipient_checkbox.value:
            _sync_recipient_with_contact()

    same_recipient_checkbox.on("update:model-value", lambda _: _maybe_sync_recipient())
    _maybe_sync_recipient()

    def save():
        with get_session() as s:
            c = Customer(
                company_id=int(comp.id),
                kdnr=0,
                name=name.value or "",
                vorname=first.value or "",
                nachname=last.value or "",
                email=email.value or "",
                short_code=short_code.value or "",
                strasse=street.value or "",
                plz=plz.value or "",
                ort=city.value or "",
                country=country.value or "",
                recipient_name=recipient_name.value or "",
                recipient_street=recipient_street.value or "",
                recipient_postal_code=recipient_plz.value or "",
                recipient_city=recipient_city.value or "",
            )
            s.add(c)
            s.commit()
            new_customer_id = int(c.id) if c.id is not None else None
        return_page = app.storage.user.get("return_page")
        if return_page == "invoice_create" and new_customer_id is not None:
            return_invoice_draft_id = app.storage.user.get("return_invoice_draft_id")
            if return_invoice_draft_id is not None:
                app.storage.user["invoice_draft_id"] = return_invoice_draft_id
            app.storage.user["new_customer_id"] = new_customer_id
            app.storage.user["page"] = "invoice_create"
            app.storage.user.pop("return_page", None)
            app.storage.user.pop("return_invoice_draft_id", None)
            ui.navigate.to("/")
            return
        app.storage.user["page"] = "customers"
        ui.navigate.to("/")

    ui.button("Speichern", on_click=save).classes(C_BTN_PRIM)
