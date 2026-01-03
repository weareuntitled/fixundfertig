from __future__ import annotations
from ._shared import *

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
        ui.button(icon="arrow_back", on_click=back).props("flat round").classes("text-slate-500")
        ui.label(customer.display_name).classes(C_PAGE_TITLE)

    with ui.card().classes(C_CARD + " p-6 w-full max-w-3xl"):
        name = ui.input("Firma", value=customer.name).classes(C_INPUT)
        first = ui.input("Vorname", value=customer.vorname).classes(C_INPUT)
        last = ui.input("Nachname", value=customer.nachname).classes(C_INPUT)
        email = ui.input("Email", value=customer.email).classes(C_INPUT)
        with ui.column().classes("w-full gap-1"):
            street = ui.input("Straße", value=customer.strasse).classes(C_INPUT)
            street_dropdown = ui.column().classes(
                "w-full border border-slate-200 rounded-lg bg-white shadow-lg max-h-56 overflow-auto"
            ).props("role=listbox aria-label=Adressvorschläge")
        plz = ui.input("PLZ", value=customer.plz).classes(C_INPUT)
        city = ui.input("Ort", value=customer.ort).classes(C_INPUT)
        country = ui.input("Land", value=customer.country).classes(C_INPUT)
        vat = ui.input("USt-ID", value=customer.vat_id).classes(C_INPUT)

        recipient_name = ui.input("Rechnungsempfänger", value=customer.recipient_name).classes(C_INPUT)
        recipient_street = ui.input("Rechnungsstraße", value=customer.recipient_street).classes(C_INPUT)
        recipient_plz = ui.input("Rechnungs-PLZ", value=customer.recipient_postal_code).classes(C_INPUT)
        recipient_city = ui.input("Rechnungs-Ort", value=customer.recipient_city).classes(C_INPUT)

        fields = [name, first, last, email, street, plz, city, country, vat, recipient_name, recipient_street, recipient_plz, recipient_city]

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
                c.strasse = street.value or ""
                c.plz = plz.value or ""
                c.ort = city.value or ""
                c.country = country.value or ""
                c.vat_id = vat.value or ""
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
            street.value = customer.strasse
            plz.value = customer.plz
            city.value = customer.ort
            country.value = customer.country
            vat.value = customer.vat_id
            recipient_name.value = customer.recipient_name
            recipient_street.value = customer.recipient_street
            recipient_plz.value = customer.recipient_postal_code
            recipient_city.value = customer.recipient_city

            set_editable(False)
            save_button.disable()
            edit_button.enable()

        with ui.row().classes("gap-2 mt-4"):
            edit_button = ui.button("Bearbeiten", on_click=lambda: (set_editable(True), save_button.enable(), edit_button.disable())).classes(C_BTN_SEC)
            save_button = ui.button("Speichern", on_click=save).classes(C_BTN_PRIM)
            save_button.disable()
            ui.button("Abbrechen", on_click=cancel_edit).classes(C_BTN_SEC)

        use_address_autocomplete(
            street,
            plz,
            city,
            country,
            street_dropdown,
        )

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
                ui.button("Löschen", icon="delete", on_click=delete_customer).classes("bg-rose-600 text-white hover:bg-rose-700")
            else:
                ui.button("Archivieren", icon="archive", on_click=archive_customer).classes(C_BTN_SEC)

    ui.label("Rechnungen").classes(C_SECTION_TITLE + " mt-6 mb-2")
    if not invoices:
        ui.label("Keine Rechnungen vorhanden").classes("text-sm text-slate-500")
    else:
        with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
            with ui.row().classes(C_TABLE_HEADER):
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

                with ui.row().classes(C_TABLE_ROW + " cursor-pointer hover:bg-slate-50").on("click", lambda _, x=inv: open_invoice(x)):
                    ui.label(f"#{inv.nr}" if inv.nr else "-").classes("w-20 text-xs font-mono")
                    ui.label(inv.date or "-").classes("w-28 text-xs font-mono")
                    ui.label(format_invoice_status(inv.status)).classes(invoice_status_badge(inv.status))
                    ui.label(f"{float(inv.total_brutto or 0):,.2f} €").classes("w-24 text-right text-sm font-mono")
