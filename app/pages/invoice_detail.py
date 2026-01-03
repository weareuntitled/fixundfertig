from __future__ import annotations
from ._shared import *

# Auto generated page renderer

def render_invoice_detail(session, comp: Company) -> None:
    invoice_id = app.storage.user.get("invoice_detail_id")
    if not invoice_id:
        ui.notify("Keine Rechnung ausgewählt", color="red")
        app.storage.user["page"] = "invoices"
        ui.navigate.to("/")
        return

    invoice = session.get(Invoice, int(invoice_id))
    if not invoice:
        ui.notify("Rechnung nicht gefunden", color="red")
        app.storage.user["page"] = "invoices"
        ui.navigate.to("/")
        return

    customer = session.get(Customer, invoice.customer_id) if invoice.customer_id else None
    items = session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id)).all()

    with ui.row().classes("w-full justify-between items-start px-6 py-6"):
        with ui.column().classes("gap-1"):
            ui.label("Rechnung").classes(C_PAGE_TITLE)
            subtitle = f"#{invoice.nr}" if invoice.nr else f"ID {invoice.id}"
            ui.label(subtitle).classes("text-sm text-slate-500")

        with ui.row().classes("gap-2 items-center"):
            ui.button("Zurück", on_click=lambda: (app.storage.user.__setitem__("page", "invoices"), ui.navigate.to("/"))).classes(C_BTN_SEC)

            def on_download():
                try:
                    download_invoice_file(invoice)
                except Exception as e:
                    ui.notify(f"Fehler: {e}", color="red")

            def on_send():
                try:
                    send_invoice_email(comp, customer, invoice)
                except Exception as e:
                    ui.notify(f"Fehler: {e}", color="red")

            ui.button("Download", on_click=on_download).classes(C_BTN_SEC)
            ui.button("Senden", on_click=on_send).classes(C_BTN_SEC)

            with ui.button(icon="more_vert").props("flat round").classes("text-slate-600"):
                with ui.menu().props("auto-close"):
                    def set_status(target_status: InvoiceStatus):
                        try:
                            with get_session() as s:
                                with s.begin():
                                    _, err = update_status_logic(s, int(invoice.id), target_status)
                                if err:
                                    ui.notify(err, color="red")
                                else:
                                    ui.notify("Status aktualisiert", color="green")
                                    ui.navigate.to("/")
                        except Exception as e:
                            ui.notify(f"Fehler: {e}", color="red")

                    def do_cancel():
                        try:
                            ok, err = cancel_invoice(int(invoice.id))
                            if not ok:
                                ui.notify(err, color="red")
                            else:
                                ui.notify("Storniert", color="green")
                                ui.navigate.to("/")
                        except Exception as e:
                            ui.notify(f"Fehler: {e}", color="red")

                    def do_correction():
                        try:
                            corr, err = create_correction(int(invoice.id), use_negative_items=True)
                            if err:
                                ui.notify(err, color="red")
                            else:
                                ui.notify("Korrektur als Entwurf erstellt", color="green")
                                _open_invoice_editor(int(corr.id))
                        except Exception as e:
                            ui.notify(f"Fehler: {e}", color="red")

                    if invoice.status in (InvoiceStatus.OPEN, InvoiceStatus.FINALIZED):
                        ui.menu_item("Als gesendet markieren", on_click=lambda: set_status(InvoiceStatus.SENT))
                    if invoice.status == InvoiceStatus.SENT:
                        ui.menu_item("Als bezahlt markieren", on_click=lambda: set_status(InvoiceStatus.PAID))
                    if invoice.status not in (InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED):
                        ui.menu_item("Korrektur erstellen", on_click=do_correction)
                        ui.menu_item("Stornieren", on_click=do_cancel)

    with ui.column().classes("w-full px-6 pb-10 gap-4"):
        with ui.card().classes(C_CARD + " p-4"):
            _render_status_stepper(invoice)

        with ui.card().classes(C_CARD + " p-4"):
            with ui.row().classes("w-full gap-8 flex-wrap"):
                with ui.column().classes("gap-1"):
                    ui.label("Kunde").classes("text-xs text-slate-400")
                    ui.label(customer.display_name if customer else "-").classes("text-sm font-semibold")
                    if customer and customer.email:
                        ui.label(customer.email).classes("text-xs text-slate-500")

                with ui.column().classes("gap-1"):
                    ui.label("Datum").classes("text-xs text-slate-400")
                    ui.label(invoice.date or "-").classes("text-sm font-mono")

                with ui.column().classes("gap-1"):
                    ui.label("Lieferdatum").classes("text-xs text-slate-400")
                    ui.label(invoice.delivery_date or "-").classes("text-sm font-mono")

                with ui.column().classes("gap-1"):
                    ui.label("Betrag").classes("text-xs text-slate-400")
                    ui.label(f"{float(invoice.total_brutto or 0):,.2f} €").classes("text-sm font-semibold font-mono")

                with ui.column().classes("gap-1"):
                    ui.label("Status").classes("text-xs text-slate-400")
                    ui.label(format_invoice_status(invoice.status)).classes(invoice_status_badge(invoice.status))

            if invoice.status == InvoiceStatus.DRAFT:
                ui.button("Bearbeiten", on_click=lambda: _open_invoice_editor(int(invoice.id))).classes(C_BTN_PRIM + " mt-3")
            else:
                with ui.row().classes("gap-2 mt-3 items-center"):
                    ui.button("Edit with risk", on_click=lambda: risk_dialog.open()).classes(C_BTN_SEC)

                with ui.dialog() as risk_dialog:
                    with ui.card().classes(C_CARD + " p-4 w-[520px] max-w-[90vw]"):
                        ui.label("Ändern auf Risiko").classes("text-base font-semibold text-slate-900")
                        ui.label("Erstellt eine Revision als neuen Entwurf. Das Original bleibt nachvollziehbar.").classes("text-sm text-slate-600")
                        reason_input = ui.textarea("Grund", placeholder="Warum musst du das ändern").classes(C_INPUT)
                        risk_checkbox = ui.checkbox("Ich verstehe das Risiko und möchte eine Revision erstellen.")
                        with ui.row().classes("justify-end w-full gap-2 mt-2"):
                            ui.button("Abbrechen", on_click=lambda: risk_dialog.close()).classes(C_BTN_SEC)
                            btn_ok = ui.button("Revision erstellen", on_click=lambda: None).classes(C_BTN_PRIM)
                            btn_ok.disable()

                        def validate():
                            if risk_checkbox.value and (reason_input.value or "").strip():
                                btn_ok.enable()
                            else:
                                btn_ok.disable()

                        reason_input.on("update:model-value", lambda e: validate())
                        risk_checkbox.on("update:model-value", lambda e: validate())

                        def do_risk():
                            new_id = create_invoice_revision_and_edit(int(invoice.id), (reason_input.value or "").strip())
                            if not new_id:
                                ui.notify("Revision konnte nicht erstellt werden", color="red")
                                return
                            risk_dialog.close()
                            _open_invoice_editor(int(new_id))

                        btn_ok.on("click", lambda: do_risk())

        ui.label("Positionen").classes(C_SECTION_TITLE + " mt-2")
        if not items:
            with ui.card().classes(C_CARD + " p-4"):
                ui.label("Keine Positionen hinterlegt").classes("text-sm text-slate-500")
        else:
            with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
                with ui.row().classes(C_TABLE_HEADER):
                    ui.label("Beschreibung").classes("flex-1 font-bold text-xs text-slate-500")
                    ui.label("Menge").classes("w-24 text-right font-bold text-xs text-slate-500")
                    ui.label("Preis").classes("w-28 text-right font-bold text-xs text-slate-500")

                for it in items:
                    with ui.row().classes(C_TABLE_ROW):
                        ui.label(it.description).classes("flex-1 text-sm")
                        ui.label(f"{float(it.quantity or 0):,.2f}").classes("w-24 text-right text-sm font-mono")
                        ui.label(f"{float(it.unit_price or 0):,.2f} €").classes("w-28 text-right text-sm font-mono")
