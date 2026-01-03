# FixundFertig/app/pages.py

from __future__ import annotations

import os
import base64
import json
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

from nicegui import ui, app
from sqlmodel import select
from sqlalchemy import literal, case, union_all, func

from data import (
    Company,
    Customer,
    Invoice,
    InvoiceItem,
    InvoiceItemTemplate,
    Expense,
    InvoiceRevision,
    log_audit_action,
    InvoiceStatus,
    get_session,
)

from renderer import render_invoice_to_pdf_bytes
from actions import cancel_invoice, create_correction, delete_draft, update_status_logic

from styles import (
    C_CARD,
    C_CARD_HOVER,
    C_BTN_PRIM,
    C_BTN_SEC,
    C_INPUT,
    C_PAGE_TITLE,
    C_SECTION_TITLE,
    C_TABLE_HEADER,
    C_TABLE_ROW,
    C_BADGE_GREEN,
)

from ui_components import (
    format_invoice_status,
    invoice_status_badge,
    kpi_card,
    sticky_header,
)

from logic import (
    finalize_invoice_logic,
    export_invoices_pdf_zip,
    export_invoices_csv,
    export_invoice_items_csv,
    export_customers_csv,
    export_database_backup,
)


# -------------------------
# Helpers
# -------------------------

def log_invoice_action(action: str, invoice_id: int | None = None) -> None:
    with get_session() as s:
        log_audit_action(s, action, invoice_id=invoice_id)
        s.commit()


def _parse_iso_date(value: str | None):
    try:
        return datetime.fromisoformat(value or "")
    except Exception:
        return datetime.min


def _open_invoice_detail(invoice_id: int) -> None:
    app.storage.user["invoice_detail_id"] = int(invoice_id)
    app.storage.user["page"] = "invoice_detail"
    ui.navigate.to("/")


def _open_invoice_editor(draft_id: int | None) -> None:
    app.storage.user["invoice_draft_id"] = int(draft_id) if draft_id else None
    app.storage.user["page"] = "invoice_create"
    ui.navigate.to("/")


# -------------------------
# PDF Download and Mail
# -------------------------

def download_invoice_file(invoice: Invoice) -> None:
    if invoice and invoice.id:
        log_invoice_action("EXPORT_CREATED", invoice.id)

    pdf_path = invoice.pdf_filename

    # If we have no file yet, create one
    if not pdf_path:
        pdf_bytes = render_invoice_to_pdf_bytes(invoice)
        if isinstance(pdf_bytes, bytearray):
            pdf_bytes = bytes(pdf_bytes)
        if not isinstance(pdf_bytes, bytes):
            raise TypeError("PDF output must be bytes")

        filename = f"rechnung_{invoice.nr}.pdf" if invoice.nr else "rechnung.pdf"
        pdf_path = f"storage/invoices/{filename}"
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        invoice.pdf_filename = filename
        invoice.pdf_storage = "local"

        if invoice.id:
            with get_session() as s:
                inv = s.get(Invoice, invoice.id)
                if inv:
                    inv.pdf_filename = filename
                    inv.pdf_storage = "local"
                    s.add(inv)
                    s.commit()

        ui.download(pdf_path)
        return

    # Normalized path
    if not os.path.isabs(pdf_path) and not str(pdf_path).startswith("storage/"):
        pdf_path = f"storage/invoices/{pdf_path}"

    if os.path.exists(pdf_path):
        ui.download(pdf_path)
        return

    # File missing but invoice exists, regenerate
    pdf_bytes = render_invoice_to_pdf_bytes(invoice)
    if isinstance(pdf_bytes, bytearray):
        pdf_bytes = bytes(pdf_bytes)
    if not isinstance(pdf_bytes, bytes):
        raise TypeError("PDF output must be bytes")

    filename = os.path.basename(invoice.pdf_filename) if invoice.pdf_filename else (f"rechnung_{invoice.nr}.pdf" if invoice.nr else "rechnung.pdf")
    pdf_path = f"storage/invoices/{filename}"
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    invoice.pdf_filename = filename
    invoice.pdf_storage = "local"

    if invoice.id:
        with get_session() as s:
            inv = s.get(Invoice, invoice.id)
            if inv:
                inv.pdf_filename = filename
                inv.pdf_storage = "local"
                s.add(inv)
                s.commit()

    ui.download(pdf_path)


def build_invoice_mailto(comp: Company | None, customer: Customer | None, invoice: Invoice) -> str:
    subject = f"Rechnung {invoice.nr or ''}".strip()
    amount = f"{float(invoice.total_brutto or 0):,.2f} EUR"

    body_lines = [
        f"Guten Tag {customer.display_name if customer else ''},".strip(),
        "",
        f"im Anhang finden Sie Ihre Rechnung {invoice.nr or ''} vom {invoice.date} über {amount}.",
        "",
        "Viele Grüße",
        comp.name if comp else "",
    ]

    params = urlencode({
        "subject": subject,
        "body": "\n".join(line for line in body_lines if line is not None),
    })

    recipient = customer.email if customer and customer.email else ""
    return f"mailto:{recipient}?{params}"


def send_invoice_email(comp: Company | None, customer: Customer | None, invoice: Invoice) -> None:
    if not customer or not customer.email:
        ui.notify("Keine Email-Adresse beim Kunden hinterlegt", color="red")
        return
    mailto = build_invoice_mailto(comp, customer, invoice)
    ui.run_javascript(f"window.location.href = {json.dumps(mailto)}")


# -------------------------
# Revisions "Edit with risk"
# -------------------------

def _snapshot_invoice(session, invoice: Invoice) -> str:
    items = session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id)).all()
    payload = {
        "invoice": {
            "id": invoice.id,
            "customer_id": invoice.customer_id,
            "nr": invoice.nr,
            "title": invoice.title,
            "date": invoice.date,
            "delivery_date": invoice.delivery_date,
            "recipient_name": invoice.recipient_name,
            "recipient_street": invoice.recipient_street,
            "recipient_postal_code": invoice.recipient_postal_code,
            "recipient_city": invoice.recipient_city,
            "total_brutto": invoice.total_brutto,
            "status": invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status),
            "revision_nr": invoice.revision_nr,
            "updated_at": invoice.updated_at,
            "related_invoice_id": invoice.related_invoice_id,
            "pdf_filename": invoice.pdf_filename,
            "pdf_storage": invoice.pdf_storage,
        },
        "items": [
            {
                "id": it.id,
                "description": it.description,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
            }
            for it in items
        ],
    }
    return json.dumps(payload)


def create_invoice_revision_and_edit(invoice_id: int, reason: str) -> int | None:
    with get_session() as s:
        original = s.get(Invoice, invoice_id)
        if not original:
            return None

        next_revision = int(original.revision_nr or 0) + 1
        snapshot_json = _snapshot_invoice(s, original)

        s.add(InvoiceRevision(
            invoice_id=original.id,
            revision_nr=next_revision,
            reason=reason,
            snapshot_json=snapshot_json,
            pdf_filename_previous=original.pdf_filename or "",
        ))

        original.revision_nr = next_revision
        original.updated_at = datetime.now().isoformat()
        s.add(original)

        new_inv = Invoice(
            customer_id=original.customer_id,
            nr=None,
            title=original.title,
            date=original.date,
            delivery_date=original.delivery_date,
            recipient_name=original.recipient_name,
            recipient_street=original.recipient_street,
            recipient_postal_code=original.recipient_postal_code,
            recipient_city=original.recipient_city,
            total_brutto=original.total_brutto,
            status=InvoiceStatus.DRAFT,
            related_invoice_id=original.id,
        )
        s.add(new_inv)
        s.commit()
        s.refresh(new_inv)

        old_items = s.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == original.id)).all()
        for it in old_items:
            s.add(InvoiceItem(
                invoice_id=new_inv.id,
                description=it.description,
                quantity=it.quantity,
                unit_price=it.unit_price,
            ))

        log_audit_action(s, "INVOICE_RISK_EDIT", invoice_id=original.id)
        s.commit()

        return int(new_inv.id)


# -------------------------
# Dashboard
# -------------------------

def render_dashboard(session, comp: Company) -> None:
    ui.label("Dashboard").classes(C_PAGE_TITLE + " mb-4")

    invs = session.exec(select(Invoice)).all()
    exps = session.exec(select(Expense)).all()

    umsatz = sum(float(i.total_brutto or 0) for i in invs if i.status in (InvoiceStatus.PAID, InvoiceStatus.FINALIZED))
    kosten = sum(float(e.amount or 0) for e in exps)
    offen = sum(float(i.total_brutto or 0) for i in invs if i.status in (InvoiceStatus.OPEN, InvoiceStatus.SENT, InvoiceStatus.FINALIZED))

    with ui.grid(columns=3).classes("w-full gap-4 mb-6"):
        kpi_card("Umsatz", f"{umsatz:,.2f} €", "trending_up", "text-emerald-500")
        kpi_card("Ausgaben", f"{kosten:,.2f} €", "trending_down", "text-rose-500")
        kpi_card("Offen", f"{offen:,.2f} €", "schedule", "text-blue-500")

    ui.label("Neueste Rechnungen").classes(C_SECTION_TITLE + " mb-2")
    with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
        with ui.row().classes(C_TABLE_HEADER):
            ui.label("Nr.").classes("w-20 font-bold text-xs text-slate-500")
            ui.label("Kunde").classes("flex-1 font-bold text-xs text-slate-500")
            ui.label("Betrag").classes("w-24 text-right font-bold text-xs text-slate-500")
            ui.label("Status").classes("w-24 text-right font-bold text-xs text-slate-500")

        latest = sorted(invs, key=lambda x: int(x.id or 0), reverse=True)[:5]
        for inv in latest:
            def go(target: Invoice = inv):
                if target.status == InvoiceStatus.DRAFT:
                    _open_invoice_editor(int(target.id))
                else:
                    _open_invoice_detail(int(target.id))

            with ui.row().classes(C_TABLE_ROW + " cursor-pointer hover:bg-slate-50").on("click", lambda _, x=inv: go(x)):
                ui.label(f"#{inv.nr}" if inv.nr else "-").classes("w-20 font-mono text-xs")
                c = session.get(Customer, inv.customer_id) if inv.customer_id else None
                ui.label(c.display_name if c else "?").classes("flex-1 text-sm")
                ui.label(f"{float(inv.total_brutto or 0):,.2f} €").classes("w-24 text-right font-mono text-sm")
                ui.label(format_invoice_status(inv.status)).classes(invoice_status_badge(inv.status) + " ml-auto")


# -------------------------
# Invoice Editor
# -------------------------

def render_invoice_create(session, comp: Company) -> None:
    draft_id = app.storage.user.get("invoice_draft_id")
    draft = session.get(Invoice, draft_id) if draft_id else None

    customers = session.exec(select(Customer)).all()
    cust_opts = {str(c.id): c.display_name for c in customers}

    template_items = session.exec(
        select(InvoiceItemTemplate).where(InvoiceItemTemplate.company_id == comp.id)
    ).all()

    init_items: list[dict] = []
    if draft:
        db_items = session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == draft.id)).all()
        for it in db_items:
            init_items.append({"desc": it.description, "qty": float(it.quantity or 0), "price": float(it.unit_price or 0), "is_brutto": False})

    if not init_items:
        init_items.append({"desc": "", "qty": 1.0, "price": 0.0, "is_brutto": False})

    state = {
        "items": init_items,
        "customer_id": str(draft.customer_id) if draft and draft.customer_id else None,
        "date": draft.date if draft and draft.date else datetime.now().strftime("%Y-%m-%d"),
        "delivery_date": draft.delivery_date if draft and draft.delivery_date else datetime.now().strftime("%Y-%m-%d"),
        "title": draft.title if draft and draft.title else "Rechnung",
        "ust": True,
    }

    blocked_statuses = {InvoiceStatus.FINALIZED, InvoiceStatus.OPEN, InvoiceStatus.SENT, InvoiceStatus.PAID}
    if draft and draft.status in blocked_statuses:
        sticky_header("Rechnungs-Editor", on_cancel=lambda: ui.navigate.to("/"))

        with ui.column().classes("w-full h-[calc(100vh-64px)] p-0 m-0"):
            with ui.column().classes("w-full p-4 gap-4"):
                with ui.card().classes(C_CARD + " p-4 w-full"):
                    ui.label("Ändern auf Risiko").classes(C_SECTION_TITLE)
                    ui.label("Diese Rechnung ist nicht mehr direkt editierbar.").classes("text-sm text-slate-600")

                    with ui.dialog() as risk_dialog:
                        with ui.card().classes(C_CARD + " p-4 w-full"):
                            ui.label("Ändern auf Risiko").classes(C_SECTION_TITLE)
                            reason_input = ui.textarea("Grund", placeholder="Grund der Änderung").classes(C_INPUT)
                            risk_checkbox = ui.checkbox("Ich verstehe das Risiko und möchte eine Revision erstellen.")
                            with ui.row().classes("justify-end w-full"):
                                action_button = ui.button(
                                    "Revision erstellen und ändern",
                                    on_click=lambda: on_risk_confirm()
                                ).classes(C_BTN_PRIM)
                                action_button.disable()

                            def validate_risk():
                                if risk_checkbox.value and (reason_input.value or "").strip():
                                    action_button.enable()
                                else:
                                    action_button.disable()

                            reason_input.on("update:model-value", lambda e: validate_risk())
                            risk_checkbox.on("update:model-value", lambda e: validate_risk())

                    def on_risk_confirm():
                        if not risk_checkbox.value or not (reason_input.value or "").strip():
                            return
                        new_id = create_invoice_revision_and_edit(int(draft.id), reason_input.value.strip())
                        if not new_id:
                            ui.notify("Revision konnte nicht erstellt werden", color="red")
                            return
                        app.storage.user["invoice_draft_id"] = new_id
                        app.storage.user["page"] = "invoice_create"
                        risk_dialog.close()
                        ui.navigate.to("/")

                    ui.button("Revision erstellen", on_click=lambda: risk_dialog.open()).classes(C_BTN_PRIM)
        return

    preview_html = None
    autosave_state = {"dirty": False, "last_change": 0.0, "saving": False}
    preview_state = {"pending": False, "last_change": 0.0}

    def mark_dirty():
        autosave_state["dirty"] = True
        autosave_state["last_change"] = time.monotonic()

    def request_preview_update():
        preview_state["pending"] = True
        preview_state["last_change"] = time.monotonic()

    # Recipient inputs declared later, but referenced in update_preview
    rec_name = rec_street = rec_zip = rec_city = None
    ust_switch = None

    def update_preview():
        cust_id = state["customer_id"]
        rec_n, rec_s, rec_z, rec_c = "", "", "", ""

        if cust_id:
            with get_session() as s:
                c = s.get(Customer, int(cust_id))
                if c:
                    rec_n = c.recipient_name or c.display_name
                    rec_s = c.recipient_street or c.strasse
                    rec_z = c.recipient_postal_code or c.plz
                    rec_c = c.recipient_city or c.ort

        final_n = rec_name.value if rec_name and rec_name.value else rec_n
        final_s = rec_street.value if rec_street and rec_street.value else rec_s
        final_z = rec_zip.value if rec_zip and rec_zip.value else rec_z
        final_c = rec_city.value if rec_city and rec_city.value else rec_c

        inv = Invoice(
            nr=comp.next_invoice_nr,
            title=state["title"],
            date=state["date"],
            delivery_date=state["delivery_date"],
            recipient_name=final_n,
            recipient_street=final_s,
            recipient_postal_code=final_z,
            recipient_city=final_c,
        )
        inv.__dict__["line_items"] = state["items"]
        inv.__dict__["tax_rate"] = 0.19 if (ust_switch and ust_switch.value) else 0.0

        try:
            pdf = render_invoice_to_pdf_bytes(inv)
            if isinstance(pdf, bytearray):
                pdf = bytes(pdf)
            if not isinstance(pdf, bytes):
                raise TypeError("PDF output must be bytes")
            b64 = base64.b64encode(pdf).decode("utf-8")
            if preview_html:
                preview_html.content = f'<iframe src="data:application/pdf;base64,{b64}" style="width:100%; height:100%; border:none;"></iframe>'
        except Exception as e:
            print(e)

    def debounce_preview():
        if preview_state["pending"] and (time.monotonic() - preview_state["last_change"] >= 0.3):
            preview_state["pending"] = False
            update_preview()

    def save_draft() -> int | None:
        nonlocal draft_id
        with get_session() as s:
            if draft_id:
                inv = s.get(Invoice, int(draft_id))
            else:
                inv = Invoice(status=InvoiceStatus.DRAFT)

            if state["customer_id"]:
                inv.customer_id = int(state["customer_id"])

            inv.title = state["title"]
            inv.date = state["date"]
            inv.delivery_date = state["delivery_date"]
            inv.total_brutto = 0

            s.add(inv)
            s.commit()
            s.refresh(inv)

            exist = s.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == inv.id)).all()
            for x in exist:
                s.delete(x)

            for it in state["items"]:
                s.add(InvoiceItem(
                    invoice_id=inv.id,
                    description=(it.get("desc") or ""),
                    quantity=float(it.get("qty") or 0),
                    unit_price=float(it.get("price") or 0),
                ))

            action = "INVOICE_UPDATED_DRAFT" if draft_id else "INVOICE_CREATED_DRAFT"
            log_audit_action(s, action, invoice_id=inv.id)
            s.commit()

            if not draft_id:
                draft_id = int(inv.id)
                app.storage.user["invoice_draft_id"] = int(inv.id)

        return int(draft_id) if draft_id else None

    def on_autosave():
        save_draft()

    def autosave_tick():
        if autosave_state["dirty"] and not autosave_state["saving"]:
            if time.monotonic() - autosave_state["last_change"] >= 3.0:
                autosave_state["saving"] = True
                on_autosave()
                autosave_state["dirty"] = False
                autosave_state["saving"] = False

    def on_finalize():
        if not state["customer_id"]:
            ui.notify("Kunde fehlt", color="red")
            return

        with get_session() as s:
            with s.begin():
                finalize_invoice_logic(
                    s,
                    comp.id,
                    int(state["customer_id"]),
                    state["title"],
                    state["date"],
                    state["delivery_date"],
                    {
                        "name": rec_name.value if rec_name else "",
                        "street": rec_street.value if rec_street else "",
                        "zip": rec_zip.value if rec_zip else "",
                        "city": rec_city.value if rec_city else "",
                    },
                    state["items"],
                    ust_switch.value if ust_switch else True,
                )

        ui.notify("Erstellt", color="green")
        app.storage.user["invoice_draft_id"] = None
        app.storage.user["page"] = "invoices"
        ui.navigate.to("/")

    def on_save_draft():
        save_draft()
        ui.notify("Gespeichert", color="green")
        app.storage.user["page"] = "invoices"
        ui.navigate.to("/")

    ui.timer(0.1, debounce_preview)
    ui.timer(3.0, autosave_tick)

    sticky_header(
        "Rechnungs-Editor",
        on_cancel=lambda: (app.storage.user.__setitem__("page", "invoices"), ui.navigate.to("/")),
        on_save=on_save_draft,
        on_finalize=on_finalize,
    )

    with ui.column().classes("w-full h-[calc(100vh-64px)] p-0 m-0"):
        with ui.grid().classes("w-full flex-grow grid-cols-1 md:grid-cols-2"):
            # Left side
            with ui.column().classes("w-full p-4 gap-4 h-full overflow-y-auto"):
                with ui.card().classes(C_CARD + " p-4 w-full"):
                    ui.label("Kopfdaten").classes(C_SECTION_TITLE)

                    cust_select = ui.select(cust_opts, label="Kunde", value=state["customer_id"], with_input=True).classes(C_INPUT)

                    def on_cust(e):
                        state["customer_id"] = e.value
                        mark_dirty()
                        if e.value:
                            with get_session() as s:
                                c = s.get(Customer, int(e.value))
                                if c:
                                    rec_name.value = c.recipient_name or c.display_name
                                    rec_street.value = c.recipient_street or c.strasse
                                    rec_zip.value = c.recipient_postal_code or c.plz
                                    rec_city.value = c.recipient_city or c.ort
                        request_preview_update()

                    cust_select.on("update:model-value", on_cust)

                    with ui.grid(columns=2).classes("w-full gap-2"):
                        ui.input(
                            "Titel",
                            value=state["title"],
                            on_change=lambda e: (state.update({"title": e.value}), mark_dirty(), request_preview_update()),
                        ).classes(C_INPUT)
                        ui.input(
                            "Rechnung",
                            value=state["date"],
                            on_change=lambda e: (state.update({"date": e.value}), mark_dirty(), request_preview_update()),
                        ).classes(C_INPUT)
                        ui.input(
                            "Lieferung",
                            value=state["delivery_date"],
                            on_change=lambda e: (state.update({"delivery_date": e.value}), mark_dirty(), request_preview_update()),
                        ).classes(C_INPUT)

                with ui.expansion("Anschrift anpassen").classes("w-full border border-slate-200 rounded bg-white text-sm"):
                    with ui.column().classes("p-3 gap-2 w-full"):
                        rec_name = ui.input("Name", on_change=lambda e: (mark_dirty(), request_preview_update())).classes(C_INPUT + " dense")
                        rec_street = ui.input("Straße", on_change=lambda e: (mark_dirty(), request_preview_update())).classes(C_INPUT + " dense")
                        with ui.row().classes("w-full gap-2"):
                            rec_zip = ui.input("PLZ", on_change=lambda e: (mark_dirty(), request_preview_update())).classes(C_INPUT + " w-20 dense")
                            rec_city = ui.input("Ort", on_change=lambda e: (mark_dirty(), request_preview_update())).classes(C_INPUT + " flex-1 dense")

                with ui.card().classes(C_CARD + " p-4 w-full"):
                    with ui.row().classes("justify-between w-full"):
                        ui.label("Posten").classes(C_SECTION_TITLE)
                        ust_switch = ui.switch(
                            "19% MwSt",
                            value=state["ust"],
                            on_change=lambda e: (state.update({"ust": e.value}), mark_dirty(), request_preview_update()),
                        ).props("dense color=grey-8")

                    if template_items:
                        item_template_select = ui.select(
                            {str(t.id): t.title for t in template_items},
                            label="Vorlage",
                            with_input=True,
                        ).classes(C_INPUT + " mb-2 dense")
                    else:
                        item_template_select = None

                    items_col = ui.column().classes("w-full gap-2")

                    def render_list():
                        items_col.clear()
                        with items_col:
                            for item in list(state["items"]):
                                with ui.row().classes("w-full gap-1 items-start bg-slate-50 p-2 rounded border"):
                                    ui.textarea(
                                        value=item.get("desc", ""),
                                        on_change=lambda e, i=item: (i.update({"desc": e.value}), mark_dirty(), request_preview_update()),
                                    ).classes("flex-1 dense text-sm").props('rows=1 placeholder="Text" auto-grow')

                                    with ui.column().classes("gap-1"):
                                        ui.number(
                                            value=item.get("qty", 0),
                                            on_change=lambda e, i=item: (i.update({"qty": float(e.value or 0)}), mark_dirty(), request_preview_update()),
                                        ).classes("w-16 dense")
                                        ui.number(
                                            value=item.get("price", 0),
                                            on_change=lambda e, i=item: (i.update({"price": float(e.value or 0)}), mark_dirty(), request_preview_update()),
                                        ).classes("w-20 dense")

                                    ui.button(
                                        icon="close",
                                        on_click=lambda i=item: (state["items"].remove(i), mark_dirty(), render_list(), request_preview_update()),
                                    ).classes("flat dense text-red")

                    def add_new():
                        state["items"].append({"desc": "", "qty": 1.0, "price": 0.0, "is_brutto": False})
                        mark_dirty()
                        render_list()
                        request_preview_update()

                    def add_tmpl():
                        if not item_template_select or not item_template_select.value:
                            return
                        t = next((x for x in template_items if str(x.id) == str(item_template_select.value)), None)
                        if t:
                            state["items"].append({"desc": t.description, "qty": float(t.quantity or 0), "price": float(t.unit_price or 0), "is_brutto": False})
                            mark_dirty()
                            render_list()
                            request_preview_update()
                            item_template_select.value = None

                    render_list()

                    with ui.row().classes("gap-2 mt-2"):
                        ui.button("Posten", icon="add", on_click=add_new).props("flat dense").classes("text-slate-600")
                        if template_items:
                            ui.button("Vorlage", icon="playlist_add", on_click=add_tmpl).props("flat dense").classes("text-slate-600")

            # Right side (Preview)
            with ui.column().classes("w-full h-full min-h-[70vh] bg-slate-200 p-0 m-0 overflow-hidden"):
                preview_html = ui.html("", sanitize=False).classes("w-full h-full min-h-[70vh] bg-slate-300")

    update_preview()


# -------------------------
# Invoice Detail
# -------------------------

def _status_step_current(invoice: Invoice) -> InvoiceStatus:
    s = invoice.status
    if s == InvoiceStatus.DRAFT:
        return InvoiceStatus.DRAFT
    if s in (InvoiceStatus.OPEN, InvoiceStatus.FINALIZED):
        return InvoiceStatus.OPEN
    if s == InvoiceStatus.SENT:
        return InvoiceStatus.SENT
    if s == InvoiceStatus.PAID:
        return InvoiceStatus.PAID
    if s == InvoiceStatus.CANCELLED:
        return InvoiceStatus.CANCELLED
    return InvoiceStatus.OPEN


def _render_status_stepper(invoice: Invoice) -> None:
    current = _status_step_current(invoice)
    steps = [
        (InvoiceStatus.DRAFT, "Entwurf"),
        (InvoiceStatus.OPEN, "Finalisiert"),
        (InvoiceStatus.SENT, "Gesendet"),
        (InvoiceStatus.PAID, "Bezahlt"),
        (InvoiceStatus.CANCELLED, "Storniert"),
    ]
    with ui.row().classes("items-center gap-2 flex-wrap"):
        for idx, (key, label) in enumerate(steps):
            is_active = key == current
            cls = "text-slate-900 font-semibold text-sm" if is_active else "text-slate-400 text-sm"
            ui.label(label).classes(cls)
            if idx < len(steps) - 1:
                ui.label("→").classes("text-slate-300 text-sm")


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


# -------------------------
# Invoices List (70/30)
# -------------------------

def render_invoices(session, comp: Company) -> None:
    ui.label("Rechnungen").classes(C_PAGE_TITLE)
    ui.label("Finale Rechnungen links, Entwürfe und Mahnungen rechts.").classes("text-sm text-slate-500 mb-4")

    with ui.row().classes("w-full justify-between items-center mb-4"):
        ui.button("Neue Rechnung", on_click=lambda: _open_invoice_editor(None)).classes(C_BTN_PRIM)

    invs = session.exec(select(Invoice).order_by(Invoice.id.desc())).all()
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

    with ui.element("div").classes("grid grid-cols-10 gap-4 w-full"):
        # Left column
        with ui.column().classes("col-span-10 lg:col-span-7 gap-3"):
            with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
                with ui.row().classes(C_TABLE_HEADER):
                    ui.label("Nr").classes("w-24 font-bold text-xs text-slate-500")
                    ui.label("Kunde").classes("flex-1 font-bold text-xs text-slate-500")
                    ui.label("Betrag").classes("w-28 text-right font-bold text-xs text-slate-500")
                    ui.label("Status").classes("w-28 text-right font-bold text-xs text-slate-500")
                    ui.label("").classes("w-44 text-right font-bold text-xs text-slate-500")

                if not finals:
                    with ui.row().classes(C_TABLE_ROW):
                        ui.label("Noch keine Rechnungen vorhanden").classes("text-sm text-slate-500")
                else:
                    for inv in finals:
                        with ui.row().classes(C_TABLE_ROW + " group"):
                            with ui.row().classes("flex-1 items-center gap-4 cursor-pointer").on("click", lambda _, x=inv: _open_invoice_detail(int(x.id))):
                                ui.label(f"#{inv.nr}" if inv.nr else "-").classes("w-24 text-xs font-mono text-slate-700")
                                ui.label(cust_name(inv)).classes("flex-1 text-sm text-slate-900")
                                ui.label(f"{float(inv.total_brutto or 0):,.2f} €").classes("w-28 text-right text-sm font-mono text-slate-800")
                                with ui.row().classes("w-28 justify-end"):
                                    ui.label(format_invoice_status(inv.status)).classes(invoice_status_badge(inv.status))

                            with ui.row().classes("w-44 justify-end gap-2"):
                                ui.button("Download", on_click=lambda x=inv: run_download(x)).props("flat dense no-parent-event").classes("text-slate-600")
                                ui.button("Senden", on_click=lambda x=inv: run_send(x)).props("flat dense no-parent-event").classes("text-slate-600")

                                with ui.button(icon="more_vert").props("flat dense no-parent-event").classes("text-slate-600"):
                                    with ui.menu().props("auto-close no-parent-event"):
                                        if inv.status in (InvoiceStatus.OPEN, InvoiceStatus.FINALIZED):
                                            ui.menu_item("Als gesendet markieren", on_click=lambda x=inv: set_status(x, InvoiceStatus.SENT))
                                        if inv.status == InvoiceStatus.SENT:
                                            ui.menu_item("Als bezahlt markieren", on_click=lambda x=inv: set_status(x, InvoiceStatus.PAID))
                                        if inv.status != InvoiceStatus.CANCELLED:
                                            ui.menu_item("Stornieren", on_click=lambda x=inv: do_cancel(x))

        # Right column
        with ui.column().classes("col-span-10 lg:col-span-3 gap-4"):
            # Drafts
            with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
                with ui.row().classes("px-4 py-3 border-b border-slate-200 items-center justify-between"):
                    ui.label("Entwürfe").classes("text-sm font-semibold text-slate-700")
                    ui.label(f"{len(drafts)}").classes("text-xs text-slate-500")

                if not drafts:
                    with ui.row().classes("px-4 py-3"):
                        ui.label("Keine Entwürfe").classes("text-sm text-slate-500")
                else:
                    for d in drafts[:12]:
                        with ui.row().classes("px-4 py-3 border-b border-slate-100 items-center justify-between"):
                            with ui.row().classes("gap-2 items-center cursor-pointer").on("click", lambda _, x=d: _open_invoice_editor(int(x.id))):
                                ui.label("Entwurf").classes(invoice_status_badge(InvoiceStatus.DRAFT))
                                ui.label(cust_name(d)).classes("text-sm text-slate-900")
                            with ui.row().classes("gap-2"):
                                ui.button("Edit", on_click=lambda x=d: _open_invoice_editor(int(x.id))).props("flat dense no-parent-event").classes("text-slate-600")
                                ui.button("Löschen", on_click=lambda x=d: (delete_draft(int(x.id)), ui.navigate.to("/"))).props("flat dense no-parent-event").classes("text-rose-600")

            # Reminders
            with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
                with ui.row().classes("px-4 py-3 border-b border-slate-200 items-center justify-between"):
                    ui.label("Mahnungen").classes("text-sm font-semibold text-slate-700")
                    ui.label(f"{len(reminders)}").classes("text-xs text-slate-500")

                if not reminders:
                    with ui.row().classes("px-4 py-3"):
                        ui.label("Keine überfälligen Rechnungen").classes("text-sm text-slate-500")
                else:
                    for r in reminders[:12]:
                        with ui.row().classes("px-4 py-3 border-b border-slate-100 items-center justify-between"):
                            with ui.row().classes("gap-2 items-center cursor-pointer").on("click", lambda _, x=r: _open_invoice_detail(int(x.id))):
                                ui.label("Overdue").classes("bg-amber-50 text-amber-800 border border-amber-100 px-2 py-0.5 rounded-full text-xs font-medium")
                                ui.label(f"#{r.nr}" if r.nr else "Rechnung").classes("text-xs font-mono text-slate-700")
                                ui.label(cust_name(r)).classes("text-sm text-slate-900")
                            ui.label(f"{float(r.total_brutto or 0):,.2f} €").classes("text-sm font-mono text-slate-700")


# -------------------------
# Customers
# -------------------------

def render_customers(session, comp: Company) -> None:
    ui.label("Kunden").classes(C_PAGE_TITLE)

    with ui.row().classes("gap-3 mb-4"):
        ui.button("Neu", icon="add", on_click=lambda: (app.storage.user.__setitem__("page", "customer_new"), ui.navigate.to("/"))).classes(C_BTN_PRIM)

    customers = session.exec(select(Customer).where(Customer.archived == False)).all()
    with ui.grid(columns=3).classes("w-full gap-4"):
        for c in customers:
            def open_detail(customer_id: int = int(c.id)):
                app.storage.user["customer_detail_id"] = customer_id
                app.storage.user["page"] = "customer_detail"
                ui.navigate.to("/")

            with ui.card().classes(C_CARD + " p-4 cursor-pointer " + C_CARD_HOVER).on("click", lambda _, x=int(c.id): open_detail(x)):
                ui.label(c.display_name).classes("font-bold")
                if c.email:
                    ui.label(c.email).classes("text-xs text-slate-500")


def render_customer_detail(session, comp: Company, customer_id: int | None) -> None:
    if not customer_id:
        ui.notify("Kunde nicht gefunden", color="red")
        app.storage.user["page"] = "customers"
        ui.navigate.to("/")
        return

    customer = session.get(Customer, int(customer_id))
    if not customer:
        ui.label("Kunde nicht gefunden").classes(C_PAGE_TITLE)
        ui.button("Zurück", icon="arrow_back", on_click=lambda: (app.storage.user.__setitem__("page", "customers"), ui.navigate.to("/"))).classes(C_BTN_SEC)
        return

    invoices = session.exec(select(Invoice).where(Invoice.customer_id == customer.id).order_by(Invoice.id.desc())).all()
    can_delete = len(invoices) == 0

    def back():
        app.storage.user["page"] = "customers"
        ui.navigate.to("/")

    with ui.row().classes("items-center gap-3 mb-2"):
        ui.button(icon="arrow_back", on_click=back).props("flat round").classes("text-slate-500")
        ui.label(customer.display_name).classes(C_PAGE_TITLE)

    with ui.card().classes(C_CARD + " p-6 w-full max-w-3xl"):
        name = ui.input("Firma", value=customer.name).classes(C_INPUT)
        first = ui.input("Vorname", value=customer.vorname).classes(C_INPUT)
        last = ui.input("Nachname", value=customer.nachname).classes(C_INPUT)
        email = ui.input("Email", value=customer.email).classes(C_INPUT)
        street = ui.input("Straße", value=customer.strasse).classes(C_INPUT)
        plz = ui.input("PLZ", value=customer.plz).classes(C_INPUT)
        city = ui.input("Ort", value=customer.ort).classes(C_INPUT)
        vat = ui.input("USt-ID", value=customer.vat_id).classes(C_INPUT)

        recipient_name = ui.input("Rechnungsempfänger", value=customer.recipient_name).classes(C_INPUT)
        recipient_street = ui.input("Rechnungsstraße", value=customer.recipient_street).classes(C_INPUT)
        recipient_plz = ui.input("Rechnungs-PLZ", value=customer.recipient_postal_code).classes(C_INPUT)
        recipient_city = ui.input("Rechnungs-Ort", value=customer.recipient_city).classes(C_INPUT)

        fields = [name, first, last, email, street, plz, city, vat, recipient_name, recipient_street, recipient_plz, recipient_city]

        def set_editable(editing: bool):
            for f in fields:
                if editing:
                    f.enable()
                else:
                    f.disable()

        set_editable(False)

        def save():
            with get_session() as s:
                c = s.get(Customer, int(customer.id))
                if not c:
                    ui.notify("Kunde nicht gefunden", color="red")
                    return
                c.name = name.value or ""
                c.vorname = first.value or ""
                c.nachname = last.value or ""
                c.email = email.value or ""
                c.strasse = street.value or ""
                c.plz = plz.value or ""
                c.ort = city.value or ""
                c.vat_id = vat.value or ""
                c.recipient_name = recipient_name.value or ""
                c.recipient_street = recipient_street.value or ""
                c.recipient_postal_code = recipient_plz.value or ""
                c.recipient_city = recipient_city.value or ""
                s.add(c)
                s.commit()

            ui.notify("Gespeichert", color="green")
            set_editable(False)
            save_button.disable()
            edit_button.enable()

        def cancel_edit():
            name.value = customer.name
            first.value = customer.vorname
            last.value = customer.nachname
            email.value = customer.email
            street.value = customer.strasse
            plz.value = customer.plz
            city.value = customer.ort
            vat.value = customer.vat_id
            recipient_name.value = customer.recipient_name
            recipient_street.value = customer.recipient_street
            recipient_plz.value = customer.recipient_postal_code
            recipient_city.value = customer.recipient_city

            set_editable(False)
            save_button.disable()
            edit_button.enable()

        with ui.row().classes("gap-2 mt-4"):
            edit_button = ui.button("Bearbeiten", on_click=lambda: (set_editable(True), save_button.enable(), edit_button.disable())).classes(C_BTN_SEC)
            save_button = ui.button("Speichern", on_click=save).classes(C_BTN_PRIM)
            save_button.disable()
            ui.button("Abbrechen", on_click=cancel_edit).classes(C_BTN_SEC)

        def delete_customer():
            with get_session() as s:
                c = s.get(Customer, int(customer.id))
                if not c:
                    ui.notify("Kunde nicht gefunden", color="red")
                    return
                invs = s.exec(select(Invoice).where(Invoice.customer_id == customer.id)).all()
                if invs:
                    ui.notify("Kunde hat Rechnungen und kann nicht gelöscht werden", color="red")
                    return
                s.delete(c)
                s.commit()
            ui.notify("Kunde gelöscht", color="green")
            back()

        def archive_customer():
            with get_session() as s:
                c = s.get(Customer, int(customer.id))
                if not c:
                    ui.notify("Kunde nicht gefunden", color="red")
                    return
                c.archived = True
                s.add(c)
                s.commit()
            ui.notify("Kunde archiviert", color="green")
            back()

        with ui.row().classes("gap-2 mt-2"):
            if can_delete:
                ui.button("Löschen", icon="delete", on_click=delete_customer).classes("bg-rose-600 text-white hover:bg-rose-700")
            else:
                ui.button("Archivieren", icon="archive", on_click=archive_customer).classes(C_BTN_SEC)

    ui.label("Rechnungen").classes(C_SECTION_TITLE + " mt-6 mb-2")
    if not invoices:
        ui.label("Keine Rechnungen vorhanden").classes("text-sm text-slate-500")
    else:
        with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
            with ui.row().classes(C_TABLE_HEADER):
                ui.label("Nr").classes("w-20 font-bold")
                ui.label("Datum").classes("w-28 font-bold")
                ui.label("Status").classes("w-28 font-bold")
                ui.label("Betrag").classes("w-24 font-bold text-right")

            for inv in invoices:
                def open_invoice(target: Invoice = inv):
                    if target.status == InvoiceStatus.DRAFT:
                        _open_invoice_editor(int(target.id))
                    else:
                        _open_invoice_detail(int(target.id))

                with ui.row().classes(C_TABLE_ROW + " cursor-pointer hover:bg-slate-50").on("click", lambda _, x=inv: open_invoice(x)):
                    ui.label(f"#{inv.nr}" if inv.nr else "-").classes("w-20 text-xs font-mono")
                    ui.label(inv.date or "-").classes("w-28 text-xs font-mono")
                    ui.label(format_invoice_status(inv.status)).classes(invoice_status_badge(inv.status))
                    ui.label(f"{float(inv.total_brutto or 0):,.2f} €").classes("w-24 text-right text-sm font-mono")


def render_customer_new(session, comp: Company) -> None:
    ui.label("Neuer Kunde").classes(C_PAGE_TITLE)

    with ui.card().classes(C_CARD + " p-6 w-full max-w-2xl"):
        name = ui.input("Firma").classes(C_INPUT)
        first = ui.input("Vorname").classes(C_INPUT)
        last = ui.input("Nachname").classes(C_INPUT)
        street = ui.input("Straße").classes(C_INPUT)
        plz = ui.input("PLZ").classes(C_INPUT)
        city = ui.input("Ort").classes(C_INPUT)
        email = ui.input("Email").classes(C_INPUT)

        def save():
            with get_session() as s:
                c = Customer(
                    company_id=int(comp.id),
                    kdnr=0,
                    name=name.value or "",
                    vorname=first.value or "",
                    nachname=last.value or "",
                    email=email.value or "",
                    strasse=street.value or "",
                    plz=plz.value or "",
                    ort=city.value or "",
                )
                s.add(c)
                s.commit()
            app.storage.user["page"] = "customers"
            ui.navigate.to("/")

        ui.button("Speichern", on_click=save).classes(C_BTN_PRIM)


# -------------------------
# Exports
# -------------------------

def render_exports(session, comp: Company) -> None:
    ui.label("Exporte").classes(C_PAGE_TITLE + " mb-4")

    def run_export(action, label: str):
        ui.notify("Wird vorbereitet…")
        try:
            with get_session() as s:
                path = action(s)
            if path and os.path.exists(path):
                ui.download(path)
                ui.notify(f"{label} bereit", color="green")
            else:
                ui.notify("Export fehlgeschlagen", color="red")
        except Exception as e:
            ui.notify(f"Fehler: {e}", color="red")

    def export_card(title: str, description: str, action):
        with ui.card().classes(C_CARD + " p-5 " + C_CARD_HOVER + " w-full"):
            ui.label(title).classes("font-semibold text-slate-900")
            ui.label(description).classes("text-sm text-slate-500 mb-2")
            ui.button("Download", icon="download", on_click=action).classes(C_BTN_SEC)

    with ui.grid(columns=2).classes("w-full gap-4"):
        export_card("PDF ZIP", "Alle Rechnungs-PDFs als ZIP-Datei", lambda: run_export(export_invoices_pdf_zip, "PDF ZIP"))
        export_card("Rechnungen CSV", "Alle Rechnungen als CSV-Datei", lambda: run_export(export_invoices_csv, "Rechnungen CSV"))
        export_card("Positionen CSV", "Alle Rechnungspositionen als CSV-Datei", lambda: run_export(export_invoice_items_csv, "Positionen CSV"))
        export_card("Kunden CSV", "Alle Kunden als CSV-Datei", lambda: run_export(export_customers_csv, "Kunden CSV"))

    with ui.expansion("Erweitert").classes("w-full mt-4"):
        with ui.column().classes("w-full gap-2 p-2"):
            export_card("DB-Backup", "SQLite Datenbank sichern", lambda: run_export(export_database_backup, "DB-Backup"))


# -------------------------
# Settings
# -------------------------

def render_settings(session, comp: Company) -> None:
    ui.label("Einstellungen").classes(C_PAGE_TITLE + " mb-6")

    with ui.card().classes(C_CARD + " p-6 w-full mb-4"):
        ui.label("Logo").classes(C_SECTION_TITLE)

        def on_up(e):
            os.makedirs("./storage", exist_ok=True)
            with open("./storage/logo.png", "wb") as f:
                f.write(e.content.read())
            ui.notify("Hochgeladen", color="green")

        ui.upload(on_upload=on_up, auto_upload=True, label="Bild wählen").props("flat dense").classes("w-full")

    with ui.card().classes(C_CARD + " p-6 w-full"):
        name = ui.input("Firma", value=comp.name).classes(C_INPUT)
        first_name = ui.input("Vorname", value=comp.first_name).classes(C_INPUT)
        last_name = ui.input("Nachname", value=comp.last_name).classes(C_INPUT)
        street = ui.input("Straße", value=comp.street).classes(C_INPUT)
        plz = ui.input("PLZ", value=comp.postal_code).classes(C_INPUT)
        city = ui.input("Ort", value=comp.city).classes(C_INPUT)
        email = ui.input("Email", value=comp.email).classes(C_INPUT)
        phone = ui.input("Telefon", value=comp.phone).classes(C_INPUT)
        iban = ui.input("IBAN", value=comp.iban).classes(C_INPUT)
        tax = ui.input("Steuernummer", value=comp.tax_id).classes(C_INPUT)
        vat = ui.input("USt-ID", value=comp.vat_id).classes(C_INPUT)

        def save():
            with get_session() as s:
                c = s.get(Company, int(comp.id))
                c.name = name.value or ""
                c.first_name = first_name.value or ""
                c.last_name = last_name.value or ""
                c.street = street.value or ""
                c.postal_code = plz.value or ""
                c.city = city.value or ""
                c.email = email.value or ""
                c.phone = phone.value or ""
                c.iban = iban.value or ""
                c.tax_id = tax.value or ""
                c.vat_id = vat.value or ""
                s.add(c)
                s.commit()
            ui.notify("Gespeichert", color="green")

        ui.button("Speichern", on_click=save).classes(C_BTN_PRIM)


# -------------------------
# Ledger (Finanzen)
# -------------------------

def render_ledger(session, comp: Company) -> None:
    ui.label("Finanzen").classes(C_PAGE_TITLE + " mb-4")

    def parse_date(value: str | None):
        return _parse_iso_date(value)

    customer_name = func.coalesce(
        func.nullif(Customer.name, ""),
        func.trim(func.coalesce(Customer.vorname, "") + literal(" ") + func.coalesce(Customer.nachname, "")),
    )

    invoice_query = select(
        Invoice.id.label("id"),
        Invoice.date.label("date"),
        Invoice.total_brutto.label("amount"),
        literal("INCOME").label("type"),
        case(
            (Invoice.status == InvoiceStatus.DRAFT, "Draft"),
            (Invoice.status == InvoiceStatus.OPEN, "Open"),
            (Invoice.status == InvoiceStatus.SENT, "Sent"),
            (Invoice.status == InvoiceStatus.PAID, "Paid"),
            (Invoice.status == InvoiceStatus.FINALIZED, "Open"),
            (Invoice.status == InvoiceStatus.CANCELLED, "Cancelled"),
            else_="Overdue",
        ).label("status"),
        func.coalesce(customer_name, literal("?")).label("party"),
        Invoice.title.label("description"),
        Invoice.status.label("invoice_status"),
        Invoice.id.label("invoice_id"),
        literal(None).label("expense_id"),
    ).select_from(Invoice).outerjoin(Customer, Invoice.customer_id == Customer.id)

    expense_query = select(
        Expense.id.label("id"),
        Expense.date.label("date"),
        Expense.amount.label("amount"),
        literal("EXPENSE").label("type"),
        literal("Paid").label("status"),
        func.coalesce(Expense.source, Expense.category, Expense.description, literal("-")).label("party"),
        Expense.description.label("description"),
        literal(None).label("invoice_status"),
        literal(None).label("invoice_id"),
        Expense.id.label("expense_id"),
    )

    rows = session.exec(union_all(invoice_query, expense_query)).all()
    items = []
    for row in rows:
        data = row._mapping if hasattr(row, "_mapping") else row
        items.append({
            "id": data["id"],
            "date": data["date"],
            "amount": float(data["amount"] or 0),
            "type": data["type"],
            "status": data["status"],
            "party": data["party"],
            "description": data["description"] or "",
            "invoice_id": data["invoice_id"],
            "expense_id": data["expense_id"],
            "sort_date": parse_date(data["date"]),
        })
    items.sort(key=lambda x: x["sort_date"], reverse=True)

    state = {"type": "ALL", "status": "ALL", "date_from": "", "date_to": "", "search": ""}

    def apply_filters(data):
        filtered = []
        for it in data:
            if state["type"] != "ALL" and it["type"] != state["type"]:
                continue
            if state["status"] != "ALL" and it["status"] != state["status"]:
                continue
            if state["date_from"] and it["sort_date"] < parse_date(state["date_from"]):
                continue
            if state["date_to"] and it["sort_date"] > parse_date(state["date_to"]):
                continue
            if state["search"]:
                hay = f"{it['party']} {it.get('description','')}".lower()
                if state["search"].lower() not in hay:
                    continue
            filtered.append(it)
        return filtered

    with ui.card().classes(C_CARD + " p-4 mb-4 sticky top-0 z-30"):
        with ui.row().classes("gap-4 w-full items-end flex-wrap"):
            ui.select({"ALL": "Alle", "INCOME": "Income", "EXPENSE": "Expense"}, label="Typ", value=state["type"],
                      on_change=lambda e: (state.__setitem__("type", e.value or "ALL"), render_list.refresh())).classes(C_INPUT)
            ui.select({"ALL": "Alle", "Draft": "Draft", "Open": "Open", "Sent": "Sent", "Paid": "Paid", "Cancelled": "Cancelled"},
                      label="Status", value=state["status"],
                      on_change=lambda e: (state.__setitem__("status", e.value or "ALL"), render_list.refresh())).classes(C_INPUT)
            ui.input("Von", on_change=lambda e: (state.__setitem__("date_from", e.value or ""), render_list.refresh())).props("type=date").classes(C_INPUT)
            ui.input("Bis", on_change=lambda e: (state.__setitem__("date_to", e.value or ""), render_list.refresh())).props("type=date").classes(C_INPUT)
            ui.input("Suche", placeholder="Party oder Beschreibung",
                     on_change=lambda e: (state.__setitem__("search", e.value or ""), render_list.refresh())).classes(C_INPUT + " min-w-[220px]")

    @ui.refreshable
    def render_list():
        data = apply_filters(items)
        if len(data) == 0:
            with ui.card().classes(C_CARD + " p-4"):
                with ui.row().classes("w-full justify-center"):
                    ui.label("Keine Ergebnisse gefunden").classes("text-sm text-slate-500")
            return

        with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
            with ui.element("div").classes(C_TABLE_HEADER + " hidden sm:grid sm:grid-cols-[110px_110px_110px_1fr_120px_120px] items-center"):
                ui.label("Datum").classes("font-bold")
                ui.label("Typ").classes("font-bold")
                ui.label("Status").classes("font-bold")
                ui.label("Kunde/Lieferant").classes("font-bold")
                ui.label("Betrag").classes("font-bold text-right")
                ui.label("").classes("font-bold text-right")

            for it in data:
                with ui.element("div").classes(C_TABLE_ROW + " group grid grid-cols-1 sm:grid-cols-[110px_110px_110px_1fr_120px_120px] gap-2 sm:gap-0 items-start sm:items-center"):
                    with ui.column().classes("gap-1"):
                        ui.label("Datum").classes("sm:hidden text-[10px] uppercase text-slate-400")
                        ui.label(it["date"]).classes("text-xs font-mono")

                    with ui.column().classes("gap-1"):
                        ui.label("Typ").classes("sm:hidden text-[10px] uppercase text-slate-400")
                        badge_class = C_BADGE_GREEN if it["type"] == "INCOME" else "bg-rose-50 text-rose-700 border border-rose-100 px-2 py-0.5 rounded-full text-xs font-medium text-center"
                        ui.label("Income" if it["type"] == "INCOME" else "Expense").classes(badge_class + " w-20")

                    with ui.column().classes("gap-1"):
                        ui.label("Status").classes("sm:hidden text-[10px] uppercase text-slate-400")
                        ui.label(it["status"]).classes("text-xs")

                    with ui.column().classes("gap-1"):
                        ui.label("Kunde/Lieferant").classes("sm:hidden text-[10px] uppercase text-slate-400")
                        ui.label(it["party"]).classes("text-sm")
                        if it.get("description"):
                            ui.label(it["description"]).classes("text-xs text-slate-500")

                    with ui.column().classes("gap-1 sm:items-end"):
                        ui.label("Betrag").classes("sm:hidden text-[10px] uppercase text-slate-400")
                        amount_label = f"{it['amount']:,.2f} €" if it["type"] == "INCOME" else f"-{it['amount']:,.2f} €"
                        amount_class = "text-right text-sm text-emerald-600" if it["type"] == "INCOME" else "text-right text-sm text-rose-600"
                        ui.label(amount_label).classes(amount_class)

                    with ui.row().classes("justify-end gap-1 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition"):
                        if it["invoice_id"]:
                            ui.button(
                                icon="open_in_new",
                                on_click=lambda _, iid=it["invoice_id"]: _open_invoice_detail(int(iid)),
                            ).props("flat dense").classes("text-slate-500")
                        else:
                            ui.label("-").classes("text-xs text-slate-400")

    render_list()


# -------------------------
# Expenses
# -------------------------

def render_expenses(session, comp: Company) -> None:
    ui.label("Ausgaben").classes(C_PAGE_TITLE)
    ui.label("Erfassen, bearbeiten und löschen.").classes("text-sm text-slate-500 mb-4")

    # Local filter state
    state = {
        "search": "",
        "date_from": "",
        "date_to": "",
        "category": "ALL",
    }

    def _parse_date(value: str | None):
        return _parse_iso_date(value)

    def _safe_set(obj, field: str, value):
        if hasattr(obj, field):
            setattr(obj, field, value)

    def _load_expenses():
        rows = session.exec(select(Expense).order_by(Expense.id.desc())).all()

        items = []
        for e in rows:
            items.append({
                "id": int(e.id),
                "date": getattr(e, "date", "") or "",
                "amount": float(getattr(e, "amount", 0) or 0),
                "category": (getattr(e, "category", "") or "").strip(),
                "source": (getattr(e, "source", "") or "").strip(),
                "description": (getattr(e, "description", "") or "").strip(),
                "sort_date": _parse_date(getattr(e, "date", "") or ""),
            })

        # newest first by date, then id
        items.sort(key=lambda x: (x["sort_date"], x["id"]), reverse=True)
        return items

    def _apply_filters(items: list[dict]) -> list[dict]:
        out: list[dict] = []
        for it in items:
            if state["date_from"] and it["sort_date"] < _parse_date(state["date_from"]):
                continue
            if state["date_to"] and it["sort_date"] > _parse_date(state["date_to"]):
                continue
            if state["category"] != "ALL":
                if (it["category"] or "").lower() != (state["category"] or "").lower():
                    continue
            if state["search"]:
                hay = f"{it.get('category','')} {it.get('source','')} {it.get('description','')}".lower()
                if state["search"].lower() not in hay:
                    continue
            out.append(it)
        return out

    items_all = _load_expenses()
    categories = sorted({(x["category"] or "").strip() for x in items_all if (x["category"] or "").strip()})
    category_opts = {"ALL": "Alle"}
    for c in categories:
        category_opts[c] = c

    # Dialog state
    current_id = {"value": None}

    with ui.dialog() as edit_dialog:
        with ui.card().classes(C_CARD + " p-5 w-[640px] max-w-[92vw]"):
            ui.label("Ausgabe").classes(C_SECTION_TITLE)

            d_date = ui.input("Datum").props("type=date").classes(C_INPUT)
            d_amount = ui.number("Betrag (EUR)", min=0, step=0.01).classes(C_INPUT)
            d_category = ui.input("Kategorie", placeholder="z.B. Software, Fahrtkosten").classes(C_INPUT)
            d_source = ui.input("Lieferant", placeholder="z.B. Adobe, Bahn, Amazon").classes(C_INPUT)
            d_desc = ui.textarea("Beschreibung", placeholder="Wofür war das").props("rows=2 auto-grow").classes(C_INPUT)

            with ui.row().classes("justify-end gap-2 mt-3 w-full"):
                ui.button("Abbrechen", on_click=lambda: edit_dialog.close()).classes(C_BTN_SEC)

                def _save():
                    date_val = (d_date.value or "").strip()
                    amount_val = float(d_amount.value or 0)
                    category_val = (d_category.value or "").strip()
                    source_val = (d_source.value or "").strip()
                    desc_val = (d_desc.value or "").strip()

                    if not date_val:
                        ui.notify("Datum fehlt", color="red")
                        return
                    if amount_val <= 0:
                        ui.notify("Betrag muss größer 0 sein", color="red")
                        return

                    with get_session() as s:
                        if current_id["value"]:
                            exp = s.get(Expense, int(current_id["value"]))
                            if not exp:
                                ui.notify("Ausgabe nicht gefunden", color="red")
                                return
                            action = "EXPENSE_UPDATED"
                        else:
                            exp = Expense()
                            action = "EXPENSE_CREATED"

                        _safe_set(exp, "company_id", int(comp.id))
                        _safe_set(exp, "date", date_val)
                        _safe_set(exp, "amount", float(amount_val))
                        _safe_set(exp, "category", category_val)
                        _safe_set(exp, "source", source_val)
                        _safe_set(exp, "description", desc_val)

                        s.add(exp)
                        s.commit()

                        try:
                            log_audit_action(s, action, invoice_id=None)
                            s.commit()
                        except Exception:
                            # Audit is optional, do not block saving
                            pass

                    ui.notify("Gespeichert", color="green")
                    edit_dialog.close()
                    ui.navigate.to("/")

                ui.button("Speichern", on_click=_save).classes(C_BTN_PRIM)

    with ui.dialog() as delete_dialog:
        with ui.card().classes(C_CARD + " p-5 w-[520px] max-w-[92vw]"):
            ui.label("Löschen").classes(C_SECTION_TITLE)
            ui.label("Willst du diese Ausgabe wirklich löschen.").classes("text-sm text-slate-600")

            with ui.row().classes("justify-end gap-2 mt-3 w-full"):
                ui.button("Abbrechen", on_click=lambda: delete_dialog.close()).classes(C_BTN_SEC)

                def _confirm_delete():
                    if not current_id["value"]:
                        delete_dialog.close()
                        return
                    with get_session() as s:
                        exp = s.get(Expense, int(current_id["value"]))
                        if exp:
                            s.delete(exp)
                            s.commit()
                            try:
                                log_audit_action(s, "EXPENSE_DELETED", invoice_id=None)
                                s.commit()
                            except Exception:
                                pass
                    ui.notify("Gelöscht", color="green")
                    delete_dialog.close()
                    ui.navigate.to("/")

                ui.button("Löschen", on_click=_confirm_delete).classes("bg-rose-600 text-white hover:bg-rose-700")

    def open_new():
        current_id["value"] = None
        d_date.value = datetime.now().strftime("%Y-%m-%d")
        d_amount.value = 0
        d_category.value = ""
        d_source.value = ""
        d_desc.value = ""
        edit_dialog.open()

    def open_edit(it: dict):
        current_id["value"] = int(it["id"])
        d_date.value = it.get("date") or datetime.now().strftime("%Y-%m-%d")
        d_amount.value = float(it.get("amount") or 0)
        d_category.value = it.get("category") or ""
        d_source.value = it.get("source") or ""
        d_desc.value = it.get("description") or ""
        edit_dialog.open()

    def open_delete(it: dict):
        current_id["value"] = int(it["id"])
        delete_dialog.open()

    with ui.row().classes("w-full justify-between items-center mb-3 gap-3 flex-wrap"):
        ui.button("Neu", icon="add", on_click=open_new).classes(C_BTN_PRIM)

        with ui.row().classes("gap-2 items-end flex-wrap"):
            ui.input(
                "Suche",
                placeholder="Kategorie, Lieferant, Beschreibung",
                on_change=lambda e: (state.__setitem__("search", e.value or ""), render_list.refresh()),
            ).classes(C_INPUT + " min-w-[260px]")

            ui.select(
                category_opts,
                label="Kategorie",
                value=state["category"],
                on_change=lambda e: (state.__setitem__("category", e.value or "ALL"), render_list.refresh()),
            ).classes(C_INPUT)

            ui.input("Von", on_change=lambda e: (state.__setitem__("date_from", e.value or ""), render_list.refresh())).props("type=date").classes(C_INPUT)
            ui.input("Bis", on_change=lambda e: (state.__setitem__("date_to", e.value or ""), render_list.refresh())).props("type=date").classes(C_INPUT)

    @ui.refreshable
    def render_list():
        data_all = _load_expenses()
        data = _apply_filters(data_all)

        total = sum(float(x["amount"] or 0) for x in data)
        with ui.row().classes("w-full items-center justify-between mb-3"):
            ui.label(f"{len(data)} Einträge").classes("text-sm text-slate-500")
            ui.label(f"Summe: {total:,.2f} €").classes("text-sm font-semibold text-rose-700")

        if not data:
            with ui.card().classes(C_CARD + " p-4"):
                ui.label("Keine Ausgaben gefunden").classes("text-sm text-slate-500")
            return

        with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
            with ui.row().classes(C_TABLE_HEADER):
                ui.label("Datum").classes("w-28 font-bold text-xs text-slate-500")
                ui.label("Kategorie").classes("w-40 font-bold text-xs text-slate-500")
                ui.label("Lieferant").classes("w-44 font-bold text-xs text-slate-500")
                ui.label("Beschreibung").classes("flex-1 font-bold text-xs text-slate-500")
                ui.label("Betrag").classes("w-28 text-right font-bold text-xs text-slate-500")
                ui.label("").classes("w-28 text-right font-bold text-xs text-slate-500")

            for it in data:
                with ui.row().classes(C_TABLE_ROW + " items-start"):
                    ui.label(it["date"] or "-").classes("w-28 text-xs font-mono text-slate-700")
                    ui.label(it["category"] or "-").classes("w-40 text-sm text-slate-900")
                    ui.label(it["source"] or "-").classes("w-44 text-sm text-slate-900")
                    ui.label(it["description"] or "-").classes("flex-1 text-sm text-slate-700")
                    ui.label(f"-{float(it['amount'] or 0):,.2f} €").classes("w-28 text-right text-sm font-mono text-rose-700")

                    with ui.row().classes("w-28 justify-end gap-1"):
                        ui.button(icon="edit", on_click=lambda _, x=it: open_edit(x)).props("flat dense").classes("text-slate-600")
                        ui.button(icon="delete", on_click=lambda _, x=it: open_delete(x)).props("flat dense").classes("text-rose-600")

    render_list()

