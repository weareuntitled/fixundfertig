from __future__ import annotations

from datetime import date
from typing import Any

from nicegui import ui

from renderer import render_invoice_to_pdf_base64

from .invoice_utils import build_invoice_preview_html


def _get(obj: Any, *names: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        for n in names:
            if n in obj and obj[n] not in (None, ""):
                return obj[n]
        return default
    for n in names:
        if hasattr(obj, n):
            v = getattr(obj, n)
            if v not in (None, ""):
                return v
    return default


def render_invoice_create(session: Any, comp: Any) -> None:
    ui.label("Rechnung erstellen").classes("text-2xl font-semibold mb-4")

    today = date.today().isoformat()

    customers = _get(comp, "customers", default=[])
    if not isinstance(customers, list):
        customers = []

    # NiceGUI ui.select supports dict (label->value) reliably
    if customers:
        customer_options = {str(_get(c, "name", default=f"Kunde {i+1}")): i for i, c in enumerate(customers)}
        customer_default = 0
    else:
        customer_options = {"Keine Kunden gefunden": None}
        customer_default = None

    items: list[dict] = []
    service_from = today
    service_to = today

    with ui.row().classes("w-full gap-6 items-start flex-col md:flex-row md:flex-nowrap"):
        # LEFT column (35%)
        with ui.column().classes("w-full md:w-[35%] gap-4"):
            with ui.card().classes("w-full p-4"):
                ui.label("Stammdaten").classes("text-lg font-semibold mb-2")

                customer_select = ui.select(
                    options=customer_options,
                    value=customer_default,
                    label="Kunde",
                ).classes("w-full")

                title_input = ui.input("Titel", value="Rechnung").classes("w-full")

                invoice_date_input = ui.input("Rechnungsdatum", value=today).props("readonly").classes("w-full")
                with invoice_date_input.add_slot("append"):
                    ui.icon("event").classes("cursor-pointer")

                invoice_date_menu = ui.menu().props("no-parent-event")
                with invoice_date_menu:
                    invoice_date_picker = ui.date(value=today).props('mask="YYYY-MM-DD"')
                    ui.button("OK", on_click=invoice_date_menu.close).props("flat color=primary")

                invoice_date_input.on("click", lambda: invoice_date_menu.open())

                def _invoice_date_changed(e) -> None:
                    invoice_date_input.value = e.value
                    update_preview()

                invoice_date_picker.on("update:modelValue", _invoice_date_changed)

                service_input = ui.input("Leistungszeitraum", value=f"{today} bis {today}").props("readonly").classes("w-full")
                with service_input.add_slot("append"):
                    ui.icon("event").classes("cursor-pointer")

                service_menu = ui.menu().props("no-parent-event")
                with service_menu:
                    service_picker = ui.date(value={"from": today, "to": today}).props('mask="YYYY-MM-DD" range')
                    ui.button("OK", on_click=service_menu.close).props("flat color=primary")

                service_input.on("click", lambda: service_menu.open())

                def _service_changed(e) -> None:
                    nonlocal service_from, service_to
                    v = e.value or {}
                    service_from = v.get("from", today)
                    service_to = v.get("to", today)
                    service_input.value = f"{service_from} bis {service_to}"
                    update_preview()

                service_picker.on("update:modelValue", _service_changed)

                # FIX: use switch (boolean), NOT ui.toggle (choice)
                vat_switch = ui.switch("USt berechnen", value=False).classes("mt-2")
                if getattr(comp, "is_small_business", False):
                    vat_switch.props("disable")
                ui.label("Kleinunternehmer: USt wird automatisch nicht ausgewiesen.").classes("text-sm text-gray-500")

            with ui.card().classes("w-full p-4"):
                ui.label("Einleitungstext").classes("text-lg font-semibold mb-2")
                intro_input = ui.textarea(
                    value="Vielen Dank für Ihren Auftrag. Hiermit berechne ich die folgenden Leistungen."
                ).classes("w-full")
                intro_input.props("autogrow")

            with ui.card().classes("w-full p-4"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Positionen").classes("text-lg font-semibold")
                    add_btn = ui.button("Position hinzufügen").props("outline color=primary")

                columns = [
                    {"name": "description", "label": "Beschreibung", "field": "description", "align": "left"},
                    {"name": "quantity", "label": "Menge", "field": "quantity", "align": "right"},
                    {"name": "unit_price", "label": "Preis", "field": "unit_price", "align": "right"},
                    {"name": "tax_rate", "label": "USt", "field": "tax_rate", "align": "right"},
                ]
                table = ui.table(columns=columns, rows=items, row_key="id").classes("w-full mt-3")
                table.props("hide-pagination :pagination='{rowsPerPage:0}'")

                dialog = ui.dialog()
                with dialog:
                    with ui.card().classes("w-[min(680px,95vw)] p-4"):
                        ui.label("Position").classes("text-lg font-semibold mb-2")
                        d_desc = ui.textarea("Beschreibung", value="").classes("w-full")
                        d_desc.props("autogrow")
                        d_qty = ui.number("Menge", value=1, min=0, step=1).classes("w-full")
                        d_price = ui.number("Einzelpreis", value=0.0, min=0, step=0.01).classes("w-full")
                        d_tax = ui.number("USt in %", value=0, min=0, step=1).classes("w-full")

                        with ui.row().classes("w-full justify-end gap-2 mt-4"):
                            ui.button("Abbrechen", on_click=dialog.close).props("flat color=primary")

                            def _add_item() -> None:
                                new_item = {
                                    "id": f"i{len(items)+1}",
                                    "description": d_desc.value or "",
                                    "quantity": float(d_qty.value or 0),
                                    "unit_price": float(d_price.value or 0),
                                    "tax_rate": float(d_tax.value or 0),
                                }
                                items.append(new_item)
                                table.rows = items
                                dialog.close()
                                update_preview()

                            ui.button("Hinzufügen", on_click=_add_item).props("unelevated color=primary")

                add_btn.on("click", dialog.open)

                ui.button(
                    "Rechnung finalisieren",
                    on_click=lambda: ui.notify("Finalize Hook fehlt", type="warning"),
                ).props("unelevated color=primary").classes("mt-4")

        # RIGHT column preview
        with ui.column().classes("w-full md:flex-1"):
            with ui.card().classes("w-full p-4 md:sticky md:top-4"):
                ui.label("Vorschau").classes("text-lg font-semibold mb-2")
                preview_summary = ui.html("").classes("w-full mb-3")
                preview_frame = (
                    ui.element("iframe")
                    .props("style='width:100%;height:78vh;border:0;'")
                    .classes("w-full")
                )

    def _current_customer_obj() -> Any:
        idx = customer_select.value
        if idx is None:
            return None
        try:
            return customers[int(idx)]
        except Exception:
            return None

    def update_preview() -> None:
        vat_enabled = bool(vat_switch.value)
        vat_rate = max((float(_get(it, "tax_rate", default=0) or 0) for it in items), default=0.0)
        net, vat, gross = compute_invoice_totals(items, vat_enabled, vat_rate)

        invoice = {
            "title": title_input.value or "Rechnung",
            "invoice_number": f"INV-{invoice_date_input.value}",
            "invoice_date": invoice_date_input.value,
            "service_from": service_from,
            "service_to": service_to,
            "intro_text": intro_input.value or "",
            "customer": _current_customer_obj(),
            "items": items,
            "show_tax": vat_enabled,
            "tax_rate": vat_rate,
            "kleinunternehmer_note": "Als Kleinunternehmer im Sinne von § 19 UStG wird keine Umsatzsteuer berechnet.",
            "totals": {"net": net, "vat": vat, "gross": gross},
        }

        preview_html = build_invoice_preview_html(invoice)
        try:
            pdf_b64 = render_invoice_to_pdf_base64(invoice, comp)
            preview_frame.props(f"src='data:application/pdf;base64,{pdf_b64}'")
            preview_summary.content = build_invoice_preview_html(invoice)
        except Exception as ex:
            preview_frame.props("src=''")
            preview_summary.content = (
                "<div class='text-red-600'>PDF Fehler: "
                f"{ex}</div>{build_invoice_preview_html(invoice)}"
            )

    customer_select.on("update:modelValue", lambda e: update_preview())
    title_input.on("update:value", lambda e: update_preview())
    intro_input.on("update:value", lambda e: update_preview())
    vat_switch.on("update:modelValue", lambda e: update_preview())

    update_preview()
