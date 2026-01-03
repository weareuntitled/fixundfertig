from __future__ import annotations
from ._shared import *

# Auto generated page renderer

def render_settings(session, comp: Company) -> None:
    ui.label("Einstellungen").classes(C_PAGE_TITLE + " mb-6")

    with ui.card().classes(C_CARD + " p-6 w-full mb-4"):
        ui.label("Logo").classes(C_SECTION_TITLE)

        def on_up(e):
            os.makedirs("./storage", exist_ok=True)
            with open("./storage/logo.png", "wb") as f:
                f.write(e.content.read())
            ui.notify("Hochgeladen", color="green")

        ui.upload(on_upload=on_up, auto_upload=True, label="Bild wählen").props("flat dense").classes("w-full")

    with ui.card().classes(C_CARD + " p-6 w-full mb-4"):
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

    with ui.card().classes(C_CARD + " p-6 w-full"):
        ui.label("Integrationen").classes(C_SECTION_TITLE)

        with ui.row().classes("w-full gap-2"):
            ui.button("Gmail").props("disable").classes(C_BTN_SEC)
            ui.button("Outlook").props("disable").classes(C_BTN_SEC)
            ui.button("IMAP").props("disable").classes(C_BTN_SEC)

        ui.label("E-Mail-Integrationen folgen in Kürze.").classes("text-xs text-slate-500")

        default_sender_email = ui.input("Standard-Absender", value=comp.default_sender_email).classes(C_INPUT).props(
            "placeholder=name@beispiel.de"
        )
        ui.label("Diese Adresse wird als Absender vorgeschlagen.").classes("text-xs text-slate-500 mb-2")

        n8n_webhook_url = ui.input("n8n Webhook URL", value=comp.n8n_webhook_url).classes(C_INPUT).props(
            "placeholder=https://n8n.example/webhook/..."
        )
        ui.label("Webhook für Automationen (z. B. Versand).").classes("text-xs text-slate-500 mb-2")

        n8n_secret = ui.input("n8n Secret Token", value=comp.n8n_secret).classes(C_INPUT).props("placeholder=secret")
        ui.label("Secret für die Authentifizierung im Workflow.").classes("text-xs text-slate-500 mb-2")

        n8n_enabled = ui.switch("n8n aktivieren", value=comp.n8n_enabled).props("dense color=grey-8")
        ui.label("Schaltet das Auslösen des Webhooks ein oder aus.").classes("text-xs text-slate-500")

    def save():
        with get_session() as s:
            c = s.get(Company, int(comp.id))
            c.name = name.value or ""
            c.first_name = first_name.value or ""
            c.last_name = last_name.value or ""
            c.street = street.value or ""
            c.postal_code = plz.value or ""
            c.city = city.value or ""
            c.email = email.value or ""
            c.phone = phone.value or ""
            c.iban = iban.value or ""
            c.tax_id = tax.value or ""
            c.vat_id = vat.value or ""
            c.default_sender_email = default_sender_email.value or ""
            c.n8n_webhook_url = n8n_webhook_url.value or ""
            c.n8n_secret = n8n_secret.value or ""
            c.n8n_enabled = bool(n8n_enabled.value)
            s.add(c)
            s.commit()
        ui.notify("Gespeichert", color="green")

    ui.button("Speichern", on_click=save).classes(C_BTN_PRIM)
