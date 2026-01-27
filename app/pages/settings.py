# app/pages/settings.py
from __future__ import annotations

import json
import mimetypes
import os
import secrets
import httpx
import time

from nicegui import app, ui
from sqlmodel import select

from ._shared import (
    C_BTN_PRIM,
    C_BTN_SEC,
    C_CARD,
    C_INPUT,
    C_PAGE_TITLE,
    Company,
    get_current_user_id,
    get_session,
    use_address_autocomplete,
)
from auth_guard import clear_auth_session
from integrations.n8n_client import post_to_n8n
from services.companies import create_company, delete_company, list_companies, update_company
from services.iban import lookup_bank_from_iban
from services.storage import cleanup_company_logos, company_logo_path, delete_company_dirs, ensure_company_dirs


LINK_TEXT = "text-sm text-blue-600 hover:text-blue-700"


def _company_select_options(companies: list[Company]) -> dict[int, str]:
    opts: dict[int, str] = {}
    for c in companies:
        if not c or not c.id:
            continue
        cid = int(c.id)
        label = (c.name or "Unternehmen").strip() or "Unternehmen"
        opts[cid] = f"{label} (#{cid})"
    return opts


def render_settings(session, comp: Company) -> None:
    user_id = get_current_user_id(session)
    if user_id is None or int(comp.user_id or 0) != int(user_id):
        ui.notify("Kein Zugriff auf Unternehmen.", color="red")
        return
    user_id = int(user_id)

    # Load fresh companies list
    companies = list_companies(user_id)
    if not companies:
        try:
            _ = create_company(user_id, name="Unternehmen")
        except Exception:
            pass
        companies = list_companies(user_id)

    # Resolve active company id from storage
    active_company_id_raw = app.storage.user.get("active_company_id")
    try:
        active_company_id = int(active_company_id_raw) if active_company_id_raw is not None else int(comp.id or 0)
    except Exception:
        active_company_id = int(comp.id or 0)

    def _open_create_dialog() -> None:
        dlg = ui.dialog()
        with dlg, ui.card().classes("p-5 w-[420px]"):
            ui.label("Neues Unternehmen").classes("font-semibold")
            name_in = ui.input("Name", placeholder="z.B. untitled-ux").classes(C_INPUT)
            err = ui.label("").classes("text-sm text-rose-600")
            err.set_visibility(False)

            def _do_create() -> None:
                err.set_visibility(False)
                name = (name_in.value or "").strip()
                if not name:
                    err.text = "Name ist erforderlich"
                    err.set_visibility(True)
                    return
                try:
                    new_comp = create_company(user_id, name=name)
                except Exception as exc:
                    err.text = str(exc)
                    err.set_visibility(True)
                    return

                if new_comp and new_comp.id:
                    app.storage.user["active_company_id"] = int(new_comp.id)
                app.storage.user["page"] = "settings"
                dlg.close()
                ui.navigate.to("/")

            with ui.row().classes("justify-end gap-2 w-full mt-3"):
                ui.button("Abbrechen", on_click=dlg.close).classes(C_BTN_SEC)
                ui.button("Erstellen", on_click=_do_create).classes(C_BTN_PRIM)

        dlg.open()

    def _open_delete_dialog() -> None:
        if len(companies) <= 1:
            ui.notify("Mindestens ein Unternehmen muss bestehen bleiben.", color="orange")
            return

        dlg = ui.dialog()
        with dlg, ui.card().classes("p-5 w-[520px]"):
            ui.label("Unternehmen löschen").classes("font-semibold")
            ui.label(
                "Das Unternehmen wird inklusive Kunden, Rechnungen, Ausgaben und Uploads gelöscht."
            ).classes("text-sm text-slate-600")
            confirm = ui.input('Tippe "DELETE" zur Bestätigung').classes(C_INPUT)

            def _do_delete() -> None:
                if (confirm.value or "").strip().upper() != "DELETE":
                    ui.notify('Bitte "DELETE" tippen.', color="orange")
                    return

                cid = int(app.storage.user.get("active_company_id") or comp.id or 0)
                if not cid:
                    ui.notify("Keine Company-ID gefunden.", color="red")
                    return

                try:
                    delete_company_dirs(cid)
                except Exception:
                    pass

                try:
                    delete_company(user_id, cid)
                except Exception as exc:
                    ui.notify(f"Löschen fehlgeschlagen: {exc}", color="red")
                    return

                remaining = list_companies(user_id)
                if remaining and remaining[0].id:
                    app.storage.user["active_company_id"] = int(remaining[0].id)
                else:
                    app.storage.user.pop("active_company_id", None)

                app.storage.user["page"] = "settings"
                dlg.close()
                ui.navigate.to("/")

            with ui.row().classes("justify-end gap-2 w-full mt-3"):
                ui.button("Abbrechen", on_click=dlg.close).classes(C_BTN_SEC)
                ui.button("Löschen", on_click=_do_delete).classes(C_BTN_PRIM)

        dlg.open()

    with ui.row().classes("w-full justify-between items-center mb-6"):
        ui.label("Einstellungen").classes(C_PAGE_TITLE)
        ui.button("Neues Unternehmen", on_click=_open_create_dialog).classes(C_BTN_PRIM)

    # ----------------------------
    # Company switcher + CRUD
    # ----------------------------
    with ui.card().classes(C_CARD + " p-5 w-full max-w-5xl mx-auto mb-4"):
        ui.label("Unternehmen").classes("text-sm font-semibold text-slate-700")

        options = _company_select_options(companies)

        # Active-ID absichern: muss ein Key in options sein
        if options:
            if active_company_id not in options:
                active_company_id = next(iter(options.keys()))
                app.storage.user["active_company_id"] = active_company_id
        else:
            # sollte praktisch nie passieren, aber verhindert Invalid-Value
            active_company_id = 0
            app.storage.user.pop("active_company_id", None)

        def _switch_company(e) -> None:
            try:
                cid = int(e.value)
            except Exception:
                return
            if options and cid not in options:
                return
            app.storage.user["active_company_id"] = cid
            app.storage.user["page"] = "settings"
            ui.navigate.to("/")

        ui.select(
            options=options,         # dict[int, str]
            value=active_company_id, # int, muss key sein
            label="Aktives Unternehmen",
            on_change=_switch_company,
        ).classes(C_INPUT)

        with ui.row().classes("w-full gap-2 mt-3 flex-wrap"):
            ui.button("Unternehmen löschen", on_click=_open_delete_dialog).classes(C_BTN_SEC)

    # Refresh comp to active company for this user
    with get_session() as s:
        statement = select(Company).where(
            Company.id == int(app.storage.user.get("active_company_id") or comp.id or 0),
            Company.user_id == user_id,
        )
        active_comp = s.exec(statement).first()
        if active_comp:
            comp = active_comp

    # ----------------------------
    # Settings UI
    # ----------------------------
    ui.label("").classes("mb-1")

    with ui.element("div").classes("w-full max-w-5xl mx-auto"):
        with ui.element("div").classes("grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-6"):
            with ui.element("div").classes("space-y-3"):
                ui.label("Logo").classes("text-sm font-semibold text-slate-700")
                with ui.element("div").classes("w-full rounded-lg border border-slate-200 bg-white p-4 space-y-3"):
                    logo_url = ""
                    logo_exists = False
                    if comp.id:
                        logo_path = company_logo_path(int(comp.id))
                        logo_exists = os.path.exists(logo_path)
                        logo_url = f"/{logo_path.replace(os.sep, '/')}"

                    logo_preview = ui.image(logo_url).classes(
                        "w-full h-40 object-contain rounded-md border border-slate-100 bg-slate-50"
                    )
                    logo_preview.set_visibility(logo_exists)
                    logo_placeholder = ui.label("Kein Logo hochgeladen").classes(
                        "text-sm text-slate-500 text-center w-full py-8"
                    )
                    logo_placeholder.set_visibility(not logo_exists)

                    def _refresh_logo_preview(cid: int) -> None:
                        logo_path = company_logo_path(cid)
                        logo_preview.set_source(f"/{logo_path.replace(os.sep, '/')}?v={int(time.time())}")
                        logo_preview.set_visibility(True)
                        logo_placeholder.set_visibility(False)

                    def on_up(e) -> None:
                        if not comp.id:
                            ui.notify("Kein aktives Unternehmen.", color="red")
                            return
                        cid = int(comp.id)
                        ensure_company_dirs(cid)
                        upload_name = getattr(e, "name", "") or getattr(getattr(e, "file", None), "name", "")
                        content_type = getattr(e, "type", "") or getattr(
                            getattr(e, "file", None), "content_type", ""
                        )
                        ext = os.path.splitext(upload_name or "")[1].lower().lstrip(".")
                        if not content_type:
                            content_type = mimetypes.guess_type(upload_name or "")[0] or ""

                        if content_type == "image/png":
                            ext = "png"
                        elif content_type in {"image/jpeg", "image/jpg"}:
                            ext = "jpg"

                        if ext not in {"png", "jpg", "jpeg"}:
                            ui.notify("Bitte PNG oder JPG hochladen.", color="orange")
                            return

                        save_path = company_logo_path(cid, ext)

                        try:
                            if hasattr(e, "file") and getattr(e, "file", None) is not None:
                                e.file.save(save_path)
                            elif hasattr(e, "content") and e.content is not None:
                                with open(save_path, "wb") as handle:
                                    handle.write(e.content)
                            else:
                                raise RuntimeError("Keine Upload-Daten gefunden.")
                        except Exception as exc:
                            ui.notify(f"Upload fehlgeschlagen: {exc}", color="red")
                            return

                        cleanup_company_logos(cid, ext)

                        _refresh_logo_preview(cid)
                        ui.notify("Hochgeladen", color="green")

                    ui.upload(on_upload=on_up, auto_upload=True, label="Bild wählen").classes(
                        f"w-full {C_BTN_SEC}"
                    ).props("accept=.png,.jpg,.jpeg,image/png,image/jpeg")

            with ui.element("div").classes("space-y-6"):
                ui.label("Unternehmen & Kontakt").classes("text-sm font-semibold text-slate-700")
                with ui.element("div").classes("grid grid-cols-1 md:grid-cols-2 gap-4"):
                    name = ui.input("Firma", value=comp.name).classes(C_INPUT)
                    first_name = ui.input("Vorname", value=comp.first_name).classes(C_INPUT)
                    last_name = ui.input("Nachname", value=comp.last_name).classes(C_INPUT)
                    email = ui.input("Email", value=comp.email).classes(C_INPUT)
                    phone = ui.input("Telefon", value=comp.phone).classes(C_INPUT)

                ui.separator().classes("my-1")

                ui.label("Adresse").classes("text-sm font-semibold text-slate-700")
                with ui.element("div").classes("grid grid-cols-1 md:grid-cols-2 gap-4"):
                    with ui.element("div").classes("relative w-full"):
                        street = ui.input("Straße", value=comp.street).classes(C_INPUT)
                        street_dropdown = ui.element("div").classes(
                            "absolute left-0 right-0 mt-1 z-10 bg-white border border-slate-200 rounded-lg shadow-sm"
                        )
                    plz = ui.input("PLZ", value=comp.postal_code).classes(C_INPUT)
                    city = ui.input("Ort", value=comp.city).classes(C_INPUT)
                    country = ui.input("Land", value=comp.country or "DE").classes(C_INPUT)

        with ui.element("div").classes("w-full mt-6 space-y-4"):
            with ui.expansion("Business Meta").classes("w-full"):
                business_type_options = [
                    "Einzelunternehmen",
                    "Freelancer",
                    "GbR/Partnership",
                    "GmbH",
                    "UG",
                    "Nonprofit",
                    "Other",
                ]

                with ui.element("div").classes("grid grid-cols-1 md:grid-cols-2 gap-4 pt-2"):
                    business_type = ui.select(
                        options=business_type_options,
                        label="Unternehmensform",
                        value=comp.business_type or "Einzelunternehmen",
                    ).classes(C_INPUT)

                    is_small_business = ui.switch(
                        "Kleinunternehmer",
                        value=bool(comp.is_small_business) if comp.is_small_business is not None else False,
                    ).props("dense color=grey-8")

                    iban = ui.input("IBAN", value=comp.iban).classes(C_INPUT)
                    bic = ui.input("BIC", value=getattr(comp, "bic", "") or "").classes(C_INPUT)
                    bank_name = ui.input("Bankname", value=getattr(comp, "bank_name", "") or "").classes(C_INPUT)

                    tax = ui.input("Steuernummer", value=comp.tax_id).classes(C_INPUT)
                    vat = ui.input("USt-ID", value=comp.vat_id).classes(C_INPUT)

                def _iban_lookup(_e=None) -> None:
                    b, bn = lookup_bank_from_iban(iban.value or "")
                    if b and not (bic.value or "").strip():
                        bic.set_value(b)
                    if bn and not (bank_name.value or "").strip():
                        bank_name.set_value(bn)

                iban.on("blur", _iban_lookup)

            with ui.expansion("Rechnungsnummern").classes("w-full"):
                with ui.element("div").classes("grid grid-cols-1 md:grid-cols-2 gap-4 pt-2"):
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

                ui.label("Platzhalter: {seq}, {date}, {customer_code}, {customer_kdnr}, {nr}.").classes(
                    "text-sm text-slate-500"
                )

            with ui.expansion("Integrationen").classes("w-full"):
                ui.label("SMTP (für Mails aus der App)").classes("text-sm font-semibold text-slate-700 pt-2")
                ui.label("Port 465 nutzt SSL. Andere Ports nutzen STARTTLS.").classes("text-sm text-slate-500")

                with ui.element("div").classes("grid grid-cols-1 md:grid-cols-2 gap-4 pt-2"):
                    smtp_server = ui.input("SMTP Server", value=getattr(comp, "smtp_server", "") or "").classes(C_INPUT)
                    smtp_port = ui.number("SMTP Port", value=getattr(comp, "smtp_port", 465) or 465).classes(C_INPUT)
                    smtp_user = ui.input("SMTP User", value=getattr(comp, "smtp_user", "") or "").classes(C_INPUT)
                    smtp_password = (
                        ui.input("SMTP Passwort", value=getattr(comp, "smtp_password", "") or "")
                        .props("type=password")
                        .classes(C_INPUT)
                    )
                    default_sender_email = ui.input(
                        "Standard Absender-Email (optional)",
                        value=comp.default_sender_email,
                    ).classes(C_INPUT)

                ui.separator().classes("my-4")

                ui.label("n8n").classes("text-sm font-semibold text-slate-700")
                ui.label("Webhooks für Automationen.").classes("text-sm text-slate-500")

                with ui.element("div").classes("grid grid-cols-1 md:grid-cols-2 gap-4 pt-2"):
                    n8n_webhook_url_test = ui.input(
                        "n8n Webhook URL (Test)",
                        value=comp.n8n_webhook_url_test,
                    ).classes(C_INPUT)
                    n8n_webhook_url_prod = ui.input(
                        "n8n Webhook URL (Production)",
                        value=comp.n8n_webhook_url_prod or comp.n8n_webhook_url,
                    ).classes(C_INPUT)
                    n8n_secret = ui.input("n8n Secret", value=comp.n8n_secret).classes(C_INPUT).props("type=password")
                    n8n_enabled = ui.switch("n8n aktivieren", value=bool(comp.n8n_enabled)).props("dense color=grey-8")
                    google_drive_folder_id = ui.input(
                        "Google Drive Ordner-ID",
                        value=comp.google_drive_folder_id,
                    ).classes(C_INPUT)

                def _n8n_status_text() -> str:
                    if not bool(n8n_enabled.value):
                        return "Status: deaktiviert"
                    if not (n8n_webhook_url_prod.value or "").strip():
                        if (n8n_webhook_url_test.value or "").strip():
                            return "Status: aktiv, aber keine Production-Webhook-URL gesetzt (Test vorhanden)"
                        return "Status: aktiv, aber keine Production-Webhook-URL gesetzt"
                    if not (n8n_secret.value or "").strip():
                        return "Status: aktiv, aber kein Secret gesetzt"
                    return "Status: aktiv und bereit"

                n8n_status = ui.label(_n8n_status_text()).classes("text-xs text-slate-500")

                def _update_n8n_status() -> None:
                    n8n_status.set_text(_n8n_status_text())

                n8n_webhook_url_test.on("change", lambda _: _update_n8n_status())
                n8n_webhook_url_prod.on("change", lambda _: _update_n8n_status())
                n8n_secret.on("change", lambda _: _update_n8n_status())
                n8n_enabled.on("change", lambda _: _update_n8n_status())

                def _copy_n8n_secret() -> None:
                    secret_value = (n8n_secret.value or "").strip()
                    if not secret_value:
                        ui.notify("n8n Secret fehlt.", color="orange")
                        return
                    ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(secret_value)})")
                    ui.notify("Secret kopiert.", color="green")

                def _test_n8n_webhook() -> None:
                    if not bool(n8n_enabled.value):
                        ui.notify("n8n ist deaktiviert.", color="orange")
                        n8n_status.set_text(_n8n_status_text())
                        ui.run_javascript("console.log('n8n_test_debug', {step: 'n8n_disabled'});")
                        return
                    webhook_url = (n8n_webhook_url_test.value or "").strip()
                    secret_value = (n8n_secret.value or "").strip()
                    if not webhook_url or not secret_value:
                        ui.notify("Test-Webhook-URL oder Secret fehlt.", color="orange")
                        n8n_status.set_text(_n8n_status_text())
                        ui.run_javascript(
                            f"console.log('n8n_test_debug', {json.dumps({'step': 'missing_webhook_or_secret', 'has_webhook_url': bool(webhook_url), 'has_secret': bool(secret_value)})});"
                        )
                        return
                    ui.run_javascript(
                        f"console.log('n8n_test_debug', {json.dumps({'step': 'sending_test', 'webhook_url': webhook_url})});"
                    )
                    try:
                        post_to_n8n(
                            webhook_url=webhook_url,
                            secret=secret_value,
                            event="test",
                            company_id=int(comp.id or 0),
                            data={"message": "Webhook-Test", "ts": int(time.time())},
                        )
                    except httpx.HTTPStatusError as exc:
                        status_code = exc.response.status_code if exc.response else None
                        ui.run_javascript(
                            f"console.log('n8n_test_debug', {json.dumps({'step': 'test_failed_status', 'status_code': status_code})});"
                        )
                        if status_code == 404:
                            ui.notify(
                                "Webhook-Test fehlgeschlagen: 404. Bitte die Test-Webhook-URL aus n8n verwenden.",
                                color="orange",
                            )
                        elif status_code == 405:
                            ui.notify(
                                "Webhook-Test fehlgeschlagen: n8n akzeptiert keine POST-Requests. "
                                "Bitte im n8n-Webhook die Methode auf POST stellen.",
                                color="orange",
                            )
                        else:
                            ui.notify(f"Webhook-Test fehlgeschlagen: {exc}", color="orange")
                        n8n_status.set_text("Status: Test fehlgeschlagen")
                        return
                    except Exception as exc:
                        ui.notify(f"Webhook-Test fehlgeschlagen: {exc}", color="orange")
                        n8n_status.set_text("Status: Test fehlgeschlagen")
                        ui.run_javascript(
                            f"console.log('n8n_test_debug', {json.dumps({'step': 'test_failed_exception', 'error': str(exc)})});"
                        )
                        return
                    ui.notify("Webhook-Test gesendet.", color="green")
                    n8n_status.set_text("Status: Test gesendet")
                    ui.run_javascript("console.log('n8n_test_debug', {step: 'test_success'});")

                with ui.row().classes("w-full gap-2 flex-wrap mt-2"):
                    ui.button(
                        "Secret generieren",
                        on_click=lambda: (
                            n8n_secret.set_value(secrets.token_urlsafe(32)),
                            ui.notify("Secret generiert", color="green"),
                        ),
                    ).classes(C_BTN_SEC)
                    ui.button("Secret kopieren", on_click=_copy_n8n_secret).classes(C_BTN_SEC)
                    ui.button("Webhook testen", on_click=_test_n8n_webhook).classes(C_BTN_SEC)

            with ui.expansion("Account").classes("w-full"):
                with ui.element("div").classes("space-y-4 pt-2"):
                    current_pw = ui.input("Aktuelles Passwort").props("type=password").classes(C_INPUT)
                    new_pw = ui.input("Neues Passwort").props("type=password").classes(C_INPUT)
                    confirm_pw = ui.input("Neues Passwort bestätigen").props("type=password").classes(C_INPUT)

                def _change_password() -> None:
                    if not (new_pw.value or ""):
                        ui.notify("Neues Passwort fehlt.", color="orange")
                        return
                    if (new_pw.value or "") != (confirm_pw.value or ""):
                        ui.notify("Passwörter stimmen nicht überein.", color="orange")
                        return

                    from services.account import change_password

                    try:
                        change_password(user_id, current_pw.value or "", new_pw.value or "")
                    except Exception as exc:
                        ui.notify(f"Passwort ändern fehlgeschlagen: {exc}", color="red")
                        return

                    ui.notify("Passwort geändert", color="green")
                    current_pw.set_value("")
                    new_pw.set_value("")
                    confirm_pw.set_value("")

                with ui.row().classes("w-full gap-2 flex-wrap mt-2"):
                    ui.button("Passwort ändern", on_click=_change_password).classes(C_BTN_SEC)

                ui.separator().classes("my-4")

                def _open_delete_account_dialog() -> None:
                    dlg = ui.dialog()
                    with dlg, ui.card().classes("p-5 w-[560px]"):
                        ui.label("Account löschen").classes("font-semibold")
                        ui.label("Das löscht deinen Account und alle Unternehmen inklusive Daten und Uploads.").classes(
                            "text-sm text-slate-600"
                        )
                        confirm = ui.input('Tippe "DELETE" zur Bestätigung').classes(C_INPUT)

                        def _do_delete_account() -> None:
                            if (confirm.value or "").strip().upper() != "DELETE":
                                ui.notify('Bitte "DELETE" tippen.', color="orange")
                                return

                            from services.account import delete_account

                            try:
                                delete_account(user_id)
                            except Exception as exc:
                                ui.notify(f"Account löschen fehlgeschlagen: {exc}", color="red")
                                return

                            clear_auth_session()
                            app.storage.user.clear()
                            dlg.close()
                            ui.notify("Account gelöscht", color="green")
                            ui.navigate.to("/signup")

                        with ui.row().classes("justify-end gap-2 w-full mt-3"):
                            ui.button("Abbrechen", on_click=dlg.close).classes(C_BTN_SEC)
                            ui.button("Account löschen", on_click=_do_delete_account).classes(C_BTN_PRIM)

                    dlg.open()

                ui.button("Account löschen", on_click=_open_delete_account_dialog).classes(C_BTN_PRIM)

    # Wire address autocomplete
    use_address_autocomplete(street, plz, city, country, street_dropdown)

    def save() -> None:
        patch = {
            "name": name.value or "",
            "first_name": first_name.value or "",
            "last_name": last_name.value or "",
            "street": street.value or "",
            "postal_code": plz.value or "",
            "city": city.value or "",
            "country": country.value or "",
            "email": email.value or "",
            "phone": phone.value or "",
            "iban": iban.value or "",
            "bic": bic.value or "",
            "bank_name": bank_name.value or "",
            "tax_id": tax.value or "",
            "vat_id": vat.value or "",
            "business_type": business_type.value or "Einzelunternehmen",
            "is_small_business": bool(is_small_business.value),
            "next_invoice_nr": int(next_invoice_nr.value or 0) or 1,
            "invoice_number_template": invoice_number_template.value or "{seq}",
            "invoice_filename_template": invoice_filename_template.value or "rechnung_{nr}",
            "default_sender_email": default_sender_email.value or "",
            "smtp_server": smtp_server.value or "",
            "smtp_port": int(smtp_port.value or 0) or 465,
            "smtp_user": smtp_user.value or "",
            "smtp_password": smtp_password.value or "",
            "n8n_webhook_url": n8n_webhook_url_prod.value or "",
            "n8n_webhook_url_test": n8n_webhook_url_test.value or "",
            "n8n_webhook_url_prod": n8n_webhook_url_prod.value or "",
            "n8n_secret": n8n_secret.value or "",
            "n8n_enabled": bool(n8n_enabled.value),
            "google_drive_folder_id": google_drive_folder_id.value or "",
        }

        try:
            update_company(user_id, int(comp.id or 0), patch)
        except Exception as exc:
            ui.notify(f"Speichern fehlgeschlagen: {exc}", color="red")
            return

        ui.notify("Gespeichert", color="green")

    with ui.element("div").classes("w-full max-w-5xl mx-auto mt-4 flex justify-end"):
        ui.button("Speichern", on_click=save).classes(C_BTN_PRIM)
