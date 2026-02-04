from __future__ import annotations

import base64
import csv
import io
import logging
import re
import mimetypes
import os
import json
import tempfile
import zipfile
import logging
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException

from ._shared import *
from styles import C_BADGE_BLUE, C_BADGE_GREEN, C_BADGE_YELLOW
from data import Document, DocumentMeta, WebhookEvent
from sqlmodel import delete
from data import WebhookEvent
import httpx

from integrations.n8n_client import post_to_n8n
from services.blob_storage import blob_storage
from services.documents import (
    backfill_document_fields,
    document_size_bytes,
    document_matches_filters,
    resolve_document_meta_values,
    resolve_document_path,
    validate_document_upload,
)

logger = logging.getLogger(__name__)


def render_documents(session, comp: Company) -> None:
    state = {
        "search": "",
        "period": "last_month",
        "year": str(datetime.now().year),
        "date_from": "",
        "date_to": "",
    }
    debug_enabled = os.getenv("FF_DEBUG") == "1"
    upload_status = None
    debug_client_logs = True

    def _log_client_debug(payload: dict) -> None:
        if not debug_client_logs:
            return
        ui.run_javascript(f"console.log('n8n_upload_debug', {json.dumps(payload)});")

    def _load_documents() -> list[Document]:
        session.expire_all()
        return session.exec(
            select(Document).where(Document.company_id == int(comp.id or 0))
        ).all()

    def _filter_documents(items: list[Document]) -> list[Document]:
        date_from, date_to = _resolved_date_range()
        return [
            doc
            for doc in items
            if document_matches_filters(
                doc,
                query=state["search"],
                source="",
                doc_type="",
                date_from=date_from,
                date_to=date_to,
            )
        ]

    def _doc_created_at(doc: Document) -> datetime:
        created_at = doc.created_at
        if isinstance(created_at, datetime):
            return created_at
        try:
            return datetime.fromisoformat(str(created_at))
        except Exception:
            return datetime.min

    def _document_invoice_date(doc: Document) -> str:
        value = getattr(doc, "invoice_date", None)
        return value or ""

    def _document_display_date(doc: Document) -> str:
        doc_date = (getattr(doc, "doc_date", None) or "").strip()
        invoice_date = _document_invoice_date(doc).strip()
        if doc_date:
            return doc_date
        if invoice_date:
            return invoice_date
        created_at = _doc_created_at(doc)
        if created_at != datetime.min:
            return created_at.strftime("%Y-%m-%d")
        return ""

    def _parse_keywords(value: object) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if not isinstance(value, str):
            value = str(value)
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = value
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        if isinstance(parsed, str):
            return [piece.strip() for piece in parsed.split(",") if piece.strip()]
        return [str(parsed).strip()] if str(parsed).strip() else []

    def _format_keywords(value: str | None) -> str:
        items = _parse_keywords(value or "")
        return ", ".join(items) if items else "-"

    def _sort_documents(items: list[Document]) -> list[Document]:
        return sorted(items, key=_doc_created_at, reverse=True)

    def _resolved_date_range() -> tuple[str, str]:
        period = state["period"]
        if period == "custom":
            return state["date_from"], state["date_to"]

        today = datetime.now().date()
        if period == "year":
            try:
                year = int(state["year"])
            except (TypeError, ValueError):
                year = today.year
            start = datetime(year, 1, 1).date()
            end = datetime(year, 12, 31).date()
            return start.isoformat(), end.isoformat()

        if period == "last_week":
            start = today - timedelta(days=7)
            return start.isoformat(), today.isoformat()

        if period == "last_3_months":
            start = today - timedelta(days=90)
            return start.isoformat(), today.isoformat()

        first_of_month = today.replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start.isoformat(), last_month_end.isoformat()

    def _year_options(items: list[Document]) -> dict[str, str]:
        years = {
            str(_doc_created_at(doc).year)
            for doc in items
            if _doc_created_at(doc) != datetime.min
        }
        if not years:
            years = {str(datetime.now().year)}
        options = {year: year for year in sorted(years, reverse=True)}
        return options

    def _safe_export_filename(name: str) -> str:
        cleaned = (name or "").strip() or "document"
        cleaned = os.path.basename(cleaned)
        cleaned = cleaned.replace("/", "_").replace("\\", "_").replace(":", "_")
        return cleaned or "document"

    @ui_handler("documents.export")
    def _export_documents(selected_ids: set[int]) -> None:
        if not selected_ids:
            ui.notify("Bitte Dokumente auswählen.", color="orange")
            return
        items = [doc for doc in _filter_documents(_load_documents()) if int(doc.id or 0) in selected_ids]
        if not items:
            ui.notify("Keine Dokumente zum Export.", color="orange")
            return
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer, delimiter=";", lineterminator="\n")
        writer.writerow(
            [
                "Datei",
                "Datum",
                "Dateigröße (Bytes)",
                "MIME",
                "Belegnummer",
                "Vendor",
                "Tags",
                "Betrag",
                "Netto",
                "Steuer",
                "Summary",
            ]
        )
        for doc in items:
            doc_date = _document_display_date(doc)
            amount_total, amount_net, amount_tax = _resolve_amounts(doc)
            filename = doc.original_filename or doc.filename or doc.title or "Dokument"
            mime_type = doc.mime_type or doc.mime or ""
            size_bytes = doc.size_bytes or doc.size or ""
            summary = doc.description or doc.title or doc.doc_type or ""
            writer.writerow(
                [
                    filename,
                    doc_date,
                    size_bytes,
                    mime_type,
                    doc.doc_number or "",
                    doc.vendor or "",
                    _format_keywords(doc.keywords_json),
                    f"{amount_total:.2f}" if amount_total is not None else "",
                    f"{amount_net:.2f}" if amount_net is not None else "",
                    f"{amount_tax:.2f}" if amount_tax is not None else "",
                    summary,
                ]
            )

        date_stamp = datetime.now().strftime("%Y%m%d")
        zip_name = f"documents_{date_stamp}.zip"
        temp_dir = tempfile.mkdtemp(prefix="documents_export_")
        zip_path = os.path.join(temp_dir, zip_name)
        missing_files = 0

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"documents_{date_stamp}.csv", csv_buffer.getvalue())
            storage = blob_storage()
            for doc in items:
                storage_key = getattr(doc, "storage_key", "") or ""
                storage_path = resolve_document_path(doc.storage_path)
                data = b""
                if storage_key and (storage_key.startswith("companies/") or storage_key.startswith("documents/")):
                    if storage.exists(storage_key):
                        data = storage.get_bytes(storage_key)
                elif storage_path and os.path.exists(storage_path):
                    try:
                        with open(storage_path, "rb") as file:
                            data = file.read()
                    except OSError:
                        data = b""

                if not data:
                    missing_files += 1
                    continue

                filename = _safe_export_filename(doc.original_filename or doc.title or f"dokument_{doc.id}")
                zf.writestr(f"{int(doc.id or 0)}_{filename}", data)

        ui.download(zip_path)
        if missing_files:
            ui.notify(f"{missing_files} Dateien fehlten im Export.", color="orange")
        ui.notify("ZIP-Export bereit.", color="green")

    async def _read_upload_bytes(upload_file) -> bytes:
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_path = Path(temp_file.name)
        temp_file.close()
        try:
            await upload_file.save(str(temp_path))
            return temp_path.read_bytes()
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @ui_handler("documents.upload")
    async def _handle_upload(event) -> None:
        action = "document_upload"
        document_id = None
        storage_key = None
        filename = getattr(event, "name", "") or getattr(event.file, "name", "") or "upload"
        try:
            _log_client_debug({"step": "upload_clicked", "filename": filename})
            if not comp.id:
                ui.notify("Kein aktives Unternehmen.", color="red")
                _log_client_debug({"step": "missing_company"})
                return
            if not bool(comp.n8n_enabled):
                ui.notify("n8n ist deaktiviert. Bitte in den Settings aktivieren.", color="orange")
                if upload_status:
                    upload_status.set_text("Status: n8n deaktiviert")
                _log_client_debug({"step": "n8n_disabled"})
                return
            webhook_url = (comp.n8n_webhook_url_prod or comp.n8n_webhook_url or "").strip()
            test_webhook_url = (comp.n8n_webhook_url_test or "").strip()
            secret_value = (comp.n8n_secret or "").strip()
            if not webhook_url and test_webhook_url:
                webhook_url = test_webhook_url
                ui.notify(
                    "Hinweis: Production-Webhook-URL fehlt. Upload nutzt die Test-Webhook-URL.",
                    color="orange",
                )
                _log_client_debug({"step": "fallback_to_test_url"})
            if not webhook_url or not secret_value:
                ui.notify("n8n Webhook-URL oder Secret fehlt.", color="orange")
                if upload_status:
                    upload_status.set_text("Status: Webhook-URL oder Secret fehlt")
                _log_client_debug(
                    {
                        "step": "missing_webhook_or_secret",
                        "has_webhook_url": bool(webhook_url),
                        "has_secret": bool(secret_value),
                    }
                )
                return

            try:
                _log_client_debug({"step": "reading_file", "filename": filename})
                data = await _read_upload_bytes(event.file)
                size_bytes = len(data)
                _log_client_debug({"step": "file_read_complete", "size_bytes": size_bytes})
                _log_client_debug({"step": "validating_file", "size_bytes": size_bytes})
                validate_document_upload(filename, size_bytes)
                _log_client_debug({"step": "validation_ok"})
            except HTTPException:
                logger.exception(
                    "ACTION_FAILED",
                    extra=_build_action_context(
                        action,
                        filename=filename,
                    ),
                )
                ui.notify("Fehler beim Upload (Dokument-ID: unbekannt)", color="red")
                _log_client_debug({"step": "validation_failed", "filename": filename})
                return

            if upload_status:
                upload_status.set_text("Status: Datei geprüft")

            mime_type = (
                getattr(event, "type", "")
                or getattr(event.file, "content_type", "")
                or mimetypes.guess_type(filename)[0]
                or ""
            )
            _log_client_debug({"step": "mime_resolved", "mime_type": mime_type})
            file_b64 = base64.b64encode(data).decode("utf-8")
            _log_client_debug({"step": "base64_encoded", "size_b64": len(file_b64)})
            file_payload = f"data:{mime_type};base64,{file_b64}" if mime_type else file_b64
            _log_client_debug({"step": "payload_ready", "payload_prefix": file_payload[:32]})
            _log_client_debug({"step": "pre_send_stage"})

            logger.info(
                "ACTION_SUCCESS",
                extra=_build_action_context(
                    action,
                    document_id=document_id,
                    filename=filename,
                    storage_key=storage_key,
                    storage_path=storage_key,
                ),
            )
            _log_client_debug({"step": "action_logged"})
            if upload_status:
                upload_status.set_text("Status: Sende an n8n...")
            _log_client_debug({"step": "status_set_sending"})
            _log_client_debug(
                {
                    "step": "sending_to_n8n",
                    "webhook_url": webhook_url,
                    "filename": filename,
                    "mime_type": mime_type,
                    "size_bytes": size_bytes,
                }
            )
            try:
                _log_client_debug({"step": "post_call_started"})
                post_to_n8n(
                    webhook_url=webhook_url,
                    secret=secret_value,
                    event="document_upload",
                    company_id=int(comp.id),
                    data={
                        "file_name": filename,
                        "mime_type": mime_type,
                        "size_bytes": size_bytes,
                        "file_base64": file_payload,
                    },
                )
                _log_client_debug({"step": "post_call_finished"})
                if upload_status:
                    upload_status.set_text("Status: Gesendet. Warte auf n8n-Ingest...")
                ui.notify("Datei an n8n gesendet.", color="green")
                _log_client_debug({"step": "send_success"})
            except httpx.HTTPStatusError as exc:
                logger.exception(
                    "N8N_WEBHOOK_FAILED",
                    extra=_build_action_context(
                        action,
                        document_id=document_id,
                        filename=filename,
                        storage_key=storage_key,
                        storage_path=storage_key,
                    ),
                )
                if upload_status:
                    upload_status.set_text("Status: Versand fehlgeschlagen")
                status_code = exc.response.status_code if exc.response else None
                _log_client_debug({"step": "send_failed_status", "status_code": status_code})
                if status_code == 404:
                    ui.notify(
                        "n8n Versand fehlgeschlagen: 404. Bitte die Production-Webhook-URL (/webhook/) verwenden.",
                        color="orange",
                    )
                elif status_code == 405:
                    ui.notify(
                        "n8n Versand fehlgeschlagen: Webhook erwartet keine POST-Requests. "
                        "Bitte in n8n den Webhook auf POST stellen.",
                        color="orange",
                    )
                else:
                    ui.notify(f"n8n Versand fehlgeschlagen: {exc}", color="orange")
            except Exception as exc:
                logger.exception(
                    "N8N_WEBHOOK_FAILED",
                    extra=_build_action_context(
                        action,
                        document_id=document_id,
                        filename=filename,
                        storage_key=storage_key,
                        storage_path=storage_key,
                    ),
                )
                if upload_status:
                    upload_status.set_text("Status: Versand fehlgeschlagen")
                ui.notify(f"n8n Versand fehlgeschlagen: {exc}", color="orange")
                _log_client_debug({"step": "send_failed_exception", "error": str(exc)})
            render_list.refresh()
        except Exception:
            logger.exception(
                "ACTION_FAILED",
                extra=_build_action_context(
                    action,
                    document_id=document_id,
                    filename=filename,
                    storage_key=storage_key,
                    storage_path=storage_key,
                ),
            )
            doc_id_display = document_id if document_id is not None else "unbekannt"
            ui.notify(f"Fehler beim Upload (Dokument-ID: {doc_id_display})", color="red")
            _log_client_debug({"step": "upload_failed_unhandled"})
        finally:
            _log_client_debug({"step": "upload_handler_done"})

    def _trigger_upload() -> None:
        has_file = bool(getattr(upload_input, "value", None))
        _log_client_debug({"step": "send_button_clicked", "has_file": has_file})
        upload_input.run_method("upload")
        _log_client_debug({"step": "upload_method_called"})

    with ui.dialog() as upload_dialog:
        with ui.card().classes(C_CARD + " p-5 w-[480px] max-w-[92vw]"):
            ui.label("Upload an n8n").classes(C_SECTION_TITLE)
            ui.label("PDF, JPG oder PNG, maximal 15 MB.").classes("text-xs text-slate-500")
            ui.label("Die Datei wird an n8n gesendet und erscheint nach der Verarbeitung in der Liste.").classes(
                "text-xs text-slate-500 mb-2"
            )
            upload_input = ui.upload(
                on_upload=_handle_upload,
                auto_upload=False,
                label="Datei wählen",
            ).classes("w-full")
            upload_input.on("change", lambda _: _log_client_debug({"step": "file_selected"}))
            upload_status = ui.label("Status: bereit zum Senden").classes("text-xs text-slate-500 mt-1")
            with ui.row().classes("justify-end w-full mt-4 gap-2"):
                ui.button(
                    "Senden an n8n",
                    on_click=_trigger_upload,
                ).classes(C_BTN_PRIM)
                ui.button("Schließen", on_click=upload_dialog.close).classes(C_BTN_SEC)

    menu_state = {"visible": False, "x": 0, "y": 0, "doc_id": None, "open_url": ""}

    def _hide_context_menu() -> None:
        menu_state["visible"] = False
        menu_overlay.style("display: none")
        context_menu.style("display: none")

    def _show_context_menu(x: int, y: int, doc_id: int, open_url: str) -> None:
        menu_state["visible"] = True
        menu_state["x"] = x
        menu_state["y"] = y
        menu_state["doc_id"] = doc_id
        menu_state["open_url"] = open_url
        context_menu.style(f"display: block; top: {y}px; left: {x}px;")
        menu_overlay.style("display: block")

    def _preview_document() -> None:
        open_url = menu_state.get("open_url")
        _hide_context_menu()
        if open_url:
            ui.run_javascript(f"window.open('{open_url}', '_blank')")

    def _download_document() -> None:
        open_url = menu_state.get("open_url")
        _hide_context_menu()
        if open_url:
            ui.run_javascript(
                "const link=document.createElement('a');"
                f"link.href='{open_url}';"
                "link.download='';"
                "document.body.appendChild(link);"
                "link.click();"
                "link.remove();"
            )

    def _delete_document() -> None:
        doc_id = menu_state.get("doc_id")
        _hide_context_menu()
        if doc_id:
            _open_delete(int(doc_id))

    @ui_handler("documents.dialog.reset_events.open")
    def _open_reset_events() -> None:
        reset_dialog.open()

    @ui_handler("documents.dialog.delete_all.open")
    def _open_delete_all() -> None:
        delete_all_dialog.open()

    def _coerce_float(value: object) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _load_meta_map(doc_ids: list[int]) -> dict[int, DocumentMeta]:
        if not doc_ids:
            return {}
        metas = session.exec(
            select(DocumentMeta).where(DocumentMeta.document_id.in_(doc_ids))
        ).all()
        return {int(meta.document_id): meta for meta in metas if meta}

    def _resolve_amounts(doc: Document) -> tuple[float | None, float | None, float | None]:
        amount_total = _coerce_float(doc.amount_total)
        amount_net = _coerce_float(doc.amount_net)
        amount_tax = _coerce_float(doc.amount_tax)
        if amount_total is None:
            amount_total = _coerce_float(getattr(doc, "gross_amount", None))
        if amount_net is None:
            amount_net = _coerce_float(getattr(doc, "net_amount", None))
        if amount_tax is None:
            amount_tax = _coerce_float(getattr(doc, "tax_amount", None))
        if amount_tax is None and amount_total is not None and amount_net is not None:
            amount_tax = max(amount_total - amount_net, 0.0)
        return amount_total, amount_net, amount_tax

    def _format_json(value: str | None, *, redact_payload: bool = False) -> str:
        if not value:
            return ""
        try:
            parsed = json.loads(value)
        except Exception:
            return str(value)
        if redact_payload and isinstance(parsed, dict):
            for key in ("file_bytes", "file_base64", "content_base64", "data_base64", "raw_base64"):
                if key in parsed:
                    parsed[key] = "<redacted>"
        return json.dumps(parsed, ensure_ascii=False, indent=2)

    @ui.refreshable
    def render_filters():
        def _set_period(value: str) -> None:
            state["period"] = value
            render_filters.refresh()
            render_list.refresh()

        with ui.row().classes("w-full items-center justify-between gap-6 flex-wrap"):
            with ui.row().classes("items-center gap-4"):
                ui.label("Dokumente").classes("text-3xl font-bold text-slate-900")
                ui.button("Upload", icon="upload", on_click=upload_dialog.open).classes(C_BTN_PRIM)

            with ui.row().classes("items-center gap-3 flex-wrap"):
                with ui.element("div").classes(
                    "flex items-center bg-white border border-slate-200 rounded-full p-1 shadow-sm"
                ):
                    for label, value in [("Week", "last_week"), ("Month", "last_month"), ("Year", "year")]:
                        is_active = state["period"] == value
                        button_classes = (
                            "px-4 py-1.5 text-sm font-medium rounded-full transition-all"
                        )
                        if is_active:
                            button_classes += " bg-blue-600 text-white shadow-sm"
                        else:
                            button_classes += " text-slate-600 hover:text-slate-900"
                        ui.button(
                            label,
                            on_click=lambda _, v=value: _set_period(v),
                        ).props("flat").classes(button_classes)

                ui.select(
                    _year_options(_load_documents()),
                    value=state["year"],
                    on_change=lambda e: (
                        state.__setitem__("year", e.value or str(datetime.now().year)),
                        render_summary.refresh(),
                        render_list.refresh(),
                    ),
                ).props("dense").classes(C_INPUT + " w-28 bg-white shadow-sm")

                ui.input(
                    placeholder="Suche",
                    value=state["search"],
                    on_change=lambda e: (state.__setitem__("search", e.value or ""), render_list.refresh()),
                ).props("dense").classes(C_INPUT + " w-64 rounded-full bg-white shadow-sm")

    @ui.refreshable
    def render_summary():
        year_value = str(state.get("year") or datetime.now().year)
        items = _load_documents()
        total_docs = 0
        total_amount = 0.0
        total_tax = 0.0
        for doc in items:
            display_date = _document_display_date(doc)
            doc_year = ""
            if display_date:
                doc_year = str(display_date)[:4]
            if not doc_year or not doc_year.isdigit():
                doc_year = str(_doc_created_at(doc).year)
            if doc_year != year_value:
                continue
            total_docs += 1
            amount_total, _, amount_tax = _resolve_amounts(doc)
            if amount_total:
                total_amount += float(amount_total)
            if amount_tax:
                total_tax += float(amount_tax)

        with ui.row().classes("w-full gap-4 flex-wrap"):
            kpi_card(
                f"Dokumente ({year_value})",
                f"{total_docs}",
                "description",
                "text-blue-600",
                classes="flex-1 min-w-[220px]",
            )
            kpi_card(
                "Gesamtsumme",
                _format_amount_eur(total_amount),
                "payments",
                "text-emerald-600",
                classes="flex-1 min-w-[220px]",
            )
            kpi_card(
                "Steuern gesichert",
                _format_amount_eur(total_tax),
                "receipt_long",
                "text-amber-600",
                classes="flex-1 min-w-[220px]",
            )

    delete_id = {"value": None}
    with ui.dialog() as delete_all_dialog:
        with ui.card().classes(C_CARD + " p-5 w-[560px] max-w-[92vw]"):
            ui.label("Alle Dokumente löschen").classes(C_SECTION_TITLE)
            ui.label(
                "Das löscht alle Dokumente inkl. Dateien und Metadaten des aktiven Unternehmens."
            ).classes("text-sm text-slate-600")
            with ui.row().classes("justify-end gap-2 mt-3 w-full"):
                ui.button("Abbrechen", on_click=delete_all_dialog.close).classes(C_BTN_SEC)

                @ui_handler("documents.dialog.delete_all.confirm")
                def _confirm_delete_all():
                    action = "delete_all_documents"
                    current_document_id = None
                    current_filename = None
                    current_storage_key = None
                    current_storage_path = None
                    try:
                        with get_session() as s:
                            documents = s.exec(
                                select(Document).where(Document.company_id == int(comp.id or 0))
                            ).all()
                            for document in documents:
                                current_document_id = int(document.id or 0) or None
                                current_filename = document.original_filename or document.title or None
                                meta_entries = s.exec(
                                    select(DocumentMeta).where(DocumentMeta.document_id == int(document.id))
                                ).all()
                                storage_key = (document.storage_key or document.storage_path or "").strip()
                                if storage_key.startswith("storage/"):
                                    storage_key = storage_key.removeprefix("storage/").lstrip("/")
                                storage_path = resolve_document_path(document.storage_path)
                                current_storage_key = storage_key or None
                                current_storage_path = storage_path or None
                                if storage_path and os.path.exists(storage_path):
                                    try:
                                        os.remove(storage_path)
                                    except OSError:
                                        pass
                                if storage_key and (storage_key.startswith("companies/") or storage_key.startswith("documents/")):
                                    try:
                                        blob_storage().delete(storage_key)
                                    except Exception:
                                        pass
                                if storage_path:
                                    try:
                                        os.rmdir(os.path.dirname(storage_path))
                                    except OSError:
                                        pass
                                for meta in meta_entries:
                                    s.delete(meta)
                                s.delete(document)
                            s.commit()
                        logger.info(
                            "ACTION_SUCCESS",
                            extra=_build_action_context(
                                action,
                                document_id=current_document_id,
                                filename=current_filename,
                                storage_key=current_storage_key,
                                storage_path=current_storage_path,
                            ),
                        )
                        ui.notify("Alle Dokumente gelöscht.", color="green")
                        delete_all_dialog.close()
                        render_list.refresh()
                    except Exception:
                        logger.exception(
                            "ACTION_FAILED",
                            extra=_build_action_context(
                                action,
                                document_id=current_document_id,
                                filename=current_filename,
                                storage_key=current_storage_key,
                                storage_path=current_storage_path,
                            ),
                        )
                        doc_id_display = current_document_id if current_document_id is not None else "unbekannt"
                        ui.notify(f"Fehler beim Löschen (Dokument-ID: {doc_id_display})", color="red")

                ui.button("Alle löschen", on_click=_confirm_delete_all).classes("bg-rose-600 text-white hover:bg-rose-700")

    with ui.dialog() as reset_dialog:
        with ui.card().classes(C_CARD + " p-5 w-[520px] max-w-[92vw]"):
            ui.label("Webhook-Events zurücksetzen").classes(C_SECTION_TITLE)
            ui.label(
                "Damit werden alle gespeicherten n8n-Events gelöscht, um Duplikate erneut senden zu können."
            ).classes("text-sm text-slate-600")
            with ui.row().classes("justify-end gap-2 mt-3 w-full"):
                ui.button("Abbrechen", on_click=reset_dialog.close).classes(C_BTN_SEC)

                @ui_handler("documents.dialog.reset_events.confirm")
                def _confirm_reset():
                    with get_session() as s:
                        s.exec(delete(WebhookEvent))
                        s.commit()
                    ui.notify("Webhook-Events gelöscht.", color="green")
                    reset_dialog.close()

                ui.button("Reset", on_click=_confirm_reset).classes("bg-rose-600 text-white hover:bg-rose-700")

    with ui.dialog() as delete_dialog:
        with ui.card().classes(C_CARD + " p-5 w-[520px] max-w-[92vw]"):
            ui.label("Dokument löschen").classes(C_SECTION_TITLE)
            ui.label("Willst du dieses Dokument wirklich löschen?").classes("text-sm text-slate-600")
            with ui.row().classes("justify-end gap-2 mt-3 w-full"):
                ui.button("Abbrechen", on_click=delete_dialog.close).classes(C_BTN_SEC)

                @ui_handler("documents.dialog.delete.confirm")
                def _confirm_delete():
                    action = "delete_document"
                    document_id = int(delete_id["value"] or 0) or None
                    filename = None
                    storage_key = None
                    storage_path = None
                    try:
                        if not delete_id["value"]:
                            delete_dialog.close()
                            return
                        with get_session() as s:
                            document = s.get(Document, int(delete_id["value"]))
                            if document:
                                filename = document.original_filename or document.title or None
                                meta_entries = s.exec(
                                    select(DocumentMeta).where(DocumentMeta.document_id == int(document.id))
                                ).all()
                                storage_key = (document.storage_key or document.storage_path or "").strip()
                                if storage_key.startswith("storage/"):
                                    storage_key = storage_key.removeprefix("storage/").lstrip("/")
                                storage_path = resolve_document_path(document.storage_path)
                                if storage_path and os.path.exists(storage_path):
                                    try:
                                        os.remove(storage_path)
                                    except OSError:
                                        pass
                                if storage_key and (storage_key.startswith("companies/") or storage_key.startswith("documents/")):
                                    try:
                                        blob_storage().delete(storage_key)
                                    except Exception:
                                        pass
                                if storage_path:
                                    try:
                                        os.rmdir(os.path.dirname(storage_path))
                                    except OSError:
                                        pass
                                for meta in meta_entries:
                                    s.delete(meta)
                                s.delete(document)
                                s.commit()
                        logger.info(
                            "ACTION_SUCCESS",
                            extra=_build_action_context(
                                action,
                                document_id=document_id,
                                filename=filename,
                                storage_key=storage_key,
                                storage_path=storage_path,
                            ),
                        )
                        ui.notify("Gelöscht", color="green")
                        delete_dialog.close()
                        render_list.refresh()
                    except Exception:
                        logger.exception(
                            "ACTION_FAILED",
                            extra=_build_action_context(
                                action,
                                document_id=document_id,
                                filename=filename,
                                storage_key=storage_key,
                                storage_path=storage_path,
                            ),
                        )
                        doc_id_display = document_id if document_id is not None else "unbekannt"
                        ui.notify(f"Fehler beim Löschen (Dokument-ID: {doc_id_display})", color="red")

                ui.button("Löschen", on_click=_confirm_delete).classes("bg-rose-600 text-white hover:bg-rose-700")

    meta_state = {"doc_id": None, "title": "", "raw": "", "line_items": "", "flags": ""}
    with ui.dialog() as meta_dialog:
        with ui.card().classes(C_CARD + " p-5 w-[860px] max-w-[96vw]"):
            meta_title = ui.label("Metadaten").classes(C_SECTION_TITLE)
            ui.label("JSON bearbeiten, um Metadaten zu aktualisieren.").classes("text-xs text-slate-500 mb-2")
            raw_area = ui.textarea(label="Raw Payload (JSON)", value="").props("rows=8").classes(
                C_INPUT + " w-full font-mono text-xs"
            )
            line_area = ui.textarea(label="Line Items (JSON)", value="").props("rows=6").classes(
                C_INPUT + " w-full font-mono text-xs"
            )
            flags_area = ui.textarea(label="Compliance Flags (JSON)", value="").props("rows=4").classes(
                C_INPUT + " w-full font-mono text-xs"
            )

            def _parse_json_input(value: str | None, default: object, label: str) -> object | None:
                cleaned = (value or "").strip()
                if not cleaned:
                    return default
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    ui.notify(f"{label} ist kein gültiges JSON.", color="red")
                    return None

            def _save_meta() -> None:
                doc_id = meta_state.get("doc_id")
                if not doc_id:
                    ui.notify("Kein Dokument gewählt.", color="orange")
                    return
                raw_value = _parse_json_input(raw_area.value, {}, "Raw Payload")
                if raw_value is None:
                    return
                line_value = _parse_json_input(line_area.value, [], "Line Items")
                if line_value is None:
                    return
                flags_value = _parse_json_input(flags_area.value, [], "Compliance Flags")
                if flags_value is None:
                    return
                with get_session() as s:
                    meta = s.exec(select(DocumentMeta).where(DocumentMeta.document_id == int(doc_id))).first()
                    if not meta:
                        meta = DocumentMeta(document_id=int(doc_id))
                        s.add(meta)
                    meta.raw_payload_json = json.dumps(raw_value, ensure_ascii=False)
                    meta.line_items_json = json.dumps(line_value, ensure_ascii=False)
                    meta.compliance_flags_json = json.dumps(flags_value, ensure_ascii=False)
                    s.commit()
                ui.notify("Metadaten gespeichert.", color="green")
                meta_dialog.close()
                render_list.refresh()

            with ui.row().classes("justify-end gap-2 mt-3 w-full"):
                ui.button("Abbrechen", on_click=meta_dialog.close).classes(C_BTN_SEC)
                ui.button("Speichern", on_click=_save_meta).classes(C_BTN_PRIM)

    @ui_handler("documents.dialog.delete.open")
    def _open_delete(doc_id: int) -> None:
        delete_id["value"] = doc_id
        delete_dialog.open()

    @ui_handler("documents.dialog.meta.open")
    def _open_meta(doc_id: int) -> None:
        if not doc_id:
            return
        _hide_context_menu()
        action = "open_document_meta"
        filename = None
        storage_key = None
        storage_path = None
        try:
            with get_session() as s:
                meta = s.exec(select(DocumentMeta).where(DocumentMeta.document_id == doc_id)).first()
                doc = s.get(Document, doc_id)
            filename = doc.original_filename if doc else ""
            storage_key = (doc.storage_key or "").strip() if doc else None
            storage_path = (doc.storage_path or "").strip() if doc else None
            meta_state["title"] = f"Dokument #{doc_id} {filename}".strip()
            meta_state["doc_id"] = doc_id
            meta_state["raw"] = _format_json(
                meta.raw_payload_json if meta else "{}", redact_payload=True
            )
            meta_state["line_items"] = _format_json(meta.line_items_json if meta else "[]")
            meta_state["flags"] = _format_json(meta.compliance_flags_json if meta else "[]")
            meta_title.text = meta_state["title"]
            raw_area.value = meta_state["raw"]
            line_area.value = meta_state["line_items"]
            flags_area.value = meta_state["flags"]
            meta_dialog.open()
            logger.info(
                "ACTION_SUCCESS",
                extra=_build_action_context(
                    action,
                    document_id=doc_id,
                    filename=filename,
                    storage_key=storage_key,
                    storage_path=storage_path,
                ),
            )
        except Exception:
            logger.exception(
                "ACTION_FAILED",
                extra=_build_action_context(
                    action,
                    document_id=doc_id,
                    filename=filename,
                    storage_key=storage_key,
                    storage_path=storage_path,
                ),
            )
            ui.notify(f"Fehler beim Öffnen der Metadaten (Dokument-ID: {doc_id})", color="red")

    menu_overlay = ui.element("div").classes("fixed inset-0 z-40").style("display: none")
    menu_overlay.on("click", lambda _: _hide_context_menu())

    context_menu = ui.element("div").classes(
        "fixed bg-white rounded-lg shadow-xl border border-slate-100 w-48 z-50 py-2"
    ).style("display: none")
    with context_menu:
        ui.button(
            "👁️ Vorschau",
            on_click=_preview_document,
        ).classes("block w-full text-left px-4 py-2 hover:bg-slate-50 text-slate-700")
        ui.button(
            "⬇️ Download",
            on_click=_download_document,
        ).classes("block w-full text-left px-4 py-2 hover:bg-slate-50 text-slate-700")
        ui.button(
            "✏️ Metadaten",
            on_click=lambda: _open_meta(int(menu_state.get("doc_id") or 0)),
        ).classes("block w-full text-left px-4 py-2 hover:bg-slate-50 text-slate-700")
        ui.element("div").classes("border-t border-slate-100 my-1")
        ui.button(
            "🗑️ Löschen",
            on_click=_delete_document,
        ).classes("block w-full text-left px-4 py-2 hover:bg-rose-50 text-rose-600")

    def _format_size(size_bytes: int) -> str:
        if size_bytes <= 0:
            return "-"
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _format_amount_value(amount: float | None, currency: str | None) -> str:
        if amount is None:
            return "nicht verfügbar"
        currency = (currency or "").strip()
        if currency:
            return f"{amount:.2f} {currency}"
        return f"{amount:.2f}"

    def _format_amount_eur(amount: float) -> str:
        return f"{amount:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

    def _format_source(source: str | None) -> str:
        value = (source or "").strip().lower()
        if value in {"manual", "manuell"}:
            return "Manuell"
        if value == "n8n":
            return "n8n"
        if value in {"mail", "email"}:
            return "Mail"
        if value:
            return value.upper()
        return "-"

    def _resolve_status(doc: Document, amount_total: float | None, vendor: str | None) -> tuple[str, str]:
        if amount_total is not None or (vendor or "").strip():
            return "Verarbeitet", C_BADGE_GREEN
        if (doc.source or "").strip().lower() in {"mail", "email"}:
            return "Eingang", C_BADGE_BLUE
        return "Neu", C_BADGE_YELLOW

    def _resolve_file_icon(mime: str, filename: str) -> tuple[str, str]:
        lower_mime = (mime or "").lower()
        lower_name = (filename or "").lower()
        if "pdf" in lower_mime or lower_name.endswith(".pdf"):
            return "picture_as_pdf", "text-rose-500 bg-rose-50 border border-rose-100"
        if lower_mime.startswith("image/") or lower_name.endswith((".png", ".jpg", ".jpeg")):
            return "image", "text-emerald-500 bg-emerald-50 border border-emerald-100"
        return "insert_drive_file", "text-slate-500 bg-slate-100 border border-slate-200"

    @ui.refreshable
    def render_list():
        _hide_context_menu()
        items = _sort_documents(_filter_documents(_load_documents()))
        with ui.card().classes(
            C_CARD + " p-0 overflow-hidden w-full rounded-md shadow-none border-slate-200 bg-white backdrop-blur-0"
        ):
            meta_map = _load_meta_map([int(doc.id or 0) for doc in items])
            backfill_document_fields(session, items, meta_map=meta_map)

            with ui.row().classes(
                "w-full px-6 py-3 text-xs font-semibold tracking-wide text-slate-500 border-b border-slate-100"
            ):
                ui.label("Datei").classes("w-[26%]")
                ui.label("Tags").classes("w-[14%]")
                ui.label("Status").classes("w-[10%]")
                ui.label("Datum").classes("w-[10%]")
                ui.label("Brutto").classes("w-[8%] text-right")
                ui.label("Netto").classes("w-[8%] text-right")
                ui.label("Steuer").classes("w-[8%] text-right")
                ui.label("Größe").classes("w-[8%] text-right")
                ui.label("Quelle").classes("w-[8%]")

            if not items:
                ui.label("Keine Dokumente gefunden.").classes("px-6 py-8 text-sm text-slate-500")
                return

            def _open_context_menu(event, doc_id: int, open_url: str) -> None:
                coords = event.args or {}
                x = int(coords.get("pageX") or coords.get("clientX") or 0)
                y = int(coords.get("pageY") or coords.get("clientY") or 0)
                if x == 0 and y == 0:
                    x = 220
                    y = 220
                _show_context_menu(x, y, doc_id, open_url)

            for doc in items:
                doc_id = int(doc.id or 0)
                display_date = _document_display_date(doc)
                meta_values = resolve_document_meta_values(meta_map.get(doc_id))
                size_bytes = document_size_bytes(doc)
                meta_size = meta_values.get("size_bytes")
                if size_bytes <= 0 and isinstance(meta_size, int) and meta_size > 0:
                    size_bytes = meta_size
                amount_total, amount_net, amount_tax = _resolve_amounts(doc)
                meta_amount_total = meta_values.get("amount_total")
                meta_amount_net = meta_values.get("amount_net")
                meta_amount_tax = meta_values.get("amount_tax")
                if amount_total is None and meta_amount_total is not None:
                    amount_total = meta_amount_total
                if amount_net is None and meta_amount_net is not None:
                    amount_net = meta_amount_net
                if amount_tax is None and meta_amount_tax is not None:
                    amount_tax = meta_amount_tax
                currency_value = (doc.currency or meta_values.get("currency") or "").strip() or None
                meta_vendor = (meta_values.get("vendor") or "").strip()
                vendor_value = (doc.vendor or meta_vendor or "").strip()
                tags_value = _format_keywords(doc.keywords_json)
                if tags_value == "-":
                    meta_keywords = meta_values.get("keywords")
                    tags_value = _format_keywords(meta_keywords) if meta_keywords else tags_value
                size_display = _format_size(size_bytes)
                size_warning = 0 < size_bytes < 1024
                if size_warning:
                    size_display = f"{size_display} ⚠️"
                filename = doc.original_filename or doc.title or "Dokument"
                mime_value = doc.mime or doc.mime_type or ""
                open_url = f"/api/documents/{doc_id}/file"
                status_label, badge_class = _resolve_status(doc, amount_total, vendor_value)
                icon_name, icon_classes = _resolve_file_icon(mime_value, filename)
                with ui.row().classes(
                    "w-full px-6 py-2.5 items-center gap-4 border-b border-slate-100 hover:bg-slate-50 transition-colors"
                ).on(
                    "contextmenu",
                    lambda e, i=doc_id, u=open_url: _open_context_menu(e, i, u),
                    js_handler="(e) => { e.preventDefault(); emit({pageX: e.pageX, pageY: e.pageY, clientX: e.clientX, clientY: e.clientY}); }",
                ):
                    with ui.element("div").classes("flex items-center gap-3 w-[26%]"):
                        with ui.element("div").classes(
                            f"w-9 h-9 rounded-md flex items-center justify-center {icon_classes}"
                        ).style("box-shadow: inset 0 0 0 1px rgba(255,255,255,0.6)"):
                            ui.icon(icon_name).classes("text-base")
                        ui.link(filename, open_url, new_tab=True).classes(
                            "text-blue-600 font-medium hover:underline"
                        )
                    with ui.element("div").classes("w-[14%]"):
                        ui.label(tags_value).classes(
                            "text-sm text-slate-500 truncate"
                        ).tooltip(tags_value if tags_value != "-" else "")
                    with ui.element("div").classes("w-[10%]"):
                        ui.label(status_label).classes(badge_class)
                    ui.label(display_date or "-").classes("w-[10%] text-sm text-slate-600")
                    ui.label(
                        _format_amount_value(amount_total, currency_value) if amount_total is not None else "-"
                    ).classes("w-[8%] text-right text-sm text-slate-600")
                    ui.label(
                        _format_amount_value(amount_net, currency_value) if amount_net is not None else "-"
                    ).classes("w-[8%] text-right text-sm text-slate-600")
                    ui.label(
                        _format_amount_value(amount_tax, currency_value) if amount_tax is not None else "-"
                    ).classes("w-[8%] text-right text-sm text-slate-600")
                    ui.label(size_display).classes("w-[8%] text-right text-sm text-slate-600")
                    ui.label(_format_source(doc.source)).classes("w-[8%] text-sm text-slate-600")

    with ui.element("div").classes(
        "w-full bg-[#F5F7FA] rounded-xl p-6 border border-slate-100"
    ):
        render_filters()
        render_summary()
        render_list()
