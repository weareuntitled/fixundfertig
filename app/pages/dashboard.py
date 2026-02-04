from __future__ import annotations

import os
import tempfile

from ._shared import *
from data import DocumentMeta
from services.blob_storage import blob_storage
from services.documents import resolve_document_path

# Auto generated page renderer

def render_dashboard(session, comp: Company) -> None:
    user = None
    current_user_id = get_current_user_id(session)
    if current_user_id:
        user = session.get(User, current_user_id)
    if user:
        display_name = f"{user.first_name} {user.last_name}".strip()
        greeting_name = display_name or user.email
    else:
        greeting_name = "there"

    doc_items = [
        {
            "title": "March Invoice – ACME Studio",
            "date": "Mar 12, 2024",
            "type": "Invoice",
            "status": "Paid",
            "icon": "description",
            "accent": "bg-blue-100 text-blue-600",
        },
        {
            "title": "Receipt – Office Supplies",
            "date": "Mar 08, 2024",
            "type": "Receipt",
            "status": "Pending",
            "icon": "receipt_long",
            "accent": "bg-orange-100 text-orange-600",
        },
        {
            "title": "Product Shoot – Asset Pack",
            "date": "Mar 05, 2024",
            "type": "Image",
            "status": "Paid",
            "icon": "image",
            "accent": "bg-emerald-100 text-emerald-600",
        },
        {
            "title": "Travel Invoice – April",
            "date": "Apr 02, 2024",
            "type": "PDF",
            "status": "Pending",
            "icon": "picture_as_pdf",
            "accent": "bg-slate-100 text-slate-700",
        },
        {
            "title": "Studio Rent – Q1",
            "date": "Mar 28, 2024",
            "type": "Invoice",
            "status": "Paid",
            "icon": "description",
            "accent": "bg-violet-100 text-violet-600",
        },
        {
            "title": "Client Receipt – Catering",
            "date": "Mar 23, 2024",
            "type": "Receipt",
            "status": "Pending",
            "icon": "receipt_long",
            "accent": "bg-amber-100 text-amber-700",
        },
        {
            "title": "Workshop Photos – Batch 4",
            "date": "Mar 19, 2024",
            "type": "Image",
            "status": "Paid",
            "icon": "image",
            "accent": "bg-teal-100 text-teal-700",
        },
        {
            "title": "Insurance Policy – Renewal",
            "date": "Mar 15, 2024",
            "type": "PDF",
            "status": "Pending",
            "icon": "picture_as_pdf",
            "accent": "bg-rose-100 text-rose-600",
        },
    ]

    def _assign_item_ids() -> None:
        invoice_rows = session.exec(
            select(Invoice)
            .join(Customer, Invoice.customer_id == Customer.id)
            .where(Customer.company_id == comp.id)
            .order_by(Invoice.id.desc())
        ).all()
        document_rows = session.exec(
            select(Document)
            .where(Document.company_id == int(comp.id or 0))
            .order_by(Document.id.desc())
        ).all()
        invoice_index = 0
        document_index = 0
        for item in doc_items:
            if item["type"] == "Invoice":
                if invoice_index < len(invoice_rows):
                    item["invoice_id"] = int(invoice_rows[invoice_index].id)
                    invoice_index += 1
            else:
                if document_index < len(document_rows):
                    item["document_id"] = int(document_rows[document_index].id)
                    document_index += 1

    _assign_item_ids()

    status_badge = {
        "Paid": "bg-emerald-100 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full text-xs font-semibold",
        "Pending": "bg-orange-100 text-orange-700 border border-orange-200 px-2 py-0.5 rounded-full text-xs font-semibold",
    }

    filters = ["All", "Paid", "Pending"]
    active_filter = {"value": "All"}

    def _open_page(page: str) -> None:
        app.storage.user["page"] = page
        ui.navigate.to("/")

    def _open_invoice(invoice_id: int | None) -> None:
        if not invoice_id:
            ui.notify("Keine Rechnung verknüpft. Öffne die Liste, um eine Rechnung auszuwählen.", color="orange")
            _open_page("invoices")
            return
        _open_invoice_detail(int(invoice_id))

    def _open_document(document_id: int | None) -> None:
        if not document_id:
            ui.notify("Kein Dokument verknüpft. Öffne die Dokumente-Liste, um ein Dokument auszuwählen.", color="orange")
            _open_page("documents")
            return
        open_url = f"/api/documents/{int(document_id)}/file"
        ui.run_javascript(f"window.open('{open_url}', '_blank')")

    def _run_export(action, label: str, ids: list[int] | None = None) -> None:
        ui.notify("Wird vorbereitet…")
        try:
            with get_session() as s:
                if ids:
                    result = action(s, comp.id, ids)
                else:
                    result = action(s, comp.id)
            if isinstance(result, (bytes, bytearray)):
                suffix = ".zip" if bytes(result[:4]) == b"PK\x03\x04" else ".csv"
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="export_")
                temp_path = temp_file.name
                temp_file.write(result)
                temp_file.close()
                ui.download(temp_path)
                ui.notify(f"{label} bereit", color="green")
                return
            if result and os.path.exists(result):
                ui.download(result)
                ui.notify(f"{label} bereit", color="green")
                return
            ui.notify("Export fehlgeschlagen", color="red")
        except Exception as e:
            ui.notify(f"Fehler: {e}", color="red")

    def _export_invoices(invoice_id: int | None) -> None:
        ids = [int(invoice_id)] if invoice_id else None
        _run_export(export_invoices_pdf_zip, "Rechnungen", ids)

    def _export_documents(document_id: int | None) -> None:
        ids = [int(document_id)] if document_id else None
        _run_export(export_documents_zip, "Dokumente", ids)

    def _send_invoice(invoice_id: int | None, *, reminder: bool = False) -> None:
        if not invoice_id:
            ui.notify("Keine Rechnung verknüpft. Öffne die Liste, um eine Rechnung zu senden.", color="orange")
            _open_page("invoices")
            return
        try:
            invoice = session.get(Invoice, int(invoice_id))
            if not invoice:
                ui.notify("Rechnung nicht gefunden.", color="red")
                return
            customer = session.get(Customer, int(invoice.customer_id)) if invoice.customer_id else None
            send_invoice_email(comp, customer, invoice)
            ui.notify("Mahnung vorbereitet" if reminder else "Senden vorbereitet", color="green")
        except Exception as e:
            ui.notify(f"Fehler: {e}", color="red")

    def _delete_document(document_id: int | None) -> None:
        if not document_id:
            ui.notify("Kein Dokument verknüpft. Öffne die Dokumente-Liste, um ein Dokument zu löschen.", color="orange")
            _open_page("documents")
            return
        try:
            with get_session() as s:
                document = s.get(Document, int(document_id))
                if not document:
                    ui.notify("Dokument nicht gefunden.", color="red")
                    return
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
            ui.notify("Dokument gelöscht", color="green")
        except Exception as e:
            logger.exception("Dashboard delete failed", extra={"document_id": document_id})
            ui.notify(f"Fehler: {e}", color="red")

    def _delete_invoice(invoice_id: int | None) -> None:
        if not invoice_id:
            ui.notify("Keine Rechnung verknüpft. Öffne die Liste, um eine Rechnung zu löschen.", color="orange")
            _open_page("invoices")
            return
        try:
            ok, err = delete_invoice(int(invoice_id))
            if not ok:
                ui.notify(err or "Löschen fehlgeschlagen", color="red")
                return
            ui.notify("Rechnung gelöscht", color="green")
        except Exception as e:
            ui.notify(f"Fehler: {e}", color="red")

    delete_state = {"kind": None, "id": None, "label": ""}

    with ui.dialog() as delete_dialog:
        with ui.card().classes(C_CARD + " p-5 w-[520px] max-w-[92vw]"):
            ui.label("Löschen").classes(C_SECTION_TITLE)
            delete_label = ui.label("Willst du dieses Element wirklich löschen?").classes("text-sm text-slate-600")
            with ui.row().classes("justify-end gap-2 mt-3 w-full"):
                ui.button("Abbrechen", on_click=delete_dialog.close).classes(C_BTN_SEC)

                def _confirm_delete() -> None:
                    if not delete_state["id"] or not delete_state["kind"]:
                        delete_dialog.close()
                        return
                    if delete_state["kind"] == "invoice":
                        _delete_invoice(int(delete_state["id"]))
                    else:
                        _delete_document(int(delete_state["id"]))
                    delete_dialog.close()

                ui.button("Löschen", on_click=_confirm_delete).classes("bg-rose-600 text-white hover:bg-rose-700")

    def _open_delete(kind: str, item_id: int | None, label: str) -> None:
        if not item_id:
            ui.notify("Kein Element verknüpft. Bitte in der Liste auswählen.", color="orange")
            _open_page("invoices" if kind == "invoice" else "documents")
            return
        delete_state["kind"] = kind
        delete_state["id"] = int(item_id)
        delete_label.text = label
        delete_dialog.open()

    def _actions_for_item(item: dict) -> list[tuple[str, callable]]:
        item_type = item.get("type")
        if item_type == "Invoice":
            invoice_id = item.get("invoice_id")
            return [
                ("Öffnen", lambda: _open_invoice(invoice_id)),
                ("Zum Ordner exportieren", lambda: _export_invoices(invoice_id)),
                ("Senden", lambda: _send_invoice(invoice_id)),
                ("Mahnen", lambda: _send_invoice(invoice_id, reminder=True)),
                ("Löschen", lambda: _open_delete("invoice", invoice_id, "Rechnung löschen?")),
            ]

        document_id = item.get("document_id")
        actions = [
            ("Öffnen", lambda: _open_document(document_id)),
            ("Zum Ordner exportieren", lambda: _export_documents(document_id)),
        ]
        if item_type in {"Receipt", "PDF"}:
            actions.extend(
                [
                    (
                        "Senden",
                        lambda: (
                            ui.notify(
                                "Senden ist nur für Rechnungen verfügbar. Öffne die Dokumente-Liste für Uploads.",
                                color="orange",
                            ),
                            _open_page("documents"),
                        ),
                    ),
                    (
                        "Mahnen",
                        lambda: ui.notify("Mahnungen sind nur für Rechnungen verfügbar.", color="orange"),
                    ),
                ]
            )
        actions.append(("Löschen", lambda: _open_delete("document", document_id, "Dokument löschen?")))
        return actions

    def set_filter(value: str) -> None:
        active_filter["value"] = value
        render_cards.refresh()

    with ui.row().classes("w-full items-center justify-between mb-6 flex-col lg:flex-row gap-4"):
        with ui.column().classes("gap-1"):
            ui.label("Dashboard").classes("text-3xl font-bold tracking-tight text-slate-900")
            ui.label(f"Welcome back, {greeting_name}").classes("text-sm text-slate-500")
        with ui.row().classes(
            "rounded-full bg-white/80 backdrop-blur-md border border-white/60 shadow-sm p-1 gap-1"
        ):
            for value in filters:
                is_active = active_filter["value"] == value
                cls = (
                    "px-4 py-1.5 rounded-full text-sm font-semibold transition-all "
                    + ("bg-slate-900 text-white shadow-sm" if is_active else "text-slate-600 hover:text-slate-900")
                )
                ui.button(value, on_click=lambda v=value: set_filter(v)).props("flat dense").classes(cls)

    @ui.refreshable
    def render_cards() -> None:
        if active_filter["value"] == "All":
            visible_items = doc_items
        else:
            visible_items = [item for item in doc_items if item["status"] == active_filter["value"]]

        with ui.element("div").classes("w-full grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6"):
            for item in visible_items:
                with ui.element("div").classes(
                    "group relative bg-white rounded-[24px] p-5 shadow-sm hover:-translate-y-1 "
                    "hover:shadow-2xl transition-all duration-200"
                ):
                    with ui.button(icon="more_horiz").props("flat round dense").classes(
                        "absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition text-slate-500 hover:text-slate-800"
                    ):
                        with ui.menu().props("auto-close"):
                            for label, handler in _actions_for_item(item):
                                ui.menu_item(label, on_click=handler)
                    with ui.column().classes("gap-4"):
                        with ui.element("div").classes(
                            "h-28 rounded-2xl bg-slate-50 flex items-center justify-center"
                        ):
                            with ui.element("div").classes(
                                f"w-16 h-16 rounded-full {item['accent']} flex items-center justify-center"
                            ):
                                ui.icon(item["icon"]).classes("text-3xl")
                        with ui.column().classes("gap-2"):
                            ui.label(item["title"]).classes("text-base font-semibold text-slate-900 truncate")
                            with ui.row().classes("items-center justify-between gap-2"):
                                ui.label(item["date"]).classes("text-xs text-slate-500")
                                ui.label(item["type"]).classes(
                                    "bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded-full text-xs font-semibold"
                                )
                            ui.label(item["status"]).classes(status_badge[item["status"]])

    render_cards()
