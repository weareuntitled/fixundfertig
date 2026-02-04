from __future__ import annotations
from ._shared import *
from ._shared import _parse_iso_date

# Auto generated page renderer

def render_expenses(session, comp: Company) -> None:
    ui.label("Ausgaben").classes(C_PAGE_TITLE)
    ui.label("Erfassen, bearbeiten und löschen.").classes("text-sm text-neutral-400 mb-4")

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
                        ui.notify("Datum fehlt", color="orange")
                        return
                    if amount_val <= 0:
                        ui.notify("Betrag muss größer 0 sein", color="orange")
                        return

                    with get_session() as s:
                        if current_id["value"]:
                            exp = s.get(Expense, int(current_id["value"]))
                            if not exp:
                                ui.notify("Ausgabe nicht gefunden", color="orange")
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

                    ui.notify("Gespeichert", color="grey")
                    edit_dialog.close()
                    ui.navigate.to("/")

                ui.button("Speichern", on_click=_save).classes(C_BTN_PRIM)

    with ui.dialog() as delete_dialog:
        with ui.card().classes(C_CARD + " p-5 w-[520px] max-w-[92vw]"):
            ui.label("Löschen").classes(C_SECTION_TITLE)
            ui.label("Willst du diese Ausgabe wirklich löschen.").classes("text-sm text-neutral-400")

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
                    ui.notify("Gelöscht", color="grey")
                    delete_dialog.close()
                    ui.navigate.to("/")

                ui.button("Löschen", on_click=_confirm_delete).classes(C_BTN_PRIM)

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
            ui.label(f"{len(data)} Einträge").classes("text-sm text-neutral-400")
            ui.label(f"Summe: {total:,.2f} €").classes("text-sm font-semibold text-amber-300")

        if not data:
            with ui.card().classes(C_CARD + " p-4"):
                ui.label("Keine Ausgaben gefunden").classes("text-sm text-neutral-400")
            return

        with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
            with ui.row().classes(C_TABLE_HEADER):
                ui.label("Datum").classes("w-28 font-bold text-xs text-neutral-400")
                ui.label("Kategorie").classes("w-40 font-bold text-xs text-neutral-400")
                ui.label("Lieferant").classes("w-44 font-bold text-xs text-neutral-400")
                ui.label("Beschreibung").classes("flex-1 font-bold text-xs text-neutral-400")
                ui.label("Betrag").classes("w-28 text-right font-bold text-xs text-neutral-400")
                ui.label("").classes("w-28 text-right font-bold text-xs text-neutral-400")

            for it in data:
                with ui.row().classes(C_TABLE_ROW + " items-start"):
                    ui.label(it["date"] or "-").classes("w-28 text-xs font-mono text-neutral-200")
                    ui.label(it["category"] or "-").classes("w-40 text-sm text-neutral-100")
                    ui.label(it["source"] or "-").classes("w-44 text-sm text-neutral-100")
                    ui.label(it["description"] or "-").classes("flex-1 text-sm text-neutral-200")
                    ui.label(f"-{float(it['amount'] or 0):,.2f} €").classes("w-28 text-right text-sm font-mono text-amber-300")

                    with ui.row().classes("w-28 justify-end gap-1"):
                        ui.button(icon="edit", on_click=lambda _, x=it: open_edit(x)).props("flat dense").classes("text-neutral-300")
                        ui.button(icon="delete", on_click=lambda _, x=it: open_delete(x)).props("flat dense").classes("text-amber-400")

    render_list()
