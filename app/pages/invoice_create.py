from __future__ import annotations

import time
from datetime import date
from typing import Any

from nicegui import app, ui
from sqlmodel import select

from renderer import PDFInvoiceRenderer
from data import Customer, InvoiceStatus
from invoice_customer_merge import merge_customer_from_new_id, parse_new_customer_id
from logic import finalize_invoice_logic
from styles import C_INPUT, C_PAGE_TITLE, STYLE_SECTION_TITLE, STYLE_TEXT_SUBTLE
from ui_components import (
    ff_btn_primary, ff_btn_secondary, ff_card, ff_input,
    settings_card, settings_grid, settings_two_column_layout,
)
from ._shared import get_session, go_app_page

from .invoice_create_customer_dialog import create_new_customer_dialog
from .invoice_create_preview import build_preview_invoice, render_preview_html, render_preview_pdf_frame


def render_invoice_create(session: Any, comp: Any) -> None:
    ui.label("Rechnung erstellen").classes(C_PAGE_TITLE)
    ui.label("Kunde, Zeitraum und Positionen erfassen, rechts die Vorschau kontrollieren.").classes(
        f"{STYLE_TEXT_SUBTLE} mb-4"
    )

    today = date.today().isoformat()
    card_cls = "w-full"
    card_cls_sticky = "w-full md:sticky md:top-4"
    card_title_cls = f"{STYLE_SECTION_TITLE} mb-2"

    customer_stmt = (
        select(Customer)
        .where(Customer.company_id == int(comp.id), Customer.archived == False)
        .order_by(Customer.name)
    )
    all_customers = list(session.exec(customer_stmt).all())
    customers_by_id = {int(c.id): c for c in all_customers if getattr(c, "id", None) is not None}
    new_customer_value = "__new_customer__"
    new_customer_id = parse_new_customer_id(app.storage.user.pop("new_customer_id", None))
    merge_customer_from_new_id(session, comp_id=int(comp.id), all_customers=all_customers,
                               customers_by_id=customers_by_id, new_customer_id=new_customer_id)

    def _build_customer_options(filter_text: str | None = None) -> dict[Any, str]:
        opts: dict[Any, str] = {}
        normalized = (filter_text or "").strip().lower()
        for i, c in enumerate(all_customers):
            if getattr(c, "id", None) is None:
                continue
            label = str(getattr(c, "display_name", None) or getattr(c, "name", f"Kunde {i+1}"))
            if normalized and normalized not in label.lower():
                continue
            opts[int(c.id)] = label
        opts[new_customer_value] = "+ Neuen Kunden anlegen"
        return opts

    customer_options = _build_customer_options()
    customer_default = next(iter(customers_by_id.keys()), None)
    items: list[dict] = []
    service_from = today
    service_to = today
    preview_summary = preview_frame = preview_summary_mobile = preview_frame_mobile = None

    def _on_customer_saved(new_id, _comp):
        nonlocal all_customers, customers_by_id
        with get_session() as s:
            stmt = select(Customer).where(Customer.company_id == int(_comp.id), Customer.archived == False).order_by(Customer.name)
            all_customers = list(s.exec(stmt).all())
            customers_by_id = {int(cu.id): cu for cu in all_customers if getattr(cu, "id", None) is not None}
        customer_select.options = _build_customer_options()
        if new_id is not None:
            customer_select.value = new_id

    new_customer_dialog = create_new_customer_dialog(comp, on_saved=_on_customer_saved)

    with ui.row().classes("w-full gap-6 items-start flex-col md:flex-row md:flex-nowrap"):
        with ui.column().classes("w-full md:w-1/3 gap-4"):
            with settings_card("Stammdaten"):
                customer_select = ui.select(options=customer_options, value=customer_default, label="Kunde", with_input=True).props("outlined dense use-input").classes(C_INPUT)

                def _filter_customers(e) -> None:
                    ft = str(e.value or "") if getattr(e, "value", None) is not None else str(e.args.get("value", "") or "") if getattr(e, "args", None) else ""
                    cv = customer_select.value
                    customer_select.options = _build_customer_options(ft)
                    if cv not in customer_select.options:
                        customer_select.value = cv

                customer_select.on("filter", _filter_customers)
                title_input = ui.input("Titel", value="Rechnung").props("outlined dense").classes(C_INPUT)
                invoice_date_input = ui.input("Rechnungsdatum", value=today).props("outlined dense readonly").classes(C_INPUT)
                with invoice_date_input.add_slot("append"):
                    ui.icon("event").classes("cursor-pointer")
                with invoice_date_input:
                    invoice_date_menu = ui.menu().props("no-parent-event anchor='bottom left' self='top left'")
                    with invoice_date_menu:
                        invoice_date_picker = ui.date(value=today).props('mask="YYYY-MM-DD"')
                        ff_btn_secondary("OK", on_click=invoice_date_menu.close, props="dense")
                invoice_date_input.on("click", lambda: invoice_date_menu.open())
                invoice_date_picker.on("update:modelValue", lambda e: (setattr(invoice_date_input, 'value', e.value), mark_preview_dirty()))

                service_input = ui.input("Leistungszeitraum", value=f"{today} bis {today}").props("outlined dense readonly").classes(C_INPUT)
                with service_input.add_slot("append"):
                    ui.icon("event").classes("cursor-pointer")
                with service_input:
                    service_menu = ui.menu().props("no-parent-event anchor='bottom left' self='top left'")
                    with service_menu:
                        service_picker = ui.date(value={"from": today, "to": today}).props('mask="YYYY-MM-DD" range')
                        ff_btn_secondary("OK", on_click=service_menu.close, props="dense")
                service_input.on("click", lambda: service_menu.open())

                def _service_changed(e) -> None:
                    nonlocal service_from, service_to
                    v = e.value or {}
                    service_from, service_to = v.get("from", today), v.get("to", today)
                    service_input.value = f"{service_from} bis {service_to}"
                    mark_preview_dirty()

                service_picker.on("update:modelValue", _service_changed)
                vat_switch = ui.switch("USt berechnen", value=False).classes("mt-2")
                if getattr(comp, "is_small_business", False):
                    vat_switch.props("disable")
                ui.label("Kleinunternehmer: USt wird automatisch nicht ausgewiesen.").classes(STYLE_TEXT_SUBTLE)

            with settings_card("Einleitungstext"):
                intro_input = ui.textarea(value="Vielen Dank für Ihren Auftrag. Hiermit berechne ich die folgenden Leistungen.").props("outlined dense").classes(C_INPUT)
                intro_input.props("autogrow")

            with settings_card("Positionen"):
                with ui.row().classes("w-full items-center justify-between flex-col md:flex-row gap-2"):
                    ui.label("Positionen").classes(STYLE_SECTION_TITLE)
                    add_btn = ff_btn_secondary("Position hinzufügen").classes("w-full md:w-auto")
                ui.label("Tipp: Nach rechts wischen, um alle Spalten zu sehen.").classes("text-xs text-slate-500 md:hidden")

                columns = [
                    {"name": "description", "label": "Beschreibung", "field": "description", "align": "left"},
                    {"name": "quantity", "label": "Menge", "field": "quantity", "align": "right"},
                    {"name": "unit_price", "label": "Preis", "field": "unit_price", "align": "right"},
                    {"name": "tax_rate", "label": "USt", "field": "tax_rate", "align": "right"},
                ]
                with ui.element("div").classes("w-full overflow-x-auto"):
                    table = ui.table(columns=columns, rows=items, row_key="id").classes("w-full mt-3 min-w-[560px]")
                    table.props("hide-pagination :pagination='{rowsPerPage:0}'")

                dialog = ui.dialog()
                with dialog:
                    with ff_card(pad="p-4", classes="w-full max-w-[92vw] max-h-[85vh] overflow-y-auto"):
                        ui.label("Position").classes(card_title_cls)
                        d_desc = ui.textarea("Beschreibung", value="").props("outlined dense").classes(C_INPUT)
                        d_desc.props("autogrow")
                        d_qty = ui.number("Menge", value=1, min=0, step=1).props("outlined dense").classes(C_INPUT)
                        d_price = ui.number("Einzelpreis", value=0.0, min=0, step=0.01).props("outlined dense").classes(C_INPUT)
                        d_tax = ui.number("USt in %", value=0, min=0, step=1).props("outlined dense").classes(C_INPUT)
                        with ui.row().classes("w-full justify-end gap-2 mt-4"):
                            ff_btn_secondary("Abbrechen", on_click=dialog.close)

                            def _add_item() -> None:
                                items.append({"id": f"i{len(items)+1}", "description": d_desc.value or "", "quantity": float(d_qty.value or 0), "unit_price": float(d_price.value or 0), "tax_rate": float(d_tax.value or 0)})
                                table.rows = items
                                dialog.close()
                                mark_preview_dirty()

                            ff_btn_primary("Hinzufügen", on_click=_add_item)
                add_btn.on("click", dialog.open)

                def _finalize_invoice(target_status=InvoiceStatus.OPEN) -> None:
                    errors: list[str] = []
                    if customer_select.value in (None, new_customer_value):
                        errors.append("Bitte einen Kunden auswählen.")
                    if not (invoice_date_input.value or "").strip():
                        errors.append("Bitte ein Rechnungsdatum setzen.")
                    if not any((str(it.get("description", "")).strip() for it in items)):
                        errors.append("Bitte mindestens eine Position mit Beschreibung hinzufügen.")
                    if errors:
                        ui.notify("\\n".join(errors), color="red")
                        return
                    try:
                        new_id = finalize_invoice_logic(session=session, comp_id=int(comp.id), cust_id=int(customer_select.value), title=title_input.value or "Rechnung", date_str=str(invoice_date_input.value or ""), delivery_str=str(service_input.value or ""), recipient_data={}, items=items, ust_enabled=bool(vat_switch.value), status=target_status, intro_text=intro_input.value or "", service_from=service_from, service_to=service_to)
                        app.storage.user["invoice_detail_id"] = int(new_id)
                        go_app_page("invoice_detail")
                    except Exception as exc:
                        ui.notify(f"Fehler beim Speichern der Rechnung: {exc}", color="red")

                ff_btn_primary("Rechnung finalisieren", on_click=lambda: _finalize_invoice(InvoiceStatus.OPEN), classes="mt-4 ff-btn-finalize-invoice w-full md:w-auto")
                ff_btn_secondary("Als Entwurf speichern", on_click=lambda: _finalize_invoice(InvoiceStatus.DRAFT), classes="mt-2 w-full md:w-auto")

        with ui.column().classes("w-full md:flex-1"):
            with ui.expansion("Vorschau", icon="visibility").classes("w-full md:hidden"):
                with ff_card(pad="p-4", classes=card_cls):
                    preview_summary_mobile = ui.html("", sanitize=False).classes("w-full mb-3")
                    preview_frame_mobile = ui.html("", sanitize=False).classes("w-full min-h-[50vh]")
            with ff_card(pad="p-4", classes=f"{card_cls_sticky} ff-invoice-preview-desktop"):
                ui.label("Vorschau").classes(card_title_cls)
                preview_summary = ui.html("", sanitize=False).classes("w-full mb-3")
                preview_frame = ui.html("", sanitize=False).classes("w-full min-h-[480px]")

    preview_state = {"dirty": True, "pending": False, "last_change": 0.0}
    renderer = PDFInvoiceRenderer()

    def mark_preview_dirty() -> None:
        preview_state["dirty"] = True
        preview_state["pending"] = True
        preview_state["last_change"] = time.monotonic()

    def _current_customer_obj():
        sel = customer_select.value
        if sel in (None, new_customer_value):
            return None
        try:
            return customers_by_id.get(int(sel))
        except (TypeError, ValueError):
            return None

    def update_preview(force_pdf: bool = False) -> None:
        invoice = build_preview_invoice(comp, _current_customer_obj(), items, title_input.value or "Rechnung", str(invoice_date_input.value or ""), service_from, service_to, intro_input.value or "", bool(vat_switch.value))
        html = render_preview_html(invoice)
        if preview_summary is not None:
            preview_summary.content = html
        if preview_summary_mobile is not None:
            preview_summary_mobile.content = html
        if not (force_pdf or preview_state["dirty"]):
            return
        preview_state["dirty"] = False
        try:
            frame_html = render_preview_pdf_frame(invoice, renderer)
            if preview_frame is not None:
                preview_frame.content = frame_html
            if preview_frame_mobile is not None:
                preview_frame_mobile.content = frame_html
        except Exception as ex:
            for f in (preview_frame, preview_frame_mobile):
                if f is not None:
                    f.content = ""
            err = f"<div class='text-rose-600'>PDF Fehler: {ex}</div>{html}"
            for s in (preview_summary, preview_summary_mobile):
                if s is not None:
                    s.content = err

    def _on_customer_change(e) -> None:
        if e.value == new_customer_value:
            prefill = ""
            prev = getattr(e, "previous_value", None)
            if isinstance(prev, str) and prev != new_customer_value:
                prefill = prev.strip()
            new_customer_dialog._reset_form(prefill_name=prefill)  # type: ignore[attr-defined]
            customer_select.value = None
            new_customer_dialog.open()
            return
        mark_preview_dirty()

    def debounce_tick() -> None:
        if not preview_state["pending"]:
            return
        if time.monotonic() - preview_state["last_change"] < 0.6:
            return
        preview_state["pending"] = False
        update_preview()

    customer_select.on_value_change(_on_customer_change)
    title_input.on("update:value", lambda e: mark_preview_dirty())
    intro_input.on("update:value", lambda e: mark_preview_dirty())
    vat_switch.on("update:modelValue", lambda e: mark_preview_dirty())
    ui.timer(0.1, debounce_tick)

    if new_customer_id is not None:
        customer_select.value = new_customer_id
        mark_preview_dirty()

    update_preview(force_pdf=True)
