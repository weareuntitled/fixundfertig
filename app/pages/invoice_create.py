from __future__ import annotations

import base64
from datetime import date
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from nicegui import app, ui
from sqlmodel import Session, select

from data import Company, Customer, Invoice
from logic import finalize_invoice_logic
from renderer import render_invoice_to_pdf_bytes


DEFAULT_INTRO_TEXT = (
    "Vielen Dank für Ihren Auftrag. "
    "Hiermit berechne ich die folgenden Leistungen."
)


def _period_from_value(v: Any) -> Tuple[Optional[str], Optional[str]]:
    if v is None:
        return None, None
    if isinstance(v, str):
        s = v.strip()
        return (s or None), (s or None)
    if isinstance(v, dict):
        f = (v.get("from") or "").strip()
        t = (v.get("to") or "").strip()
        if f and not t:
            t = f
        if t and not f:
            f = t
        return (f or None), (t or None)
    return None, None


def _period_display(v: Any) -> str:
    f, t = _period_from_value(v)
    if not f and not t:
        return ""
    if f and t and f != t:
        return f"{f} bis {t}"
    return f or t or ""


def _date_input_with_picker(label: str, storage_key: str, *, default_value: str, range_mode: bool = False) -> ui.input:
    store = app.storage.user
    if storage_key not in store:
        store[storage_key] = default_value if not range_mode else {"from": default_value, "to": default_value}

    inp = ui.input(label).props("readonly").classes("w-full")
    inp.value = _period_display(store.get(storage_key)) if range_mode else str(store.get(storage_key) or "")

    with ui.menu().props("no-parent-event") as menu:
        picker = ui.date().props('mask="YYYY-MM-DD"' + (" range" if range_mode else ""))
        picker.value = store[storage_key]

        def _sync(e: Any) -> None:
            store[storage_key] = picker.value
            inp.value = _period_display(picker.value) if range_mode else str(picker.value or "")
            inp.update()

        picker.on_value_change(_sync)
        ui.button("OK", on_click=menu.close).props("flat")

    inp.on("click", menu.open)
    return inp


def _build_preview_invoice(
    comp: Company,
    customer: Optional[Customer],
    title: str,
    invoice_date: str,
    service_period_value: Any,
    intro_text: str,
    items: List[Dict[str, Any]],
    ust_enabled: bool,
) -> Optional[bytes]:
    if not customer:
        return None

    inv = SimpleNamespace()
    inv.company = comp
    inv.customer = customer
    inv.title = title or "Rechnung"
    inv.invoice_number = "VORSCHAU"
    inv.date = invoice_date
    inv.delivery_date = _period_display(service_period_value)
    inv.payment_terms = getattr(comp, "default_payment_terms", "") or ""
    inv.address_name = customer.name
    inv.address_street = getattr(customer, "street", "") or ""
    inv.address_zip = getattr(customer, "zip", "") or ""
    inv.address_city = getattr(customer, "city", "") or ""
    inv.address_country = getattr(customer, "country", "") or ""
    inv.ust_enabled = bool(ust_enabled) and (not bool(getattr(comp, "is_small_business", False)))
    inv.__dict__["intro_text"] = intro_text or ""
    inv.__dict__["line_items"] = items
    return render_invoice_to_pdf_bytes(inv)


def render_invoice_create(session: Session, comp: Company) -> None:
    store = app.storage.user.setdefault("invoice_create_state", {})
    today = date.today().isoformat()

    store.setdefault("customer_id", None)
    store.setdefault("title", "Rechnung")
    store.setdefault("intro_text", DEFAULT_INTRO_TEXT)
    store.setdefault("ust_enabled", not bool(getattr(comp, "is_small_business", False)))
    store.setdefault("items", [])

    app.storage.user.setdefault("invoice_date", today)
    app.storage.user.setdefault("service_period", {"from": today, "to": today})

    customers = session.exec(select(Customer).where(Customer.company_id == comp.id).order_by(Customer.name)).all()
    customer_map = {c.id: c for c in customers}

    def selected_customer() -> Optional[Customer]:
        cid = store.get("customer_id")
        return customer_map.get(cid) if cid else None

    ui.label("Rechnung erstellen").classes("text-2xl font-semibold mb-4")

    preview_holder = {"el": None}

    def refresh_preview() -> None:
        el = preview_holder.get("el")
        if el is None:
            return

        cust = selected_customer()
        if not cust:
            el.set_content("<div class='text-sm text-gray-500'>Bitte Kunde wählen.</div>")
            return

        pdf_bytes = _build_preview_invoice(
            comp=comp,
            customer=cust,
            title=str(store.get("title") or "Rechnung"),
            invoice_date=str(app.storage.user.get("invoice_date") or today),
            service_period_value=app.storage.user.get("service_period"),
            intro_text=str(store.get("intro_text") or ""),
            items=list(store.get("items") or []),
            ust_enabled=bool(store.get("ust_enabled", True)),
        )
        if not pdf_bytes:
            el.set_content("<div class='text-sm text-gray-500'>Keine Vorschau verfügbar.</div>")
            return

        b64 = base64.b64encode(pdf_bytes).decode("ascii")
        el.set_content(
            f"<iframe src='data:application/pdf;base64,{b64}' "
            f"style='width:100%;height:78vh;border:0;'></iframe>"
        )

    with ui.row().classes("w-full gap-6"):
        with ui.column().classes("w-full md:w-1/2 gap-4"):
            with ui.card().classes("w-full p-4"):
                ui.label("Stammdaten").classes("text-lg font-semibold mb-2")

                sel = ui.select({c.id: c.name for c in customers}, label="Kunde", value=store.get("customer_id")).classes("w-full")

                def on_customer_change(e: Any) -> None:
                    store["customer_id"] = sel.value
                    refresh_preview()

                sel.on_value_change(on_customer_change)

                title_in = ui.input("Titel", value=store.get("title", "Rechnung")).classes("w-full")

                def on_title_change(e: Any) -> None:
                    store["title"] = title_in.value
                    refresh_preview()

                title_in.on_value_change(on_title_change)

                _date_input_with_picker("Rechnungsdatum", "invoice_date", default_value=today, range_mode=False)
                _date_input_with_picker("Leistungszeitraum", "service_period", default_value=today, range_mode=True)

                ust_toggle = ui.switch("USt berechnen", value=bool(store.get("ust_enabled", True))).classes("mt-2")

                def on_ust_change(e: Any) -> None:
                    store["ust_enabled"] = bool(ust_toggle.value)
                    refresh_preview()

                ust_toggle.on_value_change(on_ust_change)

                if bool(getattr(comp, "is_small_business", False)):
                    ust_toggle.disable()
                    ui.label("Kleinunternehmer: USt wird automatisch nicht ausgewiesen.").classes("text-sm text-gray-500")

            with ui.card().classes("w-full p-4"):
                ui.label("Einleitungstext").classes("text-lg font-semibold mb-2")
                intro_in = ui.textarea(value=str(store.get("intro_text") or DEFAULT_INTRO_TEXT)).props("autogrow").classes("w-full")

                def on_intro_change(e: Any) -> None:
                    store["intro_text"] = intro_in.value
                    refresh_preview()

                intro_in.on_value_change(on_intro_change)

            with ui.card().classes("w-full p-4"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Positionen").classes("text-lg font-semibold")
                    add_btn = ui.button("Position hinzufügen").props("outline")

                columns = [
                    {"name": "description", "label": "Beschreibung", "field": "description", "align": "left"},
                    {"name": "quantity", "label": "Menge", "field": "quantity", "align": "right"},
                    {"name": "unit_price", "label": "Preis", "field": "unit_price", "align": "right"},
                    {"name": "tax_rate", "label": "USt", "field": "tax_rate", "align": "right"},
                ]
                table = ui.table(columns=columns, rows=list(store.get("items") or [])).classes("w-full mt-3")

                with ui.dialog() as add_item_dialog:
                    with ui.card().classes("w-[min(680px,95vw)] p-4"):
                        ui.label("Position").classes("text-lg font-semibold mb-2")
                        desc_in = ui.textarea("Beschreibung").props("autogrow").classes("w-full")
                        qty_in = ui.number("Menge", value=1, min=0, step=1).classes("w-full")
                        price_in = ui.number("Einzelpreis", value=0, min=0, step=0.01).classes("w-full")

                        default_tax = 0 if bool(getattr(comp, "is_small_business", False)) or not bool(store.get("ust_enabled", True)) else 19
                        tax_in = ui.number("USt in %", value=default_tax, min=0, step=1).classes("w-full")

                        with ui.row().classes("w-full justify-end gap-2 mt-4"):
                            ui.button("Abbrechen", on_click=add_item_dialog.close).props("flat")

                            def add_item() -> None:
                                item = {
                                    "description": desc_in.value or "",
                                    "quantity": float(qty_in.value or 0),
                                    "unit_price": float(price_in.value or 0),
                                    "tax_rate": float(tax_in.value or 0),
                                }
                                store["items"] = [*list(store.get("items") or []), item]
                                table.rows = list(store["items"])
                                table.update()
                                add_item_dialog.close()
                                refresh_preview()

                            ui.button("Hinzufügen", on_click=add_item).props("unelevated color=primary")

                add_btn.on_click(add_item_dialog.open)

                def finalize() -> None:
                    cust = selected_customer()
                    if not cust:
                        ui.notify("Bitte einen Kunden wählen.", type="warning")
                        return
                    items = list(store.get("items") or [])
                    if not items:
                        ui.notify("Bitte mindestens eine Position hinzufügen.", type="warning")
                        return

                    inv_date = str(app.storage.user.get("invoice_date") or today)
                    period_val = app.storage.user.get("service_period")
                    period_display = _period_display(period_val)
                    df, dt = _period_from_value(period_val)

                    recipient = {
                        "address_name": cust.name,
                        "address_street": getattr(cust, "street", "") or "",
                        "address_zip": getattr(cust, "zip", "") or "",
                        "address_city": getattr(cust, "city", "") or "",
                        "address_country": getattr(cust, "country", "") or "",
                    }

                    invoice_id = finalize_invoice_logic(
                        session=session,
                        comp_id=comp.id,
                        cust_id=cust.id,
                        title=str(store.get("title") or "Rechnung"),
                        date_str=inv_date,
                        delivery_str=period_display,
                        recipient_data=recipient,
                        items=items,
                        ust_enabled=bool(store.get("ust_enabled", True)),
                        intro_text=str(store.get("intro_text") or ""),
                        service_from=df,
                        service_to=dt,
                    )

                    inv = session.get(Invoice, invoice_id)
                    if inv and getattr(inv, "pdf_bytes", None):
                        ui.notify("Rechnung erstellt.", type="positive")
                        ui.download(inv.pdf_bytes, filename=(getattr(inv, "invoice_number", "rechnung") + ".pdf"))
                    else:
                        ui.notify("Rechnung erstellt, PDF konnte nicht geladen werden.", type="warning")

                    store["items"] = []
                    table.rows = []
                    table.update()
                    refresh_preview()

                ui.button("Rechnung finalisieren", on_click=finalize).props("unelevated color=primary").classes("mt-4")

        with ui.column().classes("w-full md:w-1/2"):
            with ui.card().classes("w-full p-4"):
                ui.label("Vorschau").classes("text-lg font-semibold mb-2")
                preview = ui.html("<div class='text-sm text-gray-500'>Bitte Kunde wählen.</div>")
                preview_holder["el"] = preview
                refresh_preview()
