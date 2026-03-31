from __future__ import annotations
from ._shared import *
from ._shared import _parse_iso_date
from styles import STYLE_TEXT_MUTED
from ui_components import ff_btn_danger, ff_btn_primary, ff_btn_secondary, ff_card, ff_icon_button

# Auto generated page renderer

def render_expenses(session, comp: Company) -> None:
    ui.label("Ausgaben").classes(C_PAGE_TITLE)
    ui.label("Erfassen, bearbeiten und löschen.").classes(f"{STYLE_TEXT_MUTED} mb-4")

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
        with ff_card(pad="p-5", classes="w-full max-w-[92vw] max-h-[85vh] overflow-y-auto"):
            ui.label("Ausgabe").classes(C_SECTION_TITLE)

            d_date = ui.input("Datum").props("outlined dense type=date").classes(C_INPUT)
            d_amount = ui.number("Betrag (EUR)", min=0, step=0.01).props("outlined dense").classes(C_INPUT)
            d_category = ui.input("Kategorie", placeholder="z.B. Software, Fahrtkosten").props("outlined dense").classes(C_INPUT)
            d_source = ui.input("Lieferant", placeholder="z.B. Adobe, Bahn, Amazon").props("outlined dense").classes(C_INPUT)
            d_desc = (
                ui.textarea("Beschreibung", placeholder="Wofür war das")
                .props("outlined dense rows=2 auto-grow")
                .classes(C_INPUT)
            )

            with ui.row().classes("justify-end gap-2 mt-3 w-full"):
                ff_btn_secondary("Abbrechen", on_click=lambda: edit_dialog.close())

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
                    go_app_page("expenses")

                ff_btn_primary("Speichern", on_click=_save)

    with ui.dialog() as delete_dialog:
        with ff_card(pad="p-5", classes="w-full max-w-[92vw] max-h-[85vh] overflow-y-auto"):
            ui.label("Löschen").classes(C_SECTION_TITLE)
            ui.label("Willst du diese Ausgabe wirklich löschen.").classes(STYLE_TEXT_MUTED)

            with ui.row().classes("justify-end gap-2 mt-3 w-full"):
                ff_btn_secondary("Abbrechen", on_click=lambda: delete_dialog.close())

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
                    go_app_page("expenses")

                ff_btn_danger("Löschen", on_click=_confirm_delete)

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

    with ff_card(pad="p-3 sm:p-4", classes="w-full mb-4"):
        with ui.row().classes("w-full items-end gap-3 flex-wrap"):
            ff_btn_primary("Neu", icon="add", on_click=open_new, classes="shrink-0")
            ui.input(
                "Suche",
                placeholder="Kategorie, Lieferant, Beschreibung",
                on_change=lambda e: (state.__setitem__("search", e.value or ""), render_list.refresh()),
            ).props("outlined dense").classes(C_INPUT + " flex-1 min-w-[12rem] max-w-md")
            ui.select(
                category_opts,
                label="Kategorie",
                value=state["category"],
                on_change=lambda e: (state.__setitem__("category", e.value or "ALL"), render_list.refresh()),
            ).props("outlined dense").classes(C_INPUT + " w-full sm:w-44")
            ui.input(
                "Von",
                on_change=lambda e: (state.__setitem__("date_from", e.value or ""), render_list.refresh()),
            ).props("outlined dense type=date").classes(C_INPUT + " w-full sm:w-36")
            ui.input(
                "Bis",
                on_change=lambda e: (state.__setitem__("date_to", e.value or ""), render_list.refresh()),
            ).props("outlined dense type=date").classes(C_INPUT + " w-full sm:w-36")

    @ui.refreshable
    def render_list():
        data_all = _load_expenses()
        data = _apply_filters(data_all)

        total = sum(float(x["amount"] or 0) for x in data)
        with ui.row().classes("w-full items-center justify-between mb-3 gap-2"):
            ui.label(f"{len(data)} Einträge").classes(STYLE_TEXT_MUTED)
            ui.label(f"Summe: {total:,.2f} €").classes(f"text-sm font-semibold text-rose-600 {C_NUMERIC}")

        if not data:
            with ff_card(pad="p-4"):
                ui.label("Keine Ausgaben gefunden").classes(STYLE_TEXT_MUTED)
            return

        def _row_meta(it: dict) -> str:
            parts = [p for p in [(it["category"] or "").strip(), (it["source"] or "").strip()] if p]
            return " · ".join(parts) if parts else ""

        with ff_card(pad="p-0", classes="overflow-hidden"):
            with ui.row().classes(C_TABLE_HEADER + " hidden sm:flex items-center px-3 py-2.5"):
                ui.label("Datum").classes("w-24 shrink-0")
                ui.label("Ausgabe").classes("flex-1 min-w-0")
                ui.label("Betrag").classes("w-24 shrink-0 text-right")
                ui.label("").classes("w-10 shrink-0")

            for it in data:
                desc = (it["description"] or "").strip() or "—"
                meta = _row_meta(it)
                amt = f"−{float(it['amount'] or 0):,.2f} €"

                with ui.row().classes(
                    C_TABLE_ROW + " hidden sm:flex items-center px-3 py-2.5 gap-2 border-slate-200/80"
                ):
                    ui.label(it["date"] or "—").classes("w-24 shrink-0 text-sm font-mono text-slate-600")
                    with ui.column().classes("flex-1 min-w-0 gap-0.5 py-0.5"):
                        ui.label(desc).classes("text-sm text-slate-900 truncate")
                        if meta:
                            ui.label(meta).classes("text-xs text-slate-500 truncate")
                    ui.label(amt).classes(f"w-24 shrink-0 text-right text-sm font-mono text-rose-600 {C_NUMERIC}")
                    with ff_icon_button(icon="more_vert", props="dense no-parent-event"):
                        with ui.menu().props("auto-close"):
                            ui.menu_item("Bearbeiten", on_click=lambda _, x=it: open_edit(x))
                            ui.menu_item("Löschen", on_click=lambda _, x=it: open_delete(x)).classes(
                                "text-rose-600"
                            )

                with ui.row().classes(
                    "sm:hidden items-center gap-2 px-3 py-3 border-b border-slate-200/70 last:border-b-0"
                ):
                    with ui.column().classes("flex-1 min-w-0 gap-0.5"):
                        ui.label(desc).classes("text-sm font-semibold text-slate-900 truncate")
                        sub = " · ".join(p for p in [it["date"] or "—", meta] if p)
                        ui.label(sub).classes("text-xs text-slate-500 truncate")
                    ui.label(amt).classes(f"text-sm font-mono text-rose-600 shrink-0 {C_NUMERIC}")
                    with ff_icon_button(icon="more_vert", props="dense no-parent-event"):
                        with ui.menu().props("auto-close"):
                            ui.menu_item("Bearbeiten", on_click=lambda _, x=it: open_edit(x))
                            ui.menu_item("Löschen", on_click=lambda _, x=it: open_delete(x)).classes(
                                "text-rose-600"
                            )

    render_list()
