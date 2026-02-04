from __future__ import annotations

import base64
import time
from datetime import date
from typing import Any

from nicegui import app, ui
from sqlmodel import select

from renderer import PDFInvoiceRenderer

from data import Customer
from logic import finalize_invoice_logic
from .invoice_utils import build_invoice_preview_html, compute_invoice_totals


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

    customer_stmt = (
        select(Customer)
        .where(Customer.company_id == int(comp.id), Customer.archived == False)
        .order_by(Customer.name)
    )
    all_customers = session.exec(customer_stmt).all()
    customers_by_id = {int(c.id): c for c in all_customers if getattr(c, "id", None) is not None}
    new_customer_value = "__new_customer__"
    new_customer_id = app.storage.user.pop("new_customer_id", None)
    if new_customer_id is not None:
        try:
            new_customer_id = int(new_customer_id)
        except (TypeError, ValueError):
            new_customer_id = None
    if new_customer_id is not None and new_customer_id not in customers_by_id:
        extra_stmt = select(Customer).where(
            Customer.company_id == int(comp.id),
            Customer.archived == False,
            Customer.id == int(new_customer_id),
        )
        new_customer = session.exec(extra_stmt).first()
        if new_customer:
            all_customers.append(new_customer)
            customers_by_id[int(new_customer.id)] = new_customer

    # NiceGUI ui.select expects dict[value, label] when using dict options
    def _build_customer_options(filter_text: str | None = None) -> dict[Any, str]:
        customer_options: dict[Any, str] = {}
        normalized = (filter_text or "").strip().lower()
        for i, c in enumerate(all_customers):
            if getattr(c, "id", None) is None:
                continue
            label = str(_get(c, "display_name", "name", default=f"Kunde {i+1}"))
            if normalized and normalized not in label.lower():
                continue
            customer_options[int(c.id)] = label
        customer_options[new_customer_value] = "Neuen Kunden hinzufügen"
        return customer_options

    customer_options = _build_customer_options()
    customer_default = next(iter(customer_options.keys()), new_customer_value)

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
                    with_input=True,
                ).props("use-input").classes("w-full")
                def _filter_customers(e) -> None:
                    filter_text = ""
                    if getattr(e, "value", None) is not None:
                        filter_text = str(e.value or "")
                    elif getattr(e, "args", None):
                        filter_text = str(e.args.get("value", "") or "")
                    current_value = customer_select.value
                    customer_select.options = _build_customer_options(filter_text)
                    if current_value not in customer_select.options:
                        customer_select.value = current_value

                customer_select.on("filter", _filter_customers)

                title_input = ui.input("Titel", value="Rechnung").classes("w-full")

                invoice_date_input = ui.input("Rechnungsdatum", value=today).props("readonly").classes("w-full")
                with invoice_date_input.add_slot("append"):
                    ui.icon("event").classes("cursor-pointer")

                with invoice_date_input:
                    invoice_date_menu = ui.menu().props(
                        "no-parent-event anchor='bottom left' self='top left'"
                    )
                    with invoice_date_menu:
                        invoice_date_picker = ui.date(value=today).props('mask="YYYY-MM-DD"')
                        ui.button("OK", on_click=invoice_date_menu.close).props("flat color=primary")

                invoice_date_input.on("click", lambda: invoice_date_menu.open())

                def _invoice_date_changed(e) -> None:
                    invoice_date_input.value = e.value
                    mark_preview_dirty()

                invoice_date_picker.on("update:modelValue", _invoice_date_changed)

                service_input = ui.input("Leistungszeitraum", value=f"{today} bis {today}").props("readonly").classes("w-full")
                with service_input.add_slot("append"):
                    ui.icon("event").classes("cursor-pointer")

                with service_input:
                    service_menu = ui.menu().props(
                        "no-parent-event anchor='bottom left' self='top left'"
                    )
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
                    mark_preview_dirty()

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
                                mark_preview_dirty()

                            ui.button("Hinzufügen", on_click=_add_item).props("unelevated color=primary")

                add_btn.on("click", dialog.open)

                def _finalize_invoice() -> None:
                    errors: list[str] = []
                    if customer_select.value in (None, new_customer_value):
                        errors.append("Bitte einen Kunden auswählen.")
                    if not (invoice_date_input.value or "").strip():
                        errors.append("Bitte ein Rechnungsdatum setzen.")
                    if not any((str(it.get("description", "")).strip() for it in items)):
                        errors.append("Bitte mindestens eine Position mit Beschreibung hinzufügen.")
                    if errors:
                        for message in errors:
                            ui.notify(message, color="red")
                        return
                    try:
                        new_invoice_id = finalize_invoice_logic(
                            session=session,
                            comp_id=int(comp.id),
                            cust_id=int(customer_select.value),
                            title=title_input.value or "Rechnung",
                            date_str=str(invoice_date_input.value or ""),
                            delivery_str=str(service_input.value or ""),
                            recipient_data={},
                            items=items,
                            ust_enabled=bool(vat_switch.value),
                            intro_text=intro_input.value or "",
                            service_from=service_from,
                            service_to=service_to,
                        )
                        app.storage.user["page"] = "invoice_detail"
                        app.storage.user["invoice_detail_id"] = int(new_invoice_id)
                        ui.navigate.to("/")
                    except Exception as exc:
                        ui.notify(f"Fehler beim Speichern der Rechnung: {exc}", color="red")

                ui.button(
                    "Rechnung finalisieren",
                    on_click=_finalize_invoice,
                ).props("unelevated color=primary").classes("mt-4")

        # RIGHT column preview
        with ui.column().classes("w-full md:flex-1"):
            with ui.card().classes("w-full p-4 md:sticky md:top-4"):
                ui.label("Vorschau").classes("text-lg font-semibold mb-2")
                preview_summary = ui.html("", sanitize=False).classes("w-full mb-3")
                preview_frame = ui.html("", sanitize=False).classes("w-full")

    preview_state = {"dirty": True, "pending": False, "last_change": 0.0}

    def mark_preview_dirty() -> None:
        preview_state["dirty"] = True
        preview_state["pending"] = True
        preview_state["last_change"] = time.monotonic()

    def _current_customer_obj() -> Any:
        selected = customer_select.value
        if selected in (None, new_customer_value):
            return None
        try:
            return customers_by_id.get(int(selected))
        except (TypeError, ValueError):
            return None

    renderer = PDFInvoiceRenderer()

    def update_preview(force_pdf: bool = False) -> None:
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
            "company": comp,
            "customer": _current_customer_obj(),
            "items": items,
            "show_tax": vat_enabled,
            "tax_rate": vat_rate,
            "kleinunternehmer_note": "Als Kleinunternehmer im Sinne von § 19 UStG wird keine Umsatzsteuer berechnet.",
            "totals": {"net": net, "vat": vat, "gross": gross},
        }

        preview_html = build_invoice_preview_html(invoice)
        preview_summary.content = preview_html
        if not (force_pdf or preview_state["dirty"]):
            return
        preview_state["dirty"] = False
        try:
            pdf_bytes = renderer.render(invoice, template_id=None)
            pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
            preview_frame.content = (
                "<iframe "
                f"src=\"data:application/pdf;base64,{pdf_b64}\" "
                "style=\"width:100%;height:78vh;border:0;\"></iframe>"
            )
        except Exception as ex:
            preview_frame.content = ""
            preview_summary.content = (
                "<div class='text-orange-700'>PDF Fehler: "
                f"{ex}</div>{preview_html}"
            )

    def _is_new_customer_selection(value: Any) -> bool:
        if value == new_customer_value:
            return True
        if isinstance(value, str) and value.strip().lower() == "neuen kunden hinzufügen":
            return True
        return False

    def _on_customer_change(e) -> None:
        if _is_new_customer_selection(e.value):
            app.storage.user["return_page"] = "invoice_create"
            app.storage.user["return_invoice_draft_id"] = app.storage.user.get("invoice_draft_id")
            app.storage.user["page"] = "customer_new"
            ui.navigate.to("/")
            return
        mark_preview_dirty()

    def debounce_tick() -> None:
        if not preview_state["pending"]:
            return
        if time.monotonic() - preview_state["last_change"] < 0.6:
            return
        preview_state["pending"] = False
        update_preview()

    customer_select.on("update:modelValue", _on_customer_change)
    title_input.on("update:value", lambda e: mark_preview_dirty())
    intro_input.on("update:value", lambda e: mark_preview_dirty())
    vat_switch.on("update:modelValue", lambda e: mark_preview_dirty())
    ui.timer(0.1, debounce_tick)

    if new_customer_id is not None:
        customer_select.value = new_customer_id
        mark_preview_dirty()

    update_preview(force_pdf=True)
