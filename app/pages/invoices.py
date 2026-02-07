from __future__ import annotations
from ._shared import *
from ._shared import _open_invoice_editor, _parse_iso_date
from styles import STYLE_TEXT_MUTED
from ui_components import ff_btn_muted, ff_btn_primary, ff_btn_secondary, ff_card

# Auto generated page renderer

def render_invoices(session, comp: Company) -> None:
    _CLS = {
        "page_header": "w-full justify-between items-center mb-4 gap-3 flex-col sm:flex-row flex-wrap",
        "grid": "grid grid-cols-10 gap-4 w-full",
        "left_col": "col-span-10 lg:col-span-7 gap-3",
        "right_col": "col-span-10 lg:col-span-3 gap-5 order-2 lg:order-none mt-4 lg:mt-0 pt-4 lg:pt-0 border-t lg:border-t-0 border-slate-200",
        "card_header": "px-4 py-3 border-b border-slate-200 items-center justify-between",
        "card_row": "px-4 py-3 border-b border-slate-200 items-center justify-between",
        "row_label_sm": "sm:hidden text-[10px] uppercase text-slate-400",
        "icon_btn": "text-slate-500 hover:text-slate-900",
    }

    with ui.row().classes(_CLS["page_header"]):
        ui.label("Rechnungen").classes(C_PAGE_TITLE)
        ff_btn_primary("Neue Rechnung", on_click=lambda: _open_invoice_editor(None))

    # Nur Rechnungen der aktiven Company (via Customer.company_id)
    invs = session.exec(
        select(Invoice)
        .join(Customer, Invoice.customer_id == Customer.id)
        .where(Customer.company_id == comp.id)
        .order_by(Invoice.id.desc())
    ).all()

    drafts = [i for i in invs if i.status == InvoiceStatus.DRAFT]
    finals = [i for i in invs if i.status != InvoiceStatus.DRAFT]

    now = datetime.now()
    overdue_days = 14
    reminders: list[Invoice] = []
    for inv in finals:
        if inv.status in (InvoiceStatus.OPEN, InvoiceStatus.SENT, InvoiceStatus.FINALIZED):
            if _parse_iso_date(inv.date) < (now - timedelta(days=overdue_days)):
                reminders.append(inv)

    cust_cache: dict[int, Customer | None] = {}

    def cust_name(inv: Invoice) -> str:
        if not inv.customer_id:
            return "?"
        cid = int(inv.customer_id)
        if cid not in cust_cache:
            cust_cache[cid] = session.get(Customer, cid)
        c = cust_cache[cid]
        return c.display_name if c else "?"

    def run_download(inv: Invoice) -> None:
        try:
            download_invoice_file(inv)
        except Exception as e:
            ui.notify(f"Fehler: {e}", color="red")

    def run_send(inv: Invoice) -> None:
        try:
            c = cust_cache.get(int(inv.customer_id)) if inv.customer_id else None
            if not c and inv.customer_id:
                c = session.get(Customer, int(inv.customer_id))
            send_invoice_email(comp, c, inv)
        except Exception as e:
            ui.notify(f"Fehler: {e}", color="red")

    def set_status(inv: Invoice, target_status: InvoiceStatus) -> None:
        try:
            with get_session() as s:
                with s.begin():
                    _, err = update_status_logic(s, int(inv.id), target_status)
            if err:
                ui.notify(err, color="red")
            else:
                ui.notify("Status aktualisiert", color="green")
                ui.navigate.to("/")
        except Exception as e:
            ui.notify(f"Fehler: {e}", color="red")

    def do_cancel(inv: Invoice) -> None:
        try:
            ok, err = cancel_invoice(int(inv.id))
            if not ok:
                ui.notify(err, color="red")
            else:
                ui.notify("Storniert", color="green")
                ui.navigate.to("/")
        except Exception as e:
            ui.notify(f"Fehler: {e}", color="red")

    delete_state = {"id": None, "label": ""}

    with ui.dialog() as delete_dialog:
        with ff_card(pad="p-5", classes="w-full max-w-[92vw] max-h-[85vh] overflow-y-auto"):
            ui.label("Rechnung löschen").classes(C_SECTION_TITLE)
            delete_label = ui.label("Willst du diese Rechnung wirklich löschen?").classes(STYLE_TEXT_MUTED)
            with ui.row().classes("justify-end gap-2 mt-3 w-full"):
                ff_btn_secondary("Abbrechen", on_click=delete_dialog.close)

                def _confirm_delete():
                    if not delete_state["id"]:
                        delete_dialog.close()
                        return
                    try:
                        ok, err = delete_invoice(int(delete_state["id"]))
                        if not ok:
                            ui.notify(err, color="red")
                        else:
                            ui.notify("Rechnung gelöscht", color="green")
                            delete_dialog.close()
                            ui.navigate.to("/")
                    except Exception as e:
                        ui.notify(f"Fehler: {e}", color="red")

                ff_btn_muted("Löschen", on_click=_confirm_delete)

    def open_delete(inv: Invoice) -> None:
        delete_state["id"] = int(inv.id)
        label_parts = [f"#{inv.nr}" if inv.nr else "Rechnung"]
        name = cust_name(inv)
        if name:
            label_parts.append(name)
        delete_label.text = "Willst du diese Rechnung wirklich löschen? " + " ".join(label_parts)
        delete_dialog.open()

    with ui.element("div").classes(_CLS["grid"]):
        # Left column
        with ui.column().classes(_CLS["left_col"]):
            with ff_card(pad="p-0", classes="overflow-hidden"):
                with ui.element("div").classes("overflow-x-auto"):
                    with ui.element("div").classes("w-full"):
                        with ui.row().classes(C_TABLE_HEADER + " hidden sm:flex"):
                            ui.label("Nr").classes("w-24")
                            ui.label("Kunde").classes("flex-1")
                            ui.label("Betrag").classes("w-28 text-right")
                            ui.label("Status").classes("w-28 text-right")
                            ui.label("").classes("w-44 text-right")

                        if not finals:
                            with ui.row().classes(C_TABLE_ROW):
                                ui.label("Noch keine Rechnungen vorhanden").classes(STYLE_TEXT_MUTED)
                        else:
                            for idx, inv in enumerate(finals):
                                row_bg = "bg-white" if idx % 2 == 0 else "bg-slate-50/60"
                                with ui.row().classes(
                                    C_TABLE_ROW
                                    + f" {row_bg} h-16 group flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-0 hover:bg-slate-50"
                                ):
                                    with ui.row().classes("flex-1 flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 cursor-pointer w-full").on(
                                        "click", lambda _, x=inv: _open_invoice_detail(int(x.id))
                                    ):
                                        with ui.row().classes("items-start justify-between gap-3"):
                                            ui.label(f"#{inv.nr}" if inv.nr else "-").classes("text-xs font-mono text-slate-700")
                                            ui.label(format_invoice_status(inv.status)).classes(invoice_status_badge(inv.status))
                                        ui.label(cust_name(inv)).classes("text-sm text-slate-900")
                                        ui.label(f"{float(inv.total_brutto or 0):,.2f} €").classes(
                                            f"text-sm font-mono text-slate-900 {C_NUMERIC}"
                                        )
                                    with ui.row().classes("w-full justify-end gap-2 flex-wrap"):
                                        ui.button(icon="visibility", on_click=lambda x=inv: _open_invoice_detail(int(x.id))).props(
                                            "flat dense no-parent-event"
                                        ).classes(_CLS["icon_btn"])
                                        ui.button(icon="download", on_click=lambda x=inv: run_download(x)).props(
                                            "flat dense no-parent-event"
                                        ).classes(_CLS["icon_btn"])
                                        ui.button(icon="mail", on_click=lambda x=inv: run_send(x)).props(
                                            "flat dense no-parent-event"
                                        ).classes(_CLS["icon_btn"])

                                        with ui.button(icon="more_vert").props("flat dense no-parent-event").classes(_CLS["icon_btn"]):
                                            with ui.menu().props("auto-close no-parent-event"):
                                                if inv.status in (InvoiceStatus.OPEN, InvoiceStatus.FINALIZED):
                                                    ui.menu_item("Als gesendet markieren", on_click=lambda x=inv: set_status(x, InvoiceStatus.SENT))
                                                if inv.status == InvoiceStatus.SENT:
                                                    ui.menu_item("Als bezahlt markieren", on_click=lambda x=inv: set_status(x, InvoiceStatus.PAID))
                                                if inv.status != InvoiceStatus.CANCELLED:
                                                    ui.menu_item("Stornieren", on_click=lambda x=inv: do_cancel(x))
                                                ui.menu_item("Löschen", on_click=lambda x=inv: open_delete(x))

                    with ui.element("div").classes("hidden sm:block"):
                        for idx, inv in enumerate(finals):
                            row_bg = "bg-white" if idx % 2 == 0 else "bg-slate-50/60"
                            with ui.row().classes(
                                C_TABLE_ROW + f" {row_bg} h-16 group hover:bg-slate-50 hidden sm:flex sm:items-center"
                            ):
                                with ui.row().classes("flex-1 flex items-center gap-4 cursor-pointer w-full").on(
                                    "click", lambda _, x=inv: _open_invoice_detail(int(x.id))
                                ):
                                    with ui.column().classes("w-24 gap-1"):
                                        ui.label("Nr").classes(_CLS["row_label_sm"])
                                        ui.label(f"#{inv.nr}" if inv.nr else "-").classes("text-xs font-mono text-slate-700")
                                    with ui.column().classes("flex-1 gap-1"):
                                        ui.label("Kunde").classes(_CLS["row_label_sm"])
                                        ui.label(cust_name(inv)).classes("text-sm text-slate-900")
                                    with ui.column().classes("w-28 gap-1 items-end"):
                                        ui.label("Betrag").classes(_CLS["row_label_sm"])
                                        ui.label(f"{float(inv.total_brutto or 0):,.2f} €").classes(
                                            f"text-sm font-mono text-slate-900 text-right {C_NUMERIC}"
                                        )
                                    with ui.column().classes("w-28 gap-1 items-end"):
                                        ui.label("Status").classes(_CLS["row_label_sm"])
                                        with ui.row().classes("justify-end"):
                                            ui.label(format_invoice_status(inv.status)).classes(invoice_status_badge(inv.status))

                                with ui.column().classes("w-44 gap-2 items-end"):
                                    ui.label("Aktionen").classes(_CLS["row_label_sm"])
                                    with ui.row().classes("w-44 justify-end gap-2 flex-wrap"):
                                        ui.button(icon="visibility", on_click=lambda x=inv: _open_invoice_detail(int(x.id))).props(
                                            "flat dense no-parent-event"
                                        ).classes(_CLS["icon_btn"])
                                        ui.button(icon="download", on_click=lambda x=inv: run_download(x)).props(
                                            "flat dense no-parent-event"
                                        ).classes(_CLS["icon_btn"])
                                        ui.button(icon="mail", on_click=lambda x=inv: run_send(x)).props(
                                            "flat dense no-parent-event"
                                        ).classes(_CLS["icon_btn"])

                                        with ui.button(icon="more_vert").props("flat dense no-parent-event").classes(_CLS["icon_btn"]):
                                            with ui.menu().props("auto-close no-parent-event"):
                                                if inv.status in (InvoiceStatus.OPEN, InvoiceStatus.FINALIZED):
                                                    ui.menu_item("Als gesendet markieren", on_click=lambda x=inv: set_status(x, InvoiceStatus.SENT))
                                                if inv.status == InvoiceStatus.SENT:
                                                    ui.menu_item("Als bezahlt markieren", on_click=lambda x=inv: set_status(x, InvoiceStatus.PAID))
                                                if inv.status != InvoiceStatus.CANCELLED:
                                                    ui.menu_item("Stornieren", on_click=lambda x=inv: do_cancel(x))
                                                ui.menu_item("Löschen", on_click=lambda x=inv: open_delete(x))

        # Right column
        with ui.column().classes(_CLS["right_col"]):
            # Drafts
            with ff_card(pad="p-0", classes="overflow-hidden"):
                with ui.row().classes(_CLS["card_header"]):
                    ui.label("Entwürfe").classes(C_SECTION_TITLE)
                    ui.label(f"{len(drafts)}").classes("text-xs text-slate-600")

                if not drafts:
                    with ui.row().classes("px-4 py-3"):
                        ui.label("Keine Entwürfe").classes(STYLE_TEXT_MUTED)
                else:
                    for d in drafts[:12]:
                        with ui.row().classes(_CLS["card_row"]):
                            with ui.row().classes("gap-2 items-center cursor-pointer").on(
                                "click", lambda _, x=d: _open_invoice_editor(int(x.id))
                            ):
                                ui.label("Entwurf").classes(invoice_status_badge(InvoiceStatus.DRAFT))
                                ui.label(cust_name(d)).classes("text-sm text-slate-900")
                            with ui.row().classes("gap-2"):
                                ff_btn_secondary("Edit", on_click=lambda x=d: _open_invoice_editor(int(x.id)), props="dense no-parent-event", classes="text-xs")
                                ff_btn_muted("Löschen", on_click=lambda x=d: open_delete(x), props="dense no-parent-event", classes="text-xs")

            # Reminders
            with ff_card(pad="p-0", classes="overflow-hidden"):
                with ui.row().classes(_CLS["card_header"]):
                    ui.label("Mahnungen").classes(C_SECTION_TITLE)
                    ui.label(f"{len(reminders)}").classes("text-xs text-slate-600")

                if not reminders:
                    with ui.row().classes("px-4 py-3"):
                        ui.label("Keine überfälligen Rechnungen").classes(STYLE_TEXT_MUTED)
                else:
                    for r in reminders[:12]:
                        with ui.row().classes(_CLS["card_row"]):
                            with ui.row().classes("gap-2 items-center cursor-pointer").on(
                                "click", lambda _, x=r: _open_invoice_detail(int(x.id))
                            ):
                                ui.label("Overdue").classes(invoice_status_badge("Overdue"))
                                ui.label(f"#{r.nr}" if r.nr else "Rechnung").classes("text-xs font-mono text-slate-700")
                                ui.label(cust_name(r)).classes("text-sm text-slate-900")
                            ui.label(f"{float(r.total_brutto or 0):,.2f} €").classes(
                                f"text-sm font-mono text-slate-700 {C_NUMERIC}"
                            )
