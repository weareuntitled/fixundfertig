from __future__ import annotations

import csv
import io
import hashlib
import mimetypes
import os
import json
import tempfile
import zipfile
import logging
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException

from ._shared import *
from data import Document, DocumentMeta, WebhookEvent
from sqlmodel import delete
from data import WebhookEvent
from services.blob_storage import blob_storage, build_document_key
from services.documents import (
    build_document_record,
    document_matches_filters,
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
    upload_state = {
        "vendor": "",
        "doc_number": "",
        "doc_date": "",
        "amount_total": None,
        "amount_net": None,
        "amount_tax": None,
        "currency": "",
        "description": "",
    }

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
                "Datum",
                "Dokument",
                "Belegnummer",
                "Vendor",
                "Betrag",
                "Netto",
                "Steuer",
                "Währung",
                "Beschreibung",
                "ID",
            ]
        )
        for doc in items:
            invoice_date = _document_invoice_date(doc)
            writer.writerow(
                [
                    invoice_date,
                    doc.original_filename or doc.title or "Dokument",
                    doc.doc_number or "",
                    doc.vendor or "",
                    f"{doc.amount_total:.2f}" if doc.amount_total is not None else "",
                    f"{doc.amount_net:.2f}" if doc.amount_net is not None else "",
                    f"{doc.amount_tax:.2f}" if doc.amount_tax is not None else "",
                    doc.currency or "",
                    doc.description or "",
                    str(doc.id or ""),
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

    async def _handle_upload(event) -> None:
        if not comp.id:
            ui.notify("Kein aktives Unternehmen.", color="red")
            return
        filename = getattr(event, "name", "") or getattr(event.file, "name", "") or "upload"

        try:
            data = await _read_upload_bytes(event.file)
            size_bytes = len(data)
            validate_document_upload(filename, size_bytes)
        except HTTPException as exc:
            ui.notify(str(exc.detail), color="red")
            return
        except Exception as exc:
            ui.notify(f"Upload fehlgeschlagen: {exc}", color="red")
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

        doc_date = upload_state["doc_date"] or None
        amount_total = upload_state["amount_total"]
        if amount_total in ("", None):
            amount_total = None
        amount_net = upload_state["amount_net"]
        if amount_net in ("", None):
            amount_net = None
        amount_tax = upload_state["amount_tax"]
        if amount_tax in ("", None):
            amount_tax = None
        currency = upload_state["currency"].strip() if upload_state["currency"] else ""
        vendor = upload_state["vendor"].strip() if upload_state["vendor"] else ""
        doc_number = upload_state["doc_number"].strip() if upload_state["doc_number"] else ""
        description = upload_state["description"].strip() if upload_state["description"] else ""

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
                )
                document.mime = mime_type
                document.size = size_bytes
                document.sha256 = sha256
                s.add(document)
                s.flush()

                storage_key = build_document_key(int(comp.id), int(document.id), filename)
                document.storage_key = storage_key
                document.storage_path = storage_key

                blob_storage().put_bytes(storage_key, data, mime_type)
                s.commit()
            except Exception as exc:
                s.rollback()
                ui.notify(f"Upload fehlgeschlagen: {exc}", color="red")
                return

        ui.notify(f"Dokument gespeichert: {filename} ({size_bytes} Bytes)", color="green")
        render_list.refresh()

    with ui.dialog() as upload_dialog:
        with ui.card().classes(C_CARD + " p-5 w-[480px] max-w-[92vw]"):
            ui.label("Upload").classes(C_SECTION_TITLE)
            ui.label("PDF, JPG oder PNG, maximal 15 MB.").classes("text-xs text-slate-500 mb-2")
            ui.input(
                "Vendor / Verkäufer",
                on_change=lambda e: upload_state.__setitem__("vendor", e.value or ""),
            ).classes(C_INPUT + " w-full")
            ui.input(
                "Belegnummer",
                on_change=lambda e: upload_state.__setitem__("doc_number", e.value or ""),
            ).classes(C_INPUT + " w-full")
            ui.input(
                "Belegdatum",
                on_change=lambda e: upload_state.__setitem__("doc_date", e.value or ""),
            ).props("type=date").classes(C_INPUT + " w-full")
            ui.number(
                "Betrag",
                on_change=lambda e: upload_state.__setitem__("amount_total", e.value),
            ).props("step=0.01").classes(C_INPUT + " w-full")
            ui.number(
                "Netto",
                on_change=lambda e: upload_state.__setitem__("amount_net", e.value),
            ).props("step=0.01").classes(C_INPUT + " w-full")
            ui.number(
                "Steuerbetrag",
                on_change=lambda e: upload_state.__setitem__("amount_tax", e.value),
            ).props("step=0.01").classes(C_INPUT + " w-full")
            ui.input(
                "Währung",
                on_change=lambda e: upload_state.__setitem__("currency", e.value or ""),
            ).classes(C_INPUT + " w-full")
            ui.textarea(
                "Beschreibung",
                on_change=lambda e: upload_state.__setitem__("description", e.value or ""),
            ).classes(C_INPUT + " w-full")
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
    debug_button = None
    reset_button = None
    delete_all_button = None

    def _update_action_buttons() -> None:
        if export_button and upload_button:
            has_selection = bool(selected_ids)
            export_button.visible = has_selection
            upload_button.visible = not has_selection
        if debug_button:
            debug_button.visible = bool(selected_ids)

    def _debug_log_selection() -> None:
        payload = {"selected_ids": sorted(selected_ids)}
        ui.run_javascript(f"console.log('documents_debug', {json.dumps(payload)});")

    def _open_reset_events() -> None:
        reset_dialog.open()

    def _open_delete_all() -> None:
        delete_all_dialog.open()

    def _coerce_float(value: object) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _document_size_bytes(doc: Document) -> int:
        size_value = doc.size_bytes or doc.size or 0
        try:
            size = int(size_value or 0)
        except (TypeError, ValueError):
            size = 0
        if size > 0:
            return size
        storage_key = (doc.storage_key or doc.storage_path or "").strip()
        if storage_key.startswith("storage/"):
            storage_key = storage_key.removeprefix("storage/").lstrip("/")
        storage_path = resolve_document_path(doc.storage_path)
        if storage_path and os.path.exists(storage_path):
            try:
                return int(os.path.getsize(storage_path))
            except OSError:
                return 0
        if storage_key and (storage_key.startswith("companies/") or storage_key.startswith("documents/")):
            try:
                data = blob_storage().get_bytes(storage_key)
                return len(data)
            except Exception:
                return 0
        return 0

    @ui.refreshable
    def render_filters():
        with ui.row().classes("w-full items-center gap-3 flex-wrap mb-2"):
            ui.label("Dokumente").classes(C_PAGE_TITLE)
            ui.space()
            nonlocal export_button, upload_button, debug_button, reset_button, delete_all_button
            export_button = ui.button(
                "Export",
                icon="download",
                on_click=lambda: _export_documents(selected_ids),
            ).classes(C_BTN_SEC)
            upload_button = ui.button("Upload", icon="upload", on_click=upload_dialog.open).classes(C_BTN_PRIM)
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

                def _confirm_delete_all():
                    with get_session() as s:
                        documents = s.exec(
                            select(Document).where(Document.company_id == int(comp.id or 0))
                        ).all()
                        for document in documents:
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
                    ui.notify("Alle Dokumente gelöscht.", color="green")
                    delete_all_dialog.close()
                    render_list.refresh()

                ui.button("Alle löschen", on_click=_confirm_delete_all).classes("bg-rose-600 text-white hover:bg-rose-700")

    with ui.dialog() as reset_dialog:
        with ui.card().classes(C_CARD + " p-5 w-[520px] max-w-[92vw]"):
            ui.label("Webhook-Events zurücksetzen").classes(C_SECTION_TITLE)
            ui.label(
                "Damit werden alle gespeicherten n8n-Events gelöscht, um Duplikate erneut senden zu können."
            ).classes("text-sm text-slate-600")
            with ui.row().classes("justify-end gap-2 mt-3 w-full"):
                ui.button("Abbrechen", on_click=reset_dialog.close).classes(C_BTN_SEC)

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

                def _confirm_delete():
                    if not delete_id["value"]:
                        delete_dialog.close()
                        return
                    with get_session() as s:
                        document = s.get(Document, int(delete_id["value"]))
                        if document:
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
                    ui.notify("Gelöscht", color="green")
                    delete_dialog.close()
                    render_list.refresh()

                ui.button("Löschen", on_click=_confirm_delete).classes("bg-rose-600 text-white hover:bg-rose-700")

    def _open_delete(doc_id: int) -> None:
        delete_id["value"] = doc_id
        delete_dialog.open()

    def _open_meta(doc_id: int) -> None:
        with get_session() as s:
            meta = s.exec(select(DocumentMeta).where(DocumentMeta.document_id == doc_id)).first()
            doc = s.get(Document, doc_id)
        if not meta:
            ui.notify("Keine Metadaten gefunden.", color="orange")
            return
        title_label = doc.original_filename if doc else ""
        meta_state["title"] = f"Dokument #{doc_id} {title_label}".strip()
        meta_state["raw"] = _format_json(meta.raw_payload_json, redact_payload=True)
        meta_state["line_items"] = _format_json(meta.line_items_json)
        meta_state["flags"] = _format_json(meta.compliance_flags_json)
        meta_title.text = meta_state["title"]
        raw_area.value = meta_state["raw"]
        line_area.value = meta_state["line_items"]
        flags_area.value = meta_state["flags"]
        meta_dialog.open()

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
            return "-"
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
            for doc in items:
                doc_id = int(doc.id or 0)
                created_at = _doc_created_at(doc)
                size_bytes = _document_size_bytes(doc)
                amount_total = _coerce_float(doc.amount_total)
                amount_net = _coerce_float(doc.amount_net)
                amount_tax = _coerce_float(doc.amount_tax)
                rows.append(
                    {
                        "id": doc_id,
                        "date": created_at.strftime("%Y-%m-%d") if created_at != datetime.min else "",
                        "filename": doc.original_filename or doc.title or "Dokument",
                        "size_bytes": size_bytes,
                        "size_display": _format_size(size_bytes),
                        "size_warning": 0 < size_bytes < 1024,
                        "mime": doc.mime or doc.mime_type or "-",
                        "doc_number": doc.doc_number or "-",
                        "vendor": doc.vendor or "-",
                        "amount": float(amount_total or 0),
                        "amount_net": float(amount_net or 0),
                        "amount_tax": float(amount_tax or 0),
                        "amount_display": _format_amount_value(amount_total, doc.currency),
                        "amount_net_display": _format_amount_value(amount_net, doc.currency),
                        "amount_tax_display": _format_amount_value(amount_tax, doc.currency),
                        "open_url": f"/api/documents/{doc_id}/file",
                    }
                )

            columns = [
                {"name": "date", "label": "Datum", "field": "date", "sortable": True, "align": "left"},
                {"name": "filename", "label": "Datei", "field": "filename", "sortable": True, "align": "left"},
                {"name": "size_bytes", "label": "Größe", "field": "size_bytes", "sortable": True, "align": "right"},
                {"name": "mime", "label": "Mime", "field": "mime", "sortable": True, "align": "left"},
                {"name": "doc_number", "label": "Belegnr", "field": "doc_number", "sortable": True, "align": "left"},
                {"name": "vendor", "label": "Vendor", "field": "vendor", "sortable": True, "align": "left"},
                {"name": "amount", "label": "Betrag", "field": "amount", "sortable": True, "align": "right"},
                {"name": "amount_net", "label": "Netto", "field": "amount_net", "sortable": True, "align": "right"},
                {"name": "amount_tax", "label": "Steuer", "field": "amount_tax", "sortable": True, "align": "right"},
                {"name": "actions", "label": "", "field": "actions", "sortable": False, "align": "right"},
            ]
            table = ui.table(columns=columns, rows=rows, row_key="id", selection="multiple").classes("w-full")

            def _on_selection(event) -> None:
                selected_rows = event.selection or []
                selected_ids.clear()
                selected_ids.update({int(item.get("id") or 0) for item in selected_rows})
                _update_action_buttons()

            table.on_select(_on_selection)

            def _row_from_slot(slot_obj):
                props = getattr(slot_obj, "props", None)
                if isinstance(props, dict):
                    return props.get("row")
                if isinstance(props, Mapping):
                    return props.get("row")
                if hasattr(props, "get"):
                    return props.get("row")
                return getattr(props, "row", None)

            with table.add_slot("body-cell-amount") as slot:
                ui.label().bind_text_from(slot, "props.row.amount_display", strict=False).classes("text-right")

            with table.add_slot("body-cell-amount_net") as slot:
                ui.label().bind_text_from(slot, "props.row.amount_net_display", strict=False).classes("text-right")

            with table.add_slot("body-cell-amount_tax") as slot:
                ui.label().bind_text_from(slot, "props.row.amount_tax_display", strict=False).classes("text-right")

            with table.add_slot("body-cell-size_bytes") as slot:
                with ui.row().classes("items-center justify-end gap-1"):
                    ui.label().bind_text_from(slot, "props.row.size_display", strict=False).classes("text-right")
                    warn_icon = ui.icon("warning").classes("text-amber-500 text-xs")
                    warn_icon.bind_visibility_from(slot, "props.row.size_warning", strict=False)
                    warn_icon.tooltip("Sehr kleine Datei (< 1 KB).")

            with table.add_slot("body-cell-actions") as slot:
                def _open_meta_from_slot() -> None:
                    row = _row_from_slot(slot)
                    if not row:
                        props = getattr(slot, "props", None)
                        logger.warning(
                            "Dokumentslot ohne Row für Meta: props_type=%s row=%s",
                            type(props).__name__,
                            row,
                        )
                        ui.notify("Dokument nicht verfügbar.", type="warning")
                        return
                    _open_meta(int(row["id"]))

                def _open_delete_from_slot() -> None:
                    row = _row_from_slot(slot)
                    if not row:
                        props = getattr(slot, "props", None)
                        logger.warning(
                            "Dokumentslot ohne Row für Löschen: props_type=%s row=%s",
                            type(props).__name__,
                            row,
                        )
                        ui.notify("Dokument nicht verfügbar.", type="warning")
                        return
                    _open_delete(int(row["id"]))

                def _open_document_from_slot() -> None:
                    row = _row_from_slot(slot)
                    if not row or not row.get("id"):
                        props = getattr(slot, "props", None)
                        logger.warning(
                            "Dokumentslot ohne ID: props_type=%s row=%s",
                            type(props).__name__,
                            row,
                        )
                        ui.notify("Dokument nicht verfügbar.", type="warning")
                        return
                    ui.run_javascript(f"window.open('/api/documents/{int(row['id'])}/file')")

                with ui.row().classes("justify-end gap-2"):
                    link = ui.link("Öffnen", "#").classes("text-sm text-sky-600")
                    link.on("click", _open_document_from_slot)
                    ui.button(
                        "",
                        icon="info",
                        on_click=_open_meta_from_slot,
                    ).props("flat dense").classes("text-slate-600")
                    ui.button(
                        "",
                        icon="delete",
                        on_click=_open_delete_from_slot,
                    ).props("flat dense").classes("text-rose-600")

    render_filters()
    render_list()
