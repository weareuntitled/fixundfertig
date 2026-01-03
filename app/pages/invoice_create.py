from __future__ import annotations
from ._shared import *

# Auto generated page renderer

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
    recipient_defaults = {"name": "", "street": "", "zip": "", "city": ""}
    if state["customer_id"]:
        with get_session() as s:
            c = s.get(Customer, int(state["customer_id"]))
            if c:
                recipient_defaults = {
                    "name": c.recipient_name or c.display_name or "",
                    "street": c.recipient_street or c.strasse or "",
                    "zip": c.recipient_postal_code or c.plz or "",
                    "city": c.recipient_city or c.ort or "",
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
                if not inv:
                    draft_id = None
            if not draft_id:
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

                    cust_select = ui.select(
                        cust_opts,
                        label="Kunde",
                        value=state["customer_id"],
                        with_input=True,
                    ).classes(C_INPUT)

                    def on_cust(value):
                        state["customer_id"] = value
                        mark_dirty()
                        if value:
                            with get_session() as s:
                                c = s.get(Customer, int(value))
                                if c:
                                    rec_name.value = c.recipient_name or c.display_name
                                    rec_street.value = c.recipient_street or c.strasse
                                    rec_zip.value = c.recipient_postal_code or c.plz
                                    rec_city.value = c.recipient_city or c.ort
                        request_preview_update()

                    def on_cust_event(e):
                        value = None
                        if hasattr(e, "args") and isinstance(e.args, dict):
                            value = e.args.get("value")
                        elif hasattr(e, "value"):
                            value = e.value
                        on_cust(value)

                    cust_select.on("update:model-value", on_cust_event)

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
                        rec_name = ui.input(
                            "Name",
                            value=recipient_defaults["name"],
                            on_change=lambda e: (mark_dirty(), request_preview_update()),
                        ).classes(C_INPUT + " dense")
                        rec_street = ui.input(
                            "Straße",
                            value=recipient_defaults["street"],
                            on_change=lambda e: (mark_dirty(), request_preview_update()),
                        ).classes(C_INPUT + " dense")
                        with ui.row().classes("w-full gap-2"):
                            rec_zip = ui.input(
                                "PLZ",
                                value=recipient_defaults["zip"],
                                on_change=lambda e: (mark_dirty(), request_preview_update()),
                            ).classes(C_INPUT + " w-20 dense")
                            rec_city = ui.input(
                                "Ort",
                                value=recipient_defaults["city"],
                                on_change=lambda e: (mark_dirty(), request_preview_update()),
                            ).classes(C_INPUT + " flex-1 dense")

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
