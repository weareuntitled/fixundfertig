from __future__ import annotations

import secrets

from ._shared import *
from integrations.n8n_client import post_to_n8n

# Auto generated page renderer

def render_settings(session, comp: Company) -> None:
    user_id = get_current_user_id(session)
    if user_id is None or comp.user_id != user_id:
        ui.notify("Kein Zugriff auf Unternehmen.", color="red")
        return
    ui.label("Einstellungen").classes(C_PAGE_TITLE + " mb-6")

    with settings_two_column_layout(max_width_class="max-w-5xl"):
        with settings_card("Person / Kontakt"):
            with settings_grid():
                name = ui.input("Firma", value=comp.name).classes(C_INPUT)
                first_name = ui.input("Vorname", value=comp.first_name).classes(C_INPUT)
                last_name = ui.input("Nachname", value=comp.last_name).classes(C_INPUT)
                email = ui.input("Email", value=comp.email).classes(C_INPUT)
                phone = ui.input("Telefon", value=comp.phone).classes(C_INPUT)

        with settings_card("Adresse"):
            with settings_grid():
                with ui.element("div").classes("relative w-full"):
                    street = ui.input("Straße", value=comp.street).classes(C_INPUT)
                    street_dropdown = ui.element("div").classes(
                        "absolute left-0 right-0 mt-1 z-10 bg-white border border-slate-200 rounded-lg shadow-sm"
                    )
                plz = ui.input("PLZ", value=comp.postal_code).classes(C_INPUT)
                city = ui.input("Ort", value=comp.city).classes(C_INPUT)
                country = ui.input("Land", value=comp.country or "DE").classes(C_INPUT)

        with settings_card("Logo Upload"):

            def on_up(e):
                os.makedirs("./storage", exist_ok=True)
                with open("./storage/logo.png", "wb") as f:
                    f.write(e.content.read())
                ui.notify("Hochgeladen", color="green")

            ui.upload(on_upload=on_up, auto_upload=True, label="Bild wählen").props("flat dense").classes("w-full")

    with settings_card("Business Meta", classes="mb-4"):
        business_type_options = [
            "Einzelunternehmen",
            "Freelancer",
            "GbR/Partnership",
            "GmbH",
            "UG",
            "Nonprofit",
            "Other",
        ]
        with settings_grid():
            business_type = ui.select(
                options=business_type_options,
                label="Unternehmensform",
                value=comp.business_type or "Einzelunternehmen",
            ).classes(C_INPUT)
            is_small_business = ui.switch(
                "Kleinunternehmer",
                value=bool(comp.is_small_business) if comp.is_small_business is not None else False,
            ).classes(C_INPUT)
            iban = ui.input("IBAN", value=comp.iban).classes(C_INPUT)
            tax = ui.input("Steuernummer", value=comp.tax_id).classes(C_INPUT)
            vat = ui.input("USt-ID", value=comp.vat_id).classes(C_INPUT)
    with settings_card("Rechnungsnummern", classes="mb-4"):
        with settings_grid():
            next_invoice_nr = ui.number(
                "Nächste Rechnungsnummer",
                value=comp.next_invoice_nr,
                min=1,
                step=1,
            ).classes(C_INPUT)
            invoice_number_template = ui.input(
                "Rechnungsnummer-Regel",
                value=comp.invoice_number_template or "{seq}",
                placeholder="{seq}",
            ).classes(C_INPUT)
            invoice_filename_template = ui.input(
                "Dateiname-Regel (PDF)",
                value=comp.invoice_filename_template or "rechnung_{nr}",
                placeholder="rechnung_{nr}",
            ).classes(C_INPUT)
        ui.label(
            "Platzhalter: {seq} (laufende Nummer), {date}, {customer_code}, {customer_kdnr}, {nr} (fertige Nummer)."
        ).classes("text-sm text-slate-500")
    with settings_card("Integrationen", classes="mb-4"):
        ui.label("Email Connection").classes("text-sm font-semibold text-slate-700")
        ui.label("Gmail, Outlook und IMAP folgen in einem späteren Release.").classes("text-sm text-slate-500")
        with ui.row().classes("w-full gap-2 flex-wrap"):
            ui.button("Gmail").props("flat dense").classes("text-slate-500").disable()
            ui.button("Outlook").props("flat dense").classes("text-slate-500").disable()
            ui.button("IMAP").props("flat dense").classes("text-slate-500").disable()
        with settings_grid():
            default_sender_email = ui.input(
                "Standard Absender-Email (optional)",
                value=comp.default_sender_email,
            ).classes(C_INPUT)
        ui.label("Der Standard-Absender wird später für automatische Mails verwendet.").classes("text-sm text-slate-500")

        ui.separator().classes("my-4")

        ui.label("n8n").classes("text-sm font-semibold text-slate-700")
        ui.label("Webhooks für zukünftige Automationen, z. B. Rechnungen erstellen oder senden.").classes(
            "text-sm text-slate-500"
        )
        with settings_grid():
            n8n_webhook_url = ui.input("n8n Webhook URL", value=comp.n8n_webhook_url).classes(C_INPUT)
            n8n_secret = ui.input("n8n Secret", value=comp.n8n_secret).classes(C_INPUT).props("type=password")
            n8n_enabled = ui.switch("n8n aktivieren", value=comp.n8n_enabled).props("dense color=grey-8")
            google_drive_folder_id = ui.input(
                "Google Drive Ordner-ID",
                value=comp.google_drive_folder_id,
            ).classes(C_INPUT)
        with ui.row().classes("w-full gap-2 flex-wrap"):
            ui.button(
                "Secret generieren",
                on_click=lambda: (
                    n8n_secret.set_value(secrets.token_urlsafe(32)),
                    ui.notify("Secret generiert", color="green"),
                ),
            ).classes(C_BTN_SEC)

            def test_n8n_webhook() -> None:
                try:
                    resp = post_to_n8n(
                        webhook_url=(n8n_webhook_url.value or "").strip(),
                        secret=(n8n_secret.value or "").strip(),
                        event="ping",
                        company_id=comp.id,
                        data={"name": name.value, "email": email.value},
                    )
                except Exception as exc:
                    ui.notify(f"n8n Fehler: {exc}", color="red")
                    return
                ui.notify(f"n8n OK. HTTP {resp.status_code}", color="green")

            ui.button("Webhook testen", on_click=test_n8n_webhook).classes(C_BTN_SEC)

    def save():
        with get_session() as s:
            current_user_id = get_current_user_id(s)
            if current_user_id is None:
                ui.notify("Kein Zugriff auf Unternehmen.", color="red")
                return
            statement = select(Company).where(
                Company.id == int(comp.id),
                Company.user_id == current_user_id,
            )
            c = s.exec(statement).first()
            if not c:
                ui.notify("Kein Zugriff auf Unternehmen.", color="red")
                return
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
            c.business_type = business_type.value or "Einzelunternehmen"
            c.is_small_business = bool(is_small_business.value)
            c.next_invoice_nr = int(next_invoice_nr.value or 0) or 1
            c.invoice_number_template = invoice_number_template.value or "{seq}"
            c.invoice_filename_template = invoice_filename_template.value or "rechnung_{nr}"
            c.default_sender_email = default_sender_email.value or ""
            c.n8n_webhook_url = n8n_webhook_url.value or ""
            c.n8n_secret = n8n_secret.value or ""
            c.n8n_enabled = bool(n8n_enabled.value)
            c.google_drive_folder_id = google_drive_folder_id.value or ""
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

    with ui.element("div").classes("w-full max-w-5xl mx-auto mt-4 flex justify-end"):
        ui.button("Speichern", on_click=save).classes(C_BTN_PRIM)
