# app/pages/settings.py
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime

import httpx
from nicegui import app, ui
from sqlmodel import select

from data import Document
from services.documents import (
    build_display_title,
    build_download_filename,
    normalize_keywords,
    safe_filename,
)
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
from services.email import send_email
from services.iban import lookup_bank_from_iban
from services.blob_storage import blob_storage, build_document_key
from services.storage import company_logo_path, delete_company_dirs, ensure_company_dirs


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

    ui.label("Einstellungen").classes(C_PAGE_TITLE + " mb-6")

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

            ui.button("Neues Unternehmen", on_click=_open_create_dialog).classes(C_BTN_SEC)
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
        # Two column top
        with ui.grid(columns=2).classes("w-full gap-4"):
            with ui.card().classes(C_CARD + " p-6 w-full"):
                ui.label("Person / Kontakt").classes("text-sm font-semibold text-slate-700")
                with ui.grid(columns=2).classes("w-full gap-4"):
                    name = ui.input("Firma", value=comp.name).classes(C_INPUT)
                    first_name = ui.input("Vorname", value=comp.first_name).classes(C_INPUT)
                    last_name = ui.input("Nachname", value=comp.last_name).classes(C_INPUT)
                    email = ui.input("Email", value=comp.email).classes(C_INPUT)
                    phone = ui.input("Telefon", value=comp.phone).classes(C_INPUT)

            with ui.card().classes(C_CARD + " p-6 w-full"):
                ui.label("Adresse").classes("text-sm font-semibold text-slate-700")
                with ui.grid(columns=2).classes("w-full gap-4"):
                    with ui.element("div").classes("relative w-full"):
                        street = ui.input("Straße", value=comp.street).classes(C_INPUT)
                        street_dropdown = ui.element("div").classes(
                            "absolute left-0 right-0 mt-1 z-10 bg-white border border-slate-200 rounded-lg shadow-sm"
                        )
                    plz = ui.input("PLZ", value=comp.postal_code).classes(C_INPUT)
                    city = ui.input("Ort", value=comp.city).classes(C_INPUT)
                    country = ui.input("Land", value=comp.country or "DE").classes(C_INPUT)

            with ui.card().classes(C_CARD + " p-6 w-full"):
                ui.label("Logo Upload").classes("text-sm font-semibold text-slate-700")

                def on_up(e) -> None:
                    if not comp.id:
                        ui.notify("Kein aktives Unternehmen.", color="red")
                        return
                    cid = int(comp.id)
                    ensure_company_dirs(cid)

                    # NiceGUI v3: UploadEventArguments hat "file" (nicht "content")
                    # file.save(path) speichert direkt auf Disk
                    try:
                        e.file.save(company_logo_path(cid))
                    except Exception as exc:
                        ui.notify(f"Upload fehlgeschlagen: {exc}", color="red")
                        return

                    ui.notify("Hochgeladen", color="green")

                ui.upload(on_upload=on_up, auto_upload=True, label="Bild wählen").props("flat dense").classes("w-full")

            with ui.card().classes(C_CARD + " p-6 w-full"):
                ui.label("Dokument-Storage (Test)").classes("text-sm font-semibold text-slate-700")
                doc_id_input = ui.input("Dokument-ID", placeholder="z.B. 12345").classes(C_INPUT)
                key_output = ui.input("Letzter Key", value="").props("readonly").classes(C_INPUT)

                def _read_upload_bytes(upload_file) -> bytes:
                    temp_file = tempfile.NamedTemporaryFile(delete=False)
                    temp_path = Path(temp_file.name)
                    temp_file.close()
                    try:
                        upload_file.save(str(temp_path))
                        return temp_path.read_bytes()
                    finally:
                        if temp_path.exists():
                            temp_path.unlink()

                def _resolve_key() -> str | None:
                    key = (key_output.value or "").strip()
                    if not key:
                        ui.notify("Kein Key vorhanden.", color="red")
                        return None
                    return key

                def on_doc_upload(e) -> None:
                    if not comp.id:
                        ui.notify("Kein aktives Unternehmen.", color="red")
                        return
                    cid = int(comp.id)
                    doc_id = (doc_id_input.value or "").strip() or str(int(time.time()))
                    key = build_document_key(cid, doc_id, e.file.name)
                    mime = getattr(e.file, "content_type", None) or "application/octet-stream"
                    try:
                        data = _read_upload_bytes(e.file)
                        blob_storage().put_bytes(key, data, mime)
                    except Exception as exc:
                        ui.notify(f"Upload fehlgeschlagen: {exc}", color="red")
                        return
                    doc_id_input.set_value(doc_id)
                    key_output.set_value(key)
                    ui.notify("Dokument gespeichert", color="green")

                def on_doc_exists() -> None:
                    key = _resolve_key()
                    if not key:
                        return
                    try:
                        exists = blob_storage().exists(key)
                    except Exception as exc:
                        ui.notify(f"Prüfung fehlgeschlagen: {exc}", color="red")
                        return
                    ui.notify("Dokument vorhanden" if exists else "Dokument nicht gefunden", color="green")

                def on_doc_load() -> None:
                    key = _resolve_key()
                    if not key:
                        return
                    try:
                        data = blob_storage().get_bytes(key)
                    except Exception as exc:
                        ui.notify(f"Laden fehlgeschlagen: {exc}", color="red")
                        return
                    ui.notify(f"Bytes geladen: {len(data)}", color="green")

                def on_doc_delete() -> None:
                    key = _resolve_key()
                    if not key:
                        return
                    try:
                        blob_storage().delete(key)
                    except Exception as exc:
                        ui.notify(f"Löschen fehlgeschlagen: {exc}", color="red")
                        return
                    ui.notify("Dokument gelöscht", color="green")

                ui.upload(on_upload=on_doc_upload, auto_upload=True, label="Datei wählen").props("flat dense").classes(
                    "w-full"
                )
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    ui.button("Vorhanden?", on_click=on_doc_exists).classes(C_BTN_SEC)
                    ui.button("Bytes prüfen", on_click=on_doc_load).classes(C_BTN_SEC)
                    ui.button("Löschen", on_click=on_doc_delete).classes(C_BTN_SEC)

            with ui.card().classes(C_CARD + " p-6 w-full"):
                ui.label("Business Meta").classes("text-sm font-semibold text-slate-700")

                business_type_options = [
                    "Einzelunternehmen",
                    "Freelancer",
                    "GbR/Partnership",
                    "GmbH",
                    "UG",
                    "Nonprofit",
                    "Other",
                ]

                with ui.grid(columns=2).classes("w-full gap-4"):
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

        # Single column blocks
        with ui.card().classes(C_CARD + " p-6 w-full mt-4"):
            ui.label("Rechnungsnummern").classes("text-sm font-semibold text-slate-700")
            with ui.grid(columns=2).classes("w-full gap-4"):
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

        with ui.card().classes(C_CARD + " p-6 w-full mt-4"):
            ui.label("Integrationen").classes("text-sm font-semibold text-slate-700")

            ui.label("SMTP (für Mails aus der App)").classes("text-sm font-semibold text-slate-700 mt-2")
            ui.label("Port 465 nutzt SSL. Andere Ports nutzen STARTTLS.").classes("text-sm text-slate-500")

            with ui.grid(columns=2).classes("w-full gap-4"):
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

            with ui.row().classes("w-full gap-2 flex-wrap mt-2"):
                test_to = ui.input("Test Empfänger", placeholder="z.B. deine private Adresse").classes(C_INPUT)

                def _send_test_mail() -> None:
                    cfg = {
                        "host": (smtp_server.value or "").strip(),
                        "port": int(smtp_port.value or 0),
                        "user": (smtp_user.value or "").strip(),
                        "password": smtp_password.value or "",
                        "sender": (default_sender_email.value or smtp_user.value or "").strip(),
                    }
                    try:
                        ok = send_email(
                            to=(test_to.value or "").strip(),
                            subject="FixundFertig SMTP Test",
                            text="SMTP Test erfolgreich. Wenn du das liest, passt deine SMTP Konfiguration.",
                            smtp_config=cfg,
                        )
                    except Exception as exc:
                        ui.notify(f"SMTP Test fehlgeschlagen: {exc}", color="red")
                        return

                    ui.notify(
                        "SMTP Test Mail gesendet" if ok else "SMTP Config fehlt",
                        color="green" if ok else "orange",
                    )

                ui.button("Test Mail senden", on_click=_send_test_mail).classes(C_BTN_SEC)

            ui.separator().classes("my-4")

            ui.label("n8n").classes("text-sm font-semibold text-slate-700")
            ui.label("Webhooks für Automationen.").classes("text-sm text-slate-500")

            with ui.grid(columns=2).classes("w-full gap-4"):
                n8n_webhook_url = ui.input("n8n Webhook URL", value=comp.n8n_webhook_url).classes(C_INPUT)
                n8n_secret = ui.input("n8n Secret", value=comp.n8n_secret).classes(C_INPUT).props("type=password")
                n8n_enabled = ui.switch("n8n aktivieren", value=bool(comp.n8n_enabled)).props("dense color=grey-8")
                google_drive_folder_id = ui.input(
                    "Google Drive Ordner-ID",
                    value=comp.google_drive_folder_id,
                ).classes(C_INPUT)

            with ui.row().classes("w-full gap-2 flex-wrap mt-2"):
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
                            company_id=int(comp.id or 0),
                            data={"name": name.value, "email": email.value},
                        )
                    except Exception as exc:
                        ui.notify(f"n8n Fehler: {exc}", color="red")
                        return
                    ui.notify(f"n8n OK. HTTP {resp.status_code}", color="green")

                ui.button("Webhook testen", on_click=test_n8n_webhook).classes(C_BTN_SEC)

                def test_n8n_ingest() -> None:
                    secret_value = (n8n_secret.value or "").strip()
                    if not secret_value:
                        ui.notify("n8n Secret fehlt.", color="orange")
                        return
                    if not bool(n8n_enabled.value):
                        ui.notify("n8n ist deaktiviert.", color="orange")
                        return

                    base_url = os.environ.get("APP_BASE_URL", "http://localhost:8080").rstrip("/")
                    event_id = secrets.token_urlsafe(12)
                    payload = {
                        "event_id": event_id,
                        "company_id": int(comp.id or 0),
                        "file_name": "n8n-test.txt",
                        "file_base64": base64.b64encode(b"FixundFertig n8n Test").decode("utf-8"),
                        "extracted": {
                            "suggested_title": "n8n Testdokument",
                            "summary": "Test fuer den n8n Webhook Import.",
                            "vendor": "n8n",
                            "keywords": ["test", "n8n", "ingest"],
                        },
                    }
                    raw_body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    timestamp = str(int(time.time()))
                    signed_payload = f"{timestamp}.".encode("utf-8") + raw_body
                    signature = hmac.new(secret_value.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
                    headers = {
                        "Content-Type": "application/json",
                        "X-Timestamp": timestamp,
                        "X-Signature": signature,
                    }
                    try:
                        resp = httpx.post(
                            f"{base_url}/api/webhooks/n8n/ingest",
                            content=raw_body,
                            headers=headers,
                            timeout=8.0,
                        )
                    except Exception as exc:
                        ui.notify(f"Ingest fehlgeschlagen: {exc}", color="red")
                        return

                    if resp.status_code >= 400:
                        ui.notify(f"Ingest Fehler: HTTP {resp.status_code}", color="red")
                        return
                    ui.notify("Ingest OK. Dokument angelegt.", color="green")

                ui.button("Ingest testen", on_click=test_n8n_ingest).classes(C_BTN_SEC)

                def test_n8n_upload() -> None:
                    secret_value = (n8n_secret.value or "").strip()
                    if not secret_value:
                        ui.notify("n8n Secret fehlt.", color="orange")
                        return
                    if not bool(n8n_enabled.value):
                        ui.notify("n8n ist deaktiviert.", color="orange")
                        return

                    base_url = os.environ.get("APP_BASE_URL", "http://localhost:8080").rstrip("/")
                    payload = {
                        "title": "n8n Upload Test",
                        "extracted": {
                            "vendor": "n8n",
                            "doc_date": datetime.now().date().isoformat(),
                            "amount_total": 12.34,
                            "currency": "EUR",
                        },
                    }
                    data = {"payload_json": json.dumps(payload, ensure_ascii=False)}
                    files = {
                        "file": (
                            "n8n-upload-test.txt",
                            b"FixundFertig n8n Upload Test",
                            "text/plain",
                        )
                    }
                    headers = {
                        "X-Company-Id": str(int(comp.id or 0)),
                        "X-N8N-Secret": secret_value,
                    }
                    try:
                        resp = httpx.post(
                            f"{base_url}/api/webhooks/n8n/upload",
                            data=data,
                            files=files,
                            headers=headers,
                            timeout=8.0,
                        )
                    except Exception as exc:
                        ui.notify(f"Upload fehlgeschlagen: {exc}", color="red")
                        return

                    if resp.status_code >= 400:
                        ui.notify(f"Upload Fehler: HTTP {resp.status_code}", color="red")
                        return
                    ui.notify("Upload OK. Dokument gespeichert.", color="green")

                ui.button("Upload testen", on_click=test_n8n_upload).classes(C_BTN_SEC)

        with ui.card().classes(C_CARD + " p-6 w-full mt-4"):
            ui.label("Dokumente").classes("text-sm font-semibold text-slate-700")
            ui.label("Test-Hook für Metadaten").classes("text-sm text-slate-500")

            with ui.grid(columns=2).classes("w-full gap-4"):
                doc_vendor = ui.input("Lieferant", placeholder="z.B. ACME GmbH").classes(C_INPUT)
                doc_date = ui.input("Belegdatum", placeholder="YYYY-MM-DD").classes(C_INPUT)
                doc_amount = ui.number("Betrag", step=0.01).classes(C_INPUT)
                doc_currency = ui.input("Währung", value="EUR").classes(C_INPUT)
                doc_filename = ui.input("Originaldatei", placeholder="scan.pdf").classes(C_INPUT)
                doc_keywords = ui.input("Keywords (kommagetrennt)", placeholder="steuer, hardware").classes(C_INPUT)

            preview = ui.label("").classes("text-sm text-slate-500 mt-2")
            count_label = ui.label("").classes("text-sm text-slate-500")

            def _refresh_document_status() -> None:
                cid = int(comp.id or 0)
                if not cid:
                    count_label.text = "Kein aktives Unternehmen."
                    preview.text = ""
                    return
                with get_session() as s:
                    docs = list(
                        s.exec(select(Document).where(Document.company_id == cid).order_by(Document.created_at.desc()))
                    )
                count_label.text = f"{len(docs)} Dokument(e) gespeichert."
                if docs:
                    latest = docs[0]
                    preview.text = f"Letztes: {latest.title or 'Dokument'}"
                else:
                    preview.text = "Noch keine Dokumente."

            def _create_document() -> None:
                cid = int(comp.id or 0)
                if not cid:
                    ui.notify("Kein aktives Unternehmen.", color="red")
                    return
                amount_value = doc_amount.value
                amount = float(amount_value) if amount_value not in (None, "") else None
                title = build_display_title(
                    doc_vendor.value or "",
                    doc_date.value or "",
                    amount,
                    doc_currency.value or "",
                    doc_filename.value or "",
                )
                storage_key = f"{safe_filename(doc_filename.value or title)}-{secrets.token_hex(4)}"
                keywords_json = normalize_keywords(doc_keywords.value or "")
                original_name = doc_filename.value or title
                safe_name = safe_filename(original_name)
                document = Document(
                    company_id=cid,
                    filename=safe_name,
                    original_filename=original_name,
                    mime_type="application/pdf",
                    size_bytes=0,
                    source="manual",
                    doc_type="pdf",
                    storage_key=storage_key,
                    storage_path="",
                    mime="application/pdf",
                    size=0,
                    sha256="",
                    title=title,
                    description="",
                    vendor=doc_vendor.value or "",
                    doc_date=(doc_date.value or "").strip() or None,
                    amount_total=amount,
                    currency=(doc_currency.value or "").strip() or None,
                    keywords_json=keywords_json,
                )
                with get_session() as s:
                    s.add(document)
                    s.commit()
                download_name = build_download_filename(title, document.mime)
                ui.notify(f"Dokument gespeichert: {download_name}", color="green")
                _refresh_document_status()

            with ui.row().classes("w-full gap-2 flex-wrap mt-2"):
                ui.button("Beispieldokument speichern", on_click=_create_document).classes(C_BTN_SEC)

            _refresh_document_status()

        with ui.card().classes(C_CARD + " p-6 w-full mt-4"):
            ui.label("Account").classes("text-sm font-semibold text-slate-700")

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
            "n8n_webhook_url": n8n_webhook_url.value or "",
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
