from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException

from ._shared import *
from data import Document, DocumentMeta
from services.blob_storage import blob_storage, build_document_key
from services.documents import (
    build_document_record,
    document_matches_filters,
    resolve_document_path,
    serialize_document,
    validate_document_upload,
)


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
        "doc_date": "",
        "amount_total": None,
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

    def _export_documents(selected_ids: set[int]) -> None:
        if not selected_ids:
            ui.notify("Bitte Dokumente auswählen.", color="orange")
            return
        items = [doc for doc in _filter_documents(_load_documents()) if int(doc.id or 0) in selected_ids]
        if not items:
            ui.notify("Keine Dokumente zum Export.", color="orange")
            return
        meta_map = _load_meta_map({int(doc.id or 0) for doc in items})
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", encoding="utf-8", newline="") as temp:
            writer = csv.writer(temp, delimiter=";")
            writer.writerow(
                [
                    "Rechnungsdatum",
                    "Vendor",
                    "Netto",
                    "USt",
                    "Brutto",
                    "Währung",
                    "Dokumenttyp",
                    "Vendor Adresse",
                    "Vendor Straße",
                    "Vendor PLZ",
                    "Vendor Stadt",
                    "Vendor Land",
                    "Vendor Steuernummer",
                    "Vendor USt-Id",
                    "Dokument",
                    "Beschreibung",
                    "ID",
                ]
            )
            for doc in items:
                payload = meta_map.get(int(doc.id or 0), {})
                extracted = _extract_payload(payload)
                invoice_date = _string_value(
                    _value_from_sources(payload, extracted, "invoice_date", "doc_date")
                    or doc.doc_date
                    or (_doc_created_at(doc).date().isoformat() if _doc_created_at(doc) != datetime.min else "")
                )
                vendor_name = _string_value(
                    _vendor_value(payload, extracted, ["vendor_name", "vendor", "supplier_name", "supplier"], ["name"])
                    or doc.vendor
                )
                currency = _string_value(
                    _value_from_sources(payload, extracted, "currency", "currency_code") or doc.currency
                )
                net_amount = _parse_amount(
                    _value_from_sources(payload, extracted, "net_amount", "amount_net", "net")
                )
                vat_amount = _parse_amount(
                    _value_from_sources(payload, extracted, "vat_amount", "amount_vat", "tax_amount", "vat")
                )
                gross_amount = _parse_amount(
                    _value_from_sources(payload, extracted, "gross_amount", "amount_total", "total", "gross")
                )
                if gross_amount is None and doc.amount_total is not None:
                    gross_amount = float(doc.amount_total)
                if net_amount is None and gross_amount is not None and vat_amount is not None:
                    net_amount = gross_amount - vat_amount
                if vat_amount is None and gross_amount is not None and net_amount is not None:
                    vat_amount = gross_amount - net_amount
                document_type = _string_value(
                    _value_from_sources(payload, extracted, "document_type", "doc_type", "type") or doc.doc_type
                )
                vendor_address = _string_value(
                    _vendor_value(payload, extracted, ["vendor_address", "address"], ["address", "address_line1"])
                )
                vendor_street = _string_value(
                    _vendor_value(payload, extracted, ["vendor_street", "street"], ["street", "address_line1"])
                )
                vendor_zip = _string_value(
                    _vendor_value(payload, extracted, ["vendor_zip", "postal_code", "zip"], ["zip", "postal_code"])
                )
                vendor_city = _string_value(
                    _vendor_value(payload, extracted, ["vendor_city", "city"], ["city"])
                )
                vendor_country = _string_value(
                    _vendor_value(payload, extracted, ["vendor_country", "country"], ["country"])
                )
                vendor_tax_id = _string_value(
                    _vendor_value(
                        payload,
                        extracted,
                        ["vendor_tax_id", "tax_id", "tax_number"],
                        ["tax_id", "tax_number"],
                    )
                )
                vendor_vat_id = _string_value(
                    _vendor_value(
                        payload,
                        extracted,
                        ["vendor_vat_id", "vat_id", "vat_number", "ust_id", "ustid"],
                        ["vat_id", "vat_number", "ust_id", "ustid"],
                    )
                )
                writer.writerow(
                    [
                        invoice_date,
                        vendor_name,
                        f"{net_amount:.2f}" if net_amount is not None else "",
                        f"{vat_amount:.2f}" if vat_amount is not None else "",
                        f"{gross_amount:.2f}" if gross_amount is not None else "",
                        currency,
                        document_type,
                        vendor_address,
                        vendor_street,
                        vendor_zip,
                        vendor_city,
                        vendor_country,
                        vendor_tax_id,
                        vendor_vat_id,
                        doc.original_filename or doc.title or "Dokument",
                        doc.description or "",
                        str(doc.id or ""),
                    ]
                )
        ui.download(temp.name)
        ui.notify("Export bereit.", color="green")

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
        currency = upload_state["currency"].strip() if upload_state["currency"] else ""
        vendor = upload_state["vendor"].strip() if upload_state["vendor"] else ""
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
                    doc_date=doc_date,
                    amount_total=amount_total,
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
                "Belegdatum",
                on_change=lambda e: upload_state.__setitem__("doc_date", e.value or ""),
            ).props("type=date").classes(C_INPUT + " w-full")
            ui.number(
                "Betrag",
                on_change=lambda e: upload_state.__setitem__("amount_total", e.value),
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
                    on_click=lambda: upload_input.upload()
                    if upload_input.value
                    else ui.notify("Bitte Datei auswählen.", color="orange"),
                ).classes(C_BTN_PRIM)
                ui.button("Schließen", on_click=upload_dialog.close).classes(C_BTN_SEC)

    selected_ids: set[int] = set()
    export_button = None
    upload_button = None

    def _update_action_buttons() -> None:
        if export_button and upload_button:
            has_selection = bool(selected_ids)
            export_button.visible = has_selection
            upload_button.visible = not has_selection

    @ui.refreshable
    def render_filters():
        with ui.row().classes("w-full items-center gap-3 flex-wrap mb-2"):
            ui.label("Dokumente").classes(C_PAGE_TITLE)
            ui.space()
            nonlocal export_button, upload_button
            export_button = ui.button(
                "Export",
                icon="download",
                on_click=lambda: _export_documents(selected_ids),
            ).classes(C_BTN_SEC)
            upload_button = ui.button("Upload", icon="upload", on_click=upload_dialog.open).classes(C_BTN_PRIM)
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
    meta_state = {"title": "", "raw": "", "line_items": "", "flags": ""}

    def _format_json(value: str, *, redact_payload: bool = False) -> str:
        if not value:
            return ""
        try:
            payload = json.loads(value)
        except Exception:
            return value
        if redact_payload and isinstance(payload, dict) and "file_base64" in payload:
            payload = {**payload, "file_base64": "<redacted>"}
        return json.dumps(payload, ensure_ascii=False, indent=2)

    with ui.dialog() as meta_dialog:
        with ui.card().classes(C_CARD + " p-5 w-[760px] max-w-[95vw]"):
            ui.label("Dokument-Metadaten").classes(C_SECTION_TITLE)
            meta_title = ui.label("").classes("text-sm text-slate-500")
            ui.label("Payload (bereinigt)").classes("text-xs font-semibold text-slate-500 mt-3")
            raw_area = ui.textarea(value="").props("readonly").classes("w-full text-xs font-mono min-h-[140px]")
            ui.label("Line Items").classes("text-xs font-semibold text-slate-500 mt-3")
            line_area = ui.textarea(value="").props("readonly").classes("w-full text-xs font-mono min-h-[120px]")
            ui.label("Compliance Flags").classes("text-xs font-semibold text-slate-500 mt-3")
            flags_area = ui.textarea(value="").props("readonly").classes("w-full text-xs font-mono min-h-[120px]")
            with ui.row().classes("justify-end mt-4"):
                ui.button("Schließen", on_click=meta_dialog.close).classes(C_BTN_SEC)

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
                            storage_path = resolve_document_path(document.storage_path)
                            if storage_path and os.path.exists(storage_path):
                                try:
                                    os.remove(storage_path)
                                except OSError:
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

    def _parse_meta_payload(meta: DocumentMeta | None) -> dict:
        if not meta or not meta.raw_payload_json:
            return {}
        try:
            payload = json.loads(meta.raw_payload_json)
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _extract_payload(payload: dict) -> dict:
        extracted = payload.get("extracted") if isinstance(payload, dict) else None
        return extracted if isinstance(extracted, dict) else {}

    def _load_meta_map(doc_ids: set[int]) -> dict[int, dict]:
        if not doc_ids:
            return {}
        metas = session.exec(select(DocumentMeta).where(DocumentMeta.document_id.in_(list(doc_ids)))).all()
        return {int(meta.document_id): _parse_meta_payload(meta) for meta in metas}

    def _value_from_sources(payload: dict, extracted: dict, *keys: str) -> object:
        for source in (extracted, payload):
            if not isinstance(source, dict):
                continue
            for key in keys:
                value = source.get(key)
                if value not in (None, ""):
                    return value
        return None

    def _vendor_info(payload: dict, extracted: dict) -> dict:
        for source in (extracted, payload):
            if not isinstance(source, dict):
                continue
            vendor_value = source.get("vendor")
            if isinstance(vendor_value, dict):
                return vendor_value
        return {}

    def _vendor_value(payload: dict, extracted: dict, keys: list[str], vendor_keys: list[str]) -> object:
        vendor_info = _vendor_info(payload, extracted)
        for key in vendor_keys:
            value = vendor_info.get(key)
            if value not in (None, ""):
                return value
        return _value_from_sources(payload, extracted, *keys)

    def _parse_amount(value: object) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            raw = str(value).strip()
            if raw.count(",") == 1 and raw.count(".") == 0:
                raw = raw.replace(",", ".")
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _string_value(value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _format_amount_value(amount: float | None, currency: str) -> str:
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
        meta_map = _load_meta_map({int(doc.id or 0) for doc in items})

        with ui.card().classes(C_CARD + " p-0 overflow-hidden w-full"):
            rows = []
            for doc in items:
                row = serialize_document(doc)
                payload = meta_map.get(int(doc.id or 0), {})
                extracted = _extract_payload(payload)
                invoice_date = _string_value(
                    _value_from_sources(payload, extracted, "invoice_date", "doc_date")
                    or doc.doc_date
                    or (row.get("created_at", "")[:10] if row.get("created_at", "") else "")
                )
                vendor_name = _string_value(
                    _vendor_value(payload, extracted, ["vendor_name", "vendor", "supplier_name", "supplier"], ["name"])
                    or doc.vendor
                    or "-"
                )
                currency = _string_value(
                    _value_from_sources(payload, extracted, "currency", "currency_code") or doc.currency
                )
                net_amount = _parse_amount(
                    _value_from_sources(payload, extracted, "net_amount", "amount_net", "net")
                )
                vat_amount = _parse_amount(
                    _value_from_sources(payload, extracted, "vat_amount", "amount_vat", "tax_amount", "vat")
                )
                gross_amount = _parse_amount(
                    _value_from_sources(payload, extracted, "gross_amount", "amount_total", "total", "gross")
                )
                if gross_amount is None and doc.amount_total is not None:
                    gross_amount = float(doc.amount_total)
                if net_amount is None and gross_amount is not None and vat_amount is not None:
                    net_amount = gross_amount - vat_amount
                if vat_amount is None and gross_amount is not None and net_amount is not None:
                    vat_amount = gross_amount - net_amount
                document_type = _string_value(
                    _value_from_sources(payload, extracted, "document_type", "doc_type", "type") or doc.doc_type or "-"
                )
                rows.append(
                    {
                        "id": int(row.get("id") or 0),
                        "invoice_date": invoice_date,
                        "vendor_name": vendor_name,
                        "net_amount": net_amount if net_amount is not None else 0.0,
                        "vat_amount": vat_amount if vat_amount is not None else 0.0,
                        "gross_amount": gross_amount if gross_amount is not None else 0.0,
                        "net_amount_display": _format_amount_value(net_amount, currency),
                        "vat_amount_display": _format_amount_value(vat_amount, currency),
                        "gross_amount_display": _format_amount_value(gross_amount, currency),
                        "document_type": document_type or "-",
                        "open_url": f"/api/documents/{row.get('id')}/file",
                    }
                )

            columns = [
                {"name": "invoice_date", "label": "Rechnungsdatum", "field": "invoice_date", "sortable": True, "align": "left"},
                {"name": "vendor_name", "label": "Vendor", "field": "vendor_name", "sortable": True, "align": "left"},
                {"name": "net_amount", "label": "Netto", "field": "net_amount", "sortable": True, "align": "right"},
                {"name": "vat_amount", "label": "USt", "field": "vat_amount", "sortable": True, "align": "right"},
                {"name": "gross_amount", "label": "Brutto", "field": "gross_amount", "sortable": True, "align": "right"},
                {"name": "document_type", "label": "Typ", "field": "document_type", "sortable": True, "align": "left"},
                {"name": "actions", "label": "", "field": "actions", "sortable": False, "align": "right"},
            ]
            table = ui.table(columns=columns, rows=rows, row_key="id", selection="multiple").classes("w-full")

            def _on_selection(event) -> None:
                selected_rows = event.value or []
                selected_ids.clear()
                selected_ids.update({int(item.get("id") or 0) for item in selected_rows})
                _update_action_buttons()

            table.on("selection", _on_selection)

            def _row_from_slot(slot_obj):
                props = getattr(slot_obj, "props", None)
                if not isinstance(props, dict):
                    return None
                return props.get("row")

            with table.add_slot("body-cell-net_amount") as slot:
                ui.label().bind_text_from(slot, "props.row.net_amount_display", strict=False).classes("text-right")

            with table.add_slot("body-cell-vat_amount") as slot:
                ui.label().bind_text_from(slot, "props.row.vat_amount_display", strict=False).classes("text-right")

            with table.add_slot("body-cell-gross_amount") as slot:
                ui.label().bind_text_from(slot, "props.row.gross_amount_display", strict=False).classes("text-right")

            with table.add_slot("body-cell-actions") as slot:
                def _open_meta_from_slot() -> None:
                    row = _row_from_slot(slot)
                    if not row:
                        ui.notify("Dokument nicht verfügbar.", type="warning")
                        return
                    _open_meta(int(row["id"]))

                def _open_delete_from_slot() -> None:
                    row = _row_from_slot(slot)
                    if not row:
                        ui.notify("Dokument nicht verfügbar.", type="warning")
                        return
                    _open_delete(int(row["id"]))

                def _open_document_from_slot() -> None:
                    row = _row_from_slot(slot)
                    if not row or not row.get("open_url"):
                        ui.notify("Dokument nicht verfügbar.", type="warning")
                        return
                    ui.run_javascript(f"window.open({json.dumps(row['open_url'])}, '_blank')")

                with ui.row().classes("justify-end gap-2"):
                    ui.button(
                        "Meta",
                        on_click=_open_meta_from_slot,
                    ).props("flat dense").classes("text-xs text-slate-600")
                    link = ui.link("Öffnen", "#").classes("text-sm text-sky-600")
                    link.on("click", _open_document_from_slot)
                    ui.button(
                        "",
                        icon="delete",
                        on_click=_open_delete_from_slot,
                    ).props("flat dense").classes("text-rose-600")

    render_filters()
    render_list()
