from __future__ import annotations

import csv
import io
import hashlib
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
from data import Document, DocumentMeta, WebhookEvent
from sqlmodel import delete
from data import WebhookEvent
from integrations.n8n_client import post_to_n8n
from services.blob_storage import blob_storage, build_document_key
from services.documents import (
    backfill_document_fields,
    build_document_record,
    document_size_bytes,
    document_matches_filters,
    normalize_keywords,
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
    vendor_input = None
    doc_number_input = None
    doc_date_input = None
    amount_total_input = None
    amount_net_input = None
    amount_tax_input = None
    currency_input = None
    description_input = None
    tags_input = None

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

    def _get_input_value(component, default=""):
        if component is None:
            return default
        return getattr(component, "value", default)

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
            if not comp.id:
                ui.notify("Kein aktives Unternehmen.", color="red")
                return

            try:
                data = await _read_upload_bytes(event.file)
                size_bytes = len(data)
                validate_document_upload(filename, size_bytes)
            except HTTPException:
                logger.exception(
                    "ACTION_FAILED",
                    extra=_build_action_context(
                        action,
                        filename=filename,
                    ),
                )
                ui.notify("Fehler beim Upload (Dokument-ID: unbekannt)", color="red")
                return

            ext = os.path.splitext(filename)[1].lower().lstrip(".")
            if ext == "jpeg":
                ext = "jpg"

            mime_type = (
                getattr(event, "type", "")
                or getattr(event.file, "content_type", "")
                or mimetypes.guess_type(filename)[0]
                or ""
            )
            sha256 = hashlib.sha256(data).hexdigest()

            doc_date = (_get_input_value(doc_date_input, "") or "").strip() or None
            amount_total = _get_input_value(amount_total_input)
            if amount_total in ("", None):
                amount_total = None
            amount_net = _get_input_value(amount_net_input)
            if amount_net in ("", None):
                amount_net = None
            amount_tax = _get_input_value(amount_tax_input)
            if amount_tax in ("", None):
                amount_tax = None
            currency = (_get_input_value(currency_input, "") or "").strip()
            vendor = (_get_input_value(vendor_input, "") or "").strip()
            doc_number = (_get_input_value(doc_number_input, "") or "").strip()
            description = (_get_input_value(description_input, "") or "").strip()
            keywords_value = _get_input_value(tags_input, "")
            keywords_json = normalize_keywords(keywords_value)

            with get_session() as s:
                try:
                    document = build_document_record(
                        int(comp.id),
                        filename,
                        mime_type=mime_type,
                        size_bytes=size_bytes,
                        source="MANUAL",
                        doc_type=ext,
                        vendor=vendor,
                        doc_number=doc_number,
                        doc_date=doc_date,
                        amount_total=amount_total,
                        amount_net=amount_net,
                        amount_tax=amount_tax,
                        currency=currency,
                        description=description,
                        keywords_json=keywords_json,
                    )
                    document.mime = mime_type
                    document.size = size_bytes
                    document.sha256 = sha256
                    s.add(document)
                    s.flush()

                    document_id = int(document.id)
                    storage_key = build_document_key(int(comp.id), int(document.id), filename)
                    document.storage_key = storage_key
                    document.storage_path = storage_key

                    blob_storage().put_bytes(storage_key, data, mime_type)
                    s.commit()
                except Exception:
                    s.rollback()
                    raise

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
            ui.notify(f"Dokument gespeichert: {filename} ({size_bytes} Bytes)", color="green")
            if comp.n8n_enabled and (comp.n8n_webhook_url or "").strip():
                try:
                    post_to_n8n(
                        webhook_url=comp.n8n_webhook_url,
                        secret=comp.n8n_secret,
                        event="document_upload",
                        company_id=int(comp.id),
                        data={
                            "document_id": document_id,
                            "filename": filename,
                            "mime_type": mime_type,
                            "size_bytes": size_bytes,
                            "vendor": vendor,
                            "doc_number": doc_number,
                            "doc_date": doc_date,
                            "amount_total": amount_total,
                            "amount_net": amount_net,
                            "amount_tax": amount_tax,
                            "currency": currency,
                            "description": description,
                            "keywords": keywords_json,
                            "file_url": f"/api/documents/{document_id}/file",
                        },
                    )
                    ui.notify("n8n Webhook gesendet.", color="green")
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
                    ui.notify(f"n8n Webhook fehlgeschlagen: {exc}", color="orange")
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

    with ui.dialog() as upload_dialog:
        with ui.card().classes(C_CARD + " p-5 w-[480px] max-w-[92vw]"):
            ui.label("Upload").classes(C_SECTION_TITLE)
            ui.label("PDF, JPG oder PNG, maximal 15 MB.").classes("text-xs text-slate-500 mb-2")
            vendor_input = ui.input("Vendor / Verkäufer").classes(C_INPUT + " w-full")
            doc_number_input = ui.input("Belegnummer").classes(C_INPUT + " w-full")
            doc_date_input = ui.input("Belegdatum").props("type=date").classes(C_INPUT + " w-full")
            amount_total_input = ui.number("Betrag").props("step=0.01").classes(C_INPUT + " w-full")
            amount_net_input = ui.number("Netto").props("step=0.01").classes(C_INPUT + " w-full")
            amount_tax_input = ui.number("Steuerbetrag").props("step=0.01").classes(C_INPUT + " w-full")
            currency_input = ui.input("Währung").classes(C_INPUT + " w-full")
            description_input = ui.textarea("Beschreibung").classes(C_INPUT + " w-full")
            tags_input = ui.input("Tags (kommagetrennt)").classes(C_INPUT + " w-full")
            upload_input = ui.upload(
                on_upload=_handle_upload,
                auto_upload=False,
                label="Datei wählen",
            ).classes("w-full")
            with ui.row().classes("justify-end w-full mt-4 gap-2"):
                ui.button(
                    "Speichern",
                    on_click=lambda: upload_input.run_method("upload"),
                ).classes(C_BTN_PRIM)
                ui.button("Schließen", on_click=upload_dialog.close).classes(C_BTN_SEC)

    selected_ids: set[int] = set()
    export_button = None
    upload_button = None
    open_button = None
    meta_button = None
    delete_button = None
    debug_button = None
    reset_button = None
    delete_all_button = None

    def _update_action_buttons() -> None:
        if export_button and upload_button:
            has_selection = bool(selected_ids)
            export_button.visible = has_selection
            upload_button.visible = not has_selection
        if open_button and meta_button and delete_button:
            single_selection = len(selected_ids) == 1
            open_button.visible = single_selection
            meta_button.visible = single_selection
            delete_button.visible = single_selection
        if debug_button:
            debug_button.visible = bool(selected_ids)

    def _open_selected_document() -> None:
        if len(selected_ids) != 1:
            ui.notify("Bitte genau ein Dokument auswählen.", color="orange")
            return
        doc_id = next(iter(selected_ids))
        ui.run_javascript(f"window.open('/api/documents/{doc_id}/file')")

    def _open_selected_meta() -> None:
        if len(selected_ids) != 1:
            ui.notify("Bitte genau ein Dokument auswählen.", color="orange")
            return
        doc_id = next(iter(selected_ids))
        _open_meta(doc_id)

    def _open_selected_delete() -> None:
        if len(selected_ids) != 1:
            ui.notify("Bitte genau ein Dokument auswählen.", color="orange")
            return
        doc_id = next(iter(selected_ids))
        _open_delete(doc_id)

    @ui_handler("documents.debug")
    def _debug_log_selection() -> None:
        payload = {"selected_ids": sorted(selected_ids)}
        ui.run_javascript(f"console.log('documents_debug', {json.dumps(payload)});")

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
        return amount_total, amount_net, amount_tax

    @ui.refreshable
    def render_filters():
        with ui.row().classes("w-full items-center gap-3 flex-wrap mb-2"):
            ui.label("Dokumente").classes(C_PAGE_TITLE)
            ui.space()
            nonlocal export_button, upload_button, open_button, meta_button, delete_button, debug_button, reset_button, delete_all_button
            export_button = ui.button(
                "Export",
                icon="download",
                on_click=lambda: _export_documents(selected_ids),
            ).classes(C_BTN_SEC)
            upload_button = ui.button("Upload", icon="upload", on_click=upload_dialog.open).classes(C_BTN_PRIM)
            open_button = ui.button("Öffnen", icon="open_in_new", on_click=_open_selected_document).classes(C_BTN_SEC)
            meta_button = ui.button("Meta", icon="info", on_click=_open_selected_meta).classes(C_BTN_SEC)
            delete_button = ui.button(
                "Löschen",
                icon="delete",
                on_click=_open_selected_delete,
            ).classes("bg-rose-600 text-white hover:bg-rose-700")
            debug_button = ui.button("Debug", icon="terminal", on_click=_debug_log_selection).classes(C_BTN_SEC)
            reset_button = ui.button(
                "Events reset",
                icon="delete_sweep",
                on_click=_open_reset_events,
            ).classes(C_BTN_SEC)
            delete_all_button = ui.button(
                "Alles löschen",
                icon="delete_forever",
                on_click=_open_delete_all,
            ).classes("bg-rose-600 text-white hover:bg-rose-700")
            _update_action_buttons()

        with ui.row().classes("w-full items-center gap-3 flex-wrap mb-2"):
            ui.input(
                placeholder="Suche",
                value=state["search"],
                on_change=lambda e: (state.__setitem__("search", e.value or ""), render_list.refresh()),
            ).props("dense").classes(C_INPUT + " w-64")

        with ui.row().classes("w-full items-center gap-2 flex-wrap mb-3"):
            ui.label("Zeitraum").classes("text-xs text-slate-500")
            ui.button(
                "Letzte Woche",
                on_click=lambda: (state.__setitem__("period", "last_week"), render_filters.refresh(), render_list.refresh()),
            ).props("outline").classes(C_BTN_SEC + " text-xs")
            ui.button(
                "Letzter Monat",
                on_click=lambda: (state.__setitem__("period", "last_month"), render_filters.refresh(), render_list.refresh()),
            ).props("outline").classes(C_BTN_SEC + " text-xs")
            ui.button(
                "Letzte 3 Monate",
                on_click=lambda: (state.__setitem__("period", "last_3_months"), render_filters.refresh(), render_list.refresh()),
            ).props("outline").classes(C_BTN_SEC + " text-xs")
            ui.button(
                "Jahr",
                on_click=lambda: (state.__setitem__("period", "year"), render_filters.refresh(), render_list.refresh()),
            ).props("outline").classes(C_BTN_SEC + " text-xs")
            ui.button(
                "Individuell",
                on_click=lambda: (state.__setitem__("period", "custom"), render_filters.refresh(), render_list.refresh()),
            ).props("outline").classes(C_BTN_SEC + " text-xs")
            if state["period"] == "year":
                ui.select(
                    _year_options(_load_documents()),
                    label="Jahr",
                    value=state["year"],
                    on_change=lambda e: (state.__setitem__("year", e.value or ""), render_list.refresh()),
                ).props("dense").classes(C_INPUT + " w-28")
            if state["period"] == "custom":
                ui.input(
                    "Von",
                    value=state["date_from"],
                    on_change=lambda e: (state.__setitem__("date_from", e.value or ""), render_list.refresh()),
                ).props("dense type=date").classes(C_INPUT + " w-32")
                ui.input(
                    "Bis",
                    value=state["date_to"],
                    on_change=lambda e: (state.__setitem__("date_to", e.value or ""), render_list.refresh()),
                ).props("dense type=date").classes(C_INPUT + " w-32")

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
                                meta = s.exec(
                                    select(DocumentMeta).where(DocumentMeta.document_id == int(document.id))
                                ).first()
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
                                if meta:
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
                                meta = s.exec(
                                    select(DocumentMeta).where(DocumentMeta.document_id == int(document.id))
                                ).first()
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
                                if meta:
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

    @ui_handler("documents.dialog.delete.open")
    def _open_delete(doc_id: int) -> None:
        delete_id["value"] = doc_id
        delete_dialog.open()

    @ui_handler("documents.dialog.meta.open")
    def _open_meta(doc_id: int) -> None:
        action = "open_document_meta"
        filename = None
        storage_key = None
        storage_path = None
        try:
            with get_session() as s:
                meta = s.exec(select(DocumentMeta).where(DocumentMeta.document_id == doc_id)).first()
                doc = s.get(Document, doc_id)
            if not meta:
                ui.notify("Keine Metadaten gefunden.", color="orange")
                return
            filename = doc.original_filename if doc else ""
            storage_key = (doc.storage_key or "").strip() if doc else None
            storage_path = (doc.storage_path or "").strip() if doc else None
            meta_state["title"] = f"Dokument #{doc_id} {filename}".strip()
            meta_state["raw"] = _format_json(meta.raw_payload_json, redact_payload=True)
            meta_state["line_items"] = _format_json(meta.line_items_json)
            meta_state["flags"] = _format_json(meta.compliance_flags_json)
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

    @ui.refreshable
    def render_list():
        items = _sort_documents(_filter_documents(_load_documents()))
        selected_ids.clear()
        _update_action_buttons()

        with ui.card().classes(C_CARD + " p-0 overflow-hidden w-full"):
            rows = []
            meta_map = _load_meta_map([int(doc.id or 0) for doc in items])
            backfill_document_fields(session, items, meta_map=meta_map)
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
                meta_vendor = (meta_values.get("vendor") or "").strip()
                meta_doc_number = (meta_values.get("doc_number") or "").strip()
                vendor_value = (doc.vendor or meta_vendor or "").strip() or "-"
                doc_number_value = (doc.doc_number or meta_doc_number or "").strip() or "-"
                tags_value = _format_keywords(doc.keywords_json)
                if tags_value == "-":
                    meta_keywords = meta_values.get("keywords")
                    tags_value = _format_keywords(meta_keywords) if meta_keywords else tags_value
                meta_currency = (meta_values.get("currency") or "").strip()
                currency_value = (doc.currency or meta_currency or "").strip() or None
                size_display = _format_size(size_bytes)
                size_warning = 0 < size_bytes < 1024
                if size_warning:
                    size_display = f"{size_display} ⚠️"
                logger.debug(
                    "document_row_keys",
                    extra={
                        "doc_id": doc_id,
                        "amount_total": amount_total,
                        "amount_net": amount_net,
                        "amount_tax": amount_tax,
                        "currency": currency_value,
                    },
                )
                rows.append(
                    {
                        "id": doc_id,
                        "date": display_date,
                        "filename": doc.original_filename or doc.title or "Dokument",
                        "size_bytes": size_bytes,
                        "size_display": size_display,
                        "mime": doc.mime or doc.mime_type or "-",
                        "doc_number": doc_number_value,
                        "vendor": vendor_value,
                        "tags": tags_value,
                        "amount": amount_total,
                        "amount_net": amount_net,
                        "amount_tax": amount_tax,
                        "amount_display": _format_amount_value(amount_total, currency_value),
                        "amount_net_display": _format_amount_value(amount_net, currency_value),
                        "amount_tax_display": _format_amount_value(amount_tax, currency_value),
                        "open_url": f"/api/documents/{doc_id}/file",
                    }
                )

            columns = [
                {"name": "date", "label": "Datum", "field": "date", "sortable": True, "align": "left"},
                {"name": "filename", "label": "Datei", "field": "filename", "sortable": True, "align": "left"},
                {
                    "name": "size_display",
                    "label": "Größe",
                    "field": "size_display",
                    "sortable": True,
                    "align": "right",
                },
                {"name": "mime", "label": "Mime", "field": "mime", "sortable": True, "align": "left"},
                {"name": "doc_number", "label": "Belegnr", "field": "doc_number", "sortable": True, "align": "left"},
                {"name": "vendor", "label": "Vendor", "field": "vendor", "sortable": True, "align": "left"},
                {"name": "tags", "label": "Tags", "field": "tags", "sortable": True, "align": "left"},
                {
                    "name": "amount_display",
                    "label": "Betrag",
                    "field": "amount_display",
                    "sortable": True,
                    "align": "right",
                },
                {
                    "name": "amount_net_display",
                    "label": "Netto",
                    "field": "amount_net_display",
                    "sortable": True,
                    "align": "right",
                },
                {
                    "name": "amount_tax_display",
                    "label": "Steuer",
                    "field": "amount_tax_display",
                    "sortable": True,
                    "align": "right",
                },
            ]
            table = ui.table(columns=columns, rows=rows, row_key="id", selection="multiple").classes("w-full")

            def _on_selection(event) -> None:
                selected_rows = event.selection or []
                selected_ids.clear()
                selected_ids.update({int(item.get("id") or 0) for item in selected_rows})
                _update_action_buttons()

            table.on_select(_on_selection)

    render_filters()
    render_list()
