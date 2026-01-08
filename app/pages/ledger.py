from __future__ import annotations
from ._shared import *
from ._shared import _parse_iso_date

# Auto generated page renderer

def render_ledger(session, comp: Company) -> None:
    ui.label("Finanzen").classes(C_PAGE_TITLE + " mb-4")

    def parse_date(value: str | None):
        return _parse_iso_date(value)

    customer_name = func.coalesce(
        func.nullif(Customer.name, ""),
        func.trim(func.coalesce(Customer.vorname, "") + literal(" ") + func.coalesce(Customer.nachname, "")),
    )

    invoice_query = (
        select(
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
        )
        .select_from(Invoice)
        .outerjoin(Customer, Invoice.customer_id == Customer.id)
        .where(Customer.company_id == comp.id)
    )

    expense_query = (
        select(
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
        .where(Expense.company_id == comp.id)
    )

    rows = session.exec(union_all(invoice_query, expense_query)).all()
    items = []
    for row in rows:
        data = row._mapping if hasattr(row, "_mapping") else row
        items.append(
            {
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
            }
        )
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
