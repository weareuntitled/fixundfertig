"""Customer card UI components extracted from pages/_shared.py."""
from __future__ import annotations

from nicegui import ui

from data import Customer, Company
from ui_components import ff_input, settings_card, settings_grid
from styles import STYLE_DROPDOWN_PANEL

from .shared_helpers import use_address_autocomplete


def customer_contact_card(
    *,
    name_value: str = "",
    first_value: str = "",
    last_value: str = "",
    email_value: str = "",
    short_code_value: str = "",
    title: str = "Kontakt",
) -> dict[str, ui.input]:
    with settings_card(title):
        with settings_grid():
            name = ff_input("Firma", value=name_value)
            first = ff_input("Vorname", value=first_value)
            last = ff_input("Nachname", value=last_value)
            email = ff_input("Email", value=email_value)
            short_code = ff_input("Kürzel (optional)", value=short_code_value)

    return {
        "name": name,
        "first": first,
        "last": last,
        "email": email,
        "short_code": short_code,
    }


def customer_address_card(
    *,
    street_value: str = "",
    plz_value: str = "",
    city_value: str = "",
    country_value: str = "",
    country_fallback: str = "DE",
    title: str = "Adresse",
) -> dict[str, ui.input]:
    with settings_card(title):
        with settings_grid():
            with ui.element("div").classes("relative w-full"):
                street = ff_input("Straße", value=street_value)
                street_dropdown = ui.element("div").classes(STYLE_DROPDOWN_PANEL)
            plz = ff_input("PLZ", value=plz_value)
            city = ff_input("Ort", value=city_value)
            country = ff_input("Land", value=country_value or country_fallback)

    use_address_autocomplete(
        street,
        plz,
        city,
        country,
        street_dropdown,
    )

    return {
        "street": street,
        "plz": plz,
        "city": city,
        "country": country,
    }


def insert_customer(
    session,
    comp: Company,
    *,
    name: str = "",
    vorname: str = "",
    nachname: str = "",
    email: str = "",
    short_code: str = "",
    strasse: str = "",
    plz: str = "",
    ort: str = "",
    country: str = "",
    recipient_name: str = "",
    recipient_street: str = "",
    recipient_postal_code: str = "",
    recipient_city: str = "",
) -> Customer:
    c = Customer(
        company_id=int(comp.id),
        kdnr=0,
        name=name,
        vorname=vorname,
        nachname=nachname,
        email=email,
        short_code=short_code,
        strasse=strasse,
        plz=plz,
        ort=ort,
        country=country,
        recipient_name=recipient_name,
        recipient_street=recipient_street,
        recipient_postal_code=recipient_postal_code,
        recipient_city=recipient_city,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def customer_business_meta_card(
    *,
    vat_value: str = "",
    title: str = "Business",
) -> dict[str, ui.input]:
    with settings_card(title):
        with settings_grid():
            vat = ff_input("USt-ID", value=vat_value)

    return {"vat": vat}
