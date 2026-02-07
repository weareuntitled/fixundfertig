from __future__ import annotations
from ._shared import *
from styles import STYLE_TEXT_MUTED
from ui_components import ff_btn_danger, ff_btn_primary, ff_btn_secondary, ff_card, ff_input

# Auto generated page renderer

def render_customer_detail(session, comp: Company, customer_id: int | None) -> None:
    if not customer_id:
        ui.notify("Kunde nicht gefunden", color="red")
        app.storage.user["page"] = "customers"
        ui.navigate.to("/")
        return

    customer = session.get(Customer, int(customer_id))
    if not customer:
        ui.label("Kunde nicht gefunden").classes(C_PAGE_TITLE)
        ui.button("Zurück", icon="arrow_back", on_click=lambda: (app.storage.user.__setitem__("page", "customers"), ui.navigate.to("/"))).classes(C_BTN_SEC)
        return

    invoices = session.exec(select(Invoice).where(Invoice.customer_id == customer.id).order_by(Invoice.id.desc())).all()
    can_delete = len(invoices) == 0

    def back():
        app.storage.user["page"] = "customers"
        ui.navigate.to("/")

    with ui.row().classes("items-center gap-3 mb-2"):
        ui.button(icon="arrow_back", on_click=back).props("flat round").classes("text-slate-500 hover:text-slate-900")
        ui.label(customer.display_name).classes(C_PAGE_TITLE)

    with settings_two_column_layout():
        contact_fields = customer_contact_card(
            name_value=customer.name,
            first_value=customer.vorname,
            last_value=customer.nachname,
            email_value=customer.email,
            short_code_value=customer.short_code,
        )
        address_fields = customer_address_card(
            street_value=customer.strasse,
            plz_value=customer.plz,
            city_value=customer.ort,
            country_value=customer.country,
        )
        business_fields = customer_business_meta_card(vat_value=customer.vat_id)

        with settings_card("Rechnungsempfänger"):
            with settings_grid():
                recipient_name = ff_input("Rechnungsempfänger", value=customer.recipient_name)
                recipient_street = ff_input("Rechnungsstraße", value=customer.recipient_street)
                recipient_plz = ff_input("Rechnungs-PLZ", value=customer.recipient_postal_code)
                recipient_city = ff_input("Rechnungs-Ort", value=customer.recipient_city)

    name = contact_fields["name"]
    first = contact_fields["first"]
    last = contact_fields["last"]
    email = contact_fields["email"]
    short_code = contact_fields["short_code"]
    street = address_fields["street"]
    plz = address_fields["plz"]
    city = address_fields["city"]
    country = address_fields["country"]
    vat = business_fields["vat"]

    fields = [
        name,
        first,
        last,
        email,
        short_code,
        street,
        plz,
        city,
        country,
        vat,
        recipient_name,
        recipient_street,
        recipient_plz,
        recipient_city,
    ]

    def set_editable(editing: bool):
        for f in fields:
            if editing:
                f.enable()
            else:
                f.disable()

    set_editable(False)

    def save():
        with get_session() as s:
            c = s.get(Customer, int(customer.id))
            if not c:
                ui.notify("Kunde nicht gefunden", color="red")
                return
            c.name = name.value or ""
            c.vorname = first.value or ""
            c.nachname = last.value or ""
            c.email = email.value or ""
            c.short_code = short_code.value or ""
            c.strasse = street.value or ""
            c.plz = plz.value or ""
            c.ort = city.value or ""
            c.vat_id = vat.value or ""
            c.country = country.value or ""
            c.recipient_name = recipient_name.value or ""
            c.recipient_street = recipient_street.value or ""
            c.recipient_postal_code = recipient_plz.value or ""
            c.recipient_city = recipient_city.value or ""
            s.add(c)
            s.commit()

        ui.notify("Gespeichert", color="green")
        set_editable(False)
        save_button.disable()
        edit_button.enable()

    def cancel_edit():
        name.value = customer.name
        first.value = customer.vorname
        last.value = customer.nachname
        email.value = customer.email
        short_code.value = customer.short_code
        street.value = customer.strasse
        plz.value = customer.plz
        city.value = customer.ort
        vat.value = customer.vat_id
        country.value = customer.country
        recipient_name.value = customer.recipient_name
        recipient_street.value = customer.recipient_street
        recipient_plz.value = customer.recipient_postal_code
        recipient_city.value = customer.recipient_city

        set_editable(False)
        save_button.disable()
        edit_button.enable()

    with ui.row().classes("gap-2 mt-4"):
        edit_button = ff_btn_secondary(
            "Bearbeiten",
            on_click=lambda: (set_editable(True), save_button.enable(), edit_button.disable()),
        )
        save_button = ff_btn_primary("Speichern", on_click=save)
        save_button.disable()
        ff_btn_secondary("Abbrechen", on_click=cancel_edit)

    def delete_customer():
        with get_session() as s:
            c = s.get(Customer, int(customer.id))
            if not c:
                ui.notify("Kunde nicht gefunden", color="red")
                return
            invs = s.exec(select(Invoice).where(Invoice.customer_id == customer.id)).all()
            if invs:
                ui.notify("Kunde hat Rechnungen und kann nicht gelöscht werden", color="red")
                return
            s.delete(c)
            s.commit()
        ui.notify("Kunde gelöscht", color="green")
        back()

    def archive_customer():
        with get_session() as s:
            c = s.get(Customer, int(customer.id))
            if not c:
                ui.notify("Kunde nicht gefunden", color="red")
                return
            c.archived = True
            s.add(c)
            s.commit()
        ui.notify("Kunde archiviert", color="green")
        back()

    with ui.row().classes("gap-2 mt-2"):
        if can_delete:
            ff_btn_danger("Löschen", icon="delete", on_click=delete_customer)
        else:
            ff_btn_secondary("Archivieren", icon="archive", on_click=archive_customer)

    ui.label("Rechnungen").classes(C_SECTION_TITLE + " mt-6 mb-2")
    if not invoices:
        ui.label("Keine Rechnungen vorhanden").classes(STYLE_TEXT_MUTED)
    else:
        with ff_card(pad="p-0", classes="overflow-hidden"):
            with ui.row().classes(C_TABLE_HEADER + " hidden sm:flex"):
                ui.label("Nr").classes("w-20 font-bold")
                ui.label("Datum").classes("w-28 font-bold")
                ui.label("Status").classes("w-28 font-bold")
                ui.label("Betrag").classes("w-24 font-bold text-right")

            for inv in invoices:
                def open_invoice(target: Invoice = inv):
                    if target.status == InvoiceStatus.DRAFT:
                        _open_invoice_editor(int(target.id))
                    else:
                        _open_invoice_detail(int(target.id))

                with ui.row().classes(C_TABLE_ROW + " hidden sm:flex cursor-pointer hover:bg-slate-50").on(
                    "click", lambda _, x=inv: open_invoice(x)
                ):
                    ui.label(f"#{inv.nr}" if inv.nr else "-").classes("w-20 text-xs font-mono")
                    ui.label(inv.date or "-").classes("w-28 text-xs font-mono")
                    ui.label(format_invoice_status(inv.status)).classes(invoice_status_badge(inv.status))
                    ui.label(f"{float(inv.total_brutto or 0):,.2f} €").classes("w-24 text-right text-sm font-mono")

                with ui.element("div").classes("sm:hidden border-b border-slate-200/70 p-4").on(
                    "click", lambda _, x=inv: open_invoice(x)
                ):
                    with ui.row().classes("items-center justify-between gap-2"):
                        ui.label(f"#{inv.nr}" if inv.nr else "-").classes("text-sm font-mono text-slate-900")
                        ui.label(f"{float(inv.total_brutto or 0):,.2f} €").classes("text-sm font-mono text-slate-900")
                    with ui.row().classes("items-center justify-between text-xs text-slate-500 mt-1"):
                        ui.label(inv.date or "-").classes("font-mono")
                        ui.label(format_invoice_status(inv.status)).classes(invoice_status_badge(inv.status))
