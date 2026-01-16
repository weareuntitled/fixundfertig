from __future__ import annotations

import hashlib
import mimetypes
import os
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException

from ._shared import *
from data import Document
from services.blob_storage import blob_storage, build_document_key
from services.documents import (
    build_document_record,
    compute_sha256_file,
    document_matches_filters,
    resolve_document_path,
    serialize_document,
    validate_document_upload,
)
from storage.service import save_upload_bytes


def render_documents(session, comp: Company) -> None:
    ui.label("Dokumente").classes(C_PAGE_TITLE)
    ui.label("Uploads verwalten und durchsuchen.").classes("text-sm text-slate-500 mb-4")

    state = {
        "search": "",
        "source": "",
        "doc_type": "",
        "date_from": "",
        "date_to": "",
    }

    def _load_documents() -> list[Document]:
        session.expire_all()
        return session.exec(
            select(Document).where(Document.company_id == int(comp.id or 0))
        ).all()

    def _filter_documents(items: list[Document]) -> list[Document]:
        return [
            doc
            for doc in items
            if document_matches_filters(
                doc,
                query=state["search"],
                source=state["source"],
                doc_type=state["doc_type"],
                date_from=state["date_from"],
                date_to=state["date_to"],
            )
        ]

    def _sort_documents(items: list[Document]) -> list[Document]:
        def sort_key(doc: Document):
            created_at = doc.created_at
            if isinstance(created_at, datetime):
                return created_at
            try:
                return datetime.fromisoformat(str(created_at))
            except Exception:
                return datetime.min

        return sorted(items, key=sort_key, reverse=True)

    def _doc_type_options(items: list[Document]) -> dict[str, str]:
        types = sorted(
            {
                (os.path.splitext(doc.original_filename or "")[1].lstrip(".").lower())
                for doc in items
                if os.path.splitext(doc.original_filename or "")[1].lstrip(".").strip()
            }
        )
        options = {"": "Alle"}
        for entry in types:
            options[entry] = entry
        return options

    def _source_options(items: list[Document]) -> dict[str, str]:
        sources = sorted(
            {
                (doc.source.value if isinstance(doc.source, DocumentSource) else (doc.source or "")).strip()
                for doc in items
                if (doc.source or "")
            }
        )
        options = {"": "Alle"}
        for entry in sources:
            options[entry] = entry
        return options

    def _handle_upload(event) -> None:
        if not comp.id:
            ui.notify("Kein aktives Unternehmen.", color="red")
            return
        filename = getattr(event, "name", "") or getattr(event.file, "name", "") or "upload"

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

        try:
            data = _read_upload_bytes(event.file)
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

        with get_session() as s:
            try:
                document = build_document_record(
                    int(comp.id),
                    filename,
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                    source="MANUAL",
                    doc_type=ext,
                    original_filename=filename,
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

    with ui.card().classes(C_CARD + " p-5 mb-4"):
        ui.label("Upload").classes("text-sm font-semibold text-slate-700")
        ui.label("PDF, JPG oder PNG, maximal 15 MB.").classes("text-xs text-slate-500 mb-2")
        ui.upload(on_upload=_handle_upload, auto_upload=True, label="Datei wählen").props("flat dense").classes("w-full")

    with ui.row().classes("w-full justify-between items-end mb-3 gap-3 flex-wrap"):
        ui.input(
            "Suche",
            placeholder="Dateiname",
            on_change=lambda e: (state.__setitem__("search", e.value or ""), render_list.refresh()),
        ).classes(C_INPUT + " min-w-[240px]")

        with ui.row().classes("gap-2 items-end flex-wrap"):
            ui.select(
                _source_options(_load_documents()),
                label="Quelle",
                value=state["source"],
                on_change=lambda e: (state.__setitem__("source", e.value or ""), render_list.refresh()),
            ).classes(C_INPUT)
            ui.select(
                _doc_type_options(_load_documents()),
                label="Typ",
                value=state["doc_type"],
                on_change=lambda e: (state.__setitem__("doc_type", e.value or ""), render_list.refresh()),
            ).classes(C_INPUT)
            ui.input("Von", on_change=lambda e: (state.__setitem__("date_from", e.value or ""), render_list.refresh())).props("type=date").classes(C_INPUT)
            ui.input("Bis", on_change=lambda e: (state.__setitem__("date_to", e.value or ""), render_list.refresh())).props("type=date").classes(C_INPUT)

    delete_id = {"value": None}

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
                            storage_path = document_storage_path(int(document.company_id), document.storage_key)
                            if storage_path and os.path.exists(storage_path):
                                try:
                                    os.remove(storage_path)
                                except OSError:
                                    pass
                            s.delete(document)
                            s.commit()
                    ui.notify("Gelöscht", color="green")
                    delete_dialog.close()
                    render_list.refresh()

                ui.button("Löschen", on_click=_confirm_delete).classes("bg-rose-600 text-white hover:bg-rose-700")

    def _open_delete(doc_id: int) -> None:
        delete_id["value"] = doc_id
        delete_dialog.open()

    @ui.refreshable
    def render_list():
        items = _sort_documents(_filter_documents(_load_documents()))

        if not items:
            with ui.card().classes(C_CARD + " p-4"):
                ui.label("Keine Dokumente gefunden").classes("text-sm text-slate-500")
            return

        with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
            with ui.row().classes(C_TABLE_HEADER):
                ui.label("Datum").classes("w-32 font-bold text-xs text-slate-500")
                ui.label("Datei").classes("flex-1 font-bold text-xs text-slate-500")
                ui.label("Typ").classes("w-24 font-bold text-xs text-slate-500")
                ui.label("Quelle").classes("w-24 font-bold text-xs text-slate-500")
                ui.label("").classes("w-32 font-bold text-xs text-slate-500")

            for doc in items:
                row = serialize_document(doc)
                created_at = row.get("created_at", "")
                with ui.row().classes("w-full items-center border-t border-slate-100 px-4 py-3"):
                    ui.label(created_at[:10]).classes("w-32 text-sm text-slate-600")
                    ui.label(row.get("original_filename") or row.get("title") or "Dokument").classes("flex-1 text-sm text-slate-700 truncate")
                    ui.label(row.get("type") or "-").classes("w-24 text-sm text-slate-600")
                    ui.label(row.get("source") or "-").classes("w-24 text-sm text-slate-600")
                    with ui.row().classes("w-32 justify-end gap-2"):
                        ui.link(
                            "Öffnen",
                            f"/api/documents/{row.get('id')}/file",
                            new_tab=True,
                        ).classes("text-sm text-sky-600")
                        ui.button(
                            "",
                            icon="delete",
                            on_click=lambda doc_id=row.get("id"): _open_delete(int(doc_id)),
                        ).props("flat dense").classes("text-rose-600")

    render_list()
