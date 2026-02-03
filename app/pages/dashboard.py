from __future__ import annotations
from ._shared import *
from ._shared import _open_invoice_editor
from datetime import datetime

# Auto generated page renderer

def render_dashboard(session, comp: Company) -> None:
    user = None
    current_user_id = get_current_user_id(session)
    if current_user_id:
        user = session.get(User, current_user_id)
    if user:
        display_name = f"{user.first_name} {user.last_name}".strip()
        greeting_name = display_name or user.email
    else:
        greeting_name = "there"

    def _open_new_invoice() -> None:
        app.storage.user["return_page"] = "dashboard"
        _open_invoice_editor(None)

    with ui.row().classes("w-full items-center justify-between mb-6 flex-col sm:flex-row gap-3"):
        ui.label(f"Welcome back, {greeting_name}").classes("text-3xl font-bold tracking-tight text-slate-900")
        ui.button("New invoice", icon="add", on_click=_open_new_invoice).classes(C_BTN_PRIM)

    invs = session.exec(
        select(Invoice)
        .join(Customer, Invoice.customer_id == Customer.id)
        .where(Customer.company_id == comp.id)
    ).all()

    customers = session.exec(
        select(Customer).where(Customer.company_id == comp.id)
    ).all()

    exps = session.exec(
        select(Expense).where(Expense.company_id == comp.id)
    ).all()

    umsatz = sum(float(i.total_brutto or 0) for i in invs if i.status in (InvoiceStatus.PAID, InvoiceStatus.FINALIZED))
    kosten = sum(float(e.amount or 0) for e in exps)
    offen = sum(float(i.total_brutto or 0) for i in invs if i.status in (InvoiceStatus.OPEN, InvoiceStatus.SENT, InvoiceStatus.FINALIZED))

    def shift_month(date_value: datetime, months: int) -> datetime:
        month_index = date_value.month - 1 + months
        year = date_value.year + month_index // 12
        month = month_index % 12 + 1
        return date_value.replace(year=year, month=month, day=1)

    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_starts = [shift_month(month_start, -offset) for offset in range(5, -1, -1)]
    month_labels = [start.strftime("%b %y") for start in month_starts]
    month_totals = []
    for start in month_starts:
        end = shift_month(start, 1)
        total = sum(
            float(inv.total_brutto or 0)
            for inv in invs
            if inv.status in (InvoiceStatus.PAID, InvoiceStatus.FINALIZED)
            and start <= _parse_iso_date(inv.date) < end
        )
        month_totals.append(round(total, 2))

    def sum_invoices(start: datetime, end: datetime, statuses: tuple[InvoiceStatus, ...]) -> float:
        return sum(
            float(inv.total_brutto or 0)
            for inv in invs
            if inv.status in statuses and start <= _parse_iso_date(inv.date) < end
        )

    def sum_expenses(start: datetime, end: datetime) -> float:
        return sum(
            float(exp.amount or 0)
            for exp in exps
            if start <= _parse_iso_date(exp.date) < end
        )

    def count_invoices(start: datetime, end: datetime) -> int:
        return sum(1 for inv in invs if start <= _parse_iso_date(inv.date) < end)

    def build_trend(current: float, previous: float) -> tuple[str, str, str]:
        if previous == 0:
            percent = 0 if current == 0 else 100
        else:
            percent = ((current - previous) / previous) * 100
        direction = "up" if percent > 0 else "down" if percent < 0 else "flat"
        color = "text-emerald-500" if direction == "up" else "text-rose-500" if direction == "down" else "text-slate-500"
        return f"{abs(percent):.0f}% vs last month", direction, color

    previous_month_start = shift_month(month_start, -1)
    next_month_start = shift_month(month_start, 1)
    revenue_trend = build_trend(
        sum_invoices(month_start, next_month_start, (InvoiceStatus.PAID, InvoiceStatus.FINALIZED)),
        sum_invoices(previous_month_start, month_start, (InvoiceStatus.PAID, InvoiceStatus.FINALIZED)),
    )
    expense_trend = build_trend(
        sum_expenses(month_start, next_month_start),
        sum_expenses(previous_month_start, month_start),
    )
    open_trend = build_trend(
        sum_invoices(month_start, next_month_start, (InvoiceStatus.OPEN, InvoiceStatus.SENT, InvoiceStatus.FINALIZED)),
        sum_invoices(previous_month_start, month_start, (InvoiceStatus.OPEN, InvoiceStatus.SENT, InvoiceStatus.FINALIZED)),
    )
    invoice_trend = build_trend(
        count_invoices(month_start, next_month_start),
        count_invoices(previous_month_start, month_start),
    )

    with ui.element("div").classes("w-full grid grid-cols-12 gap-6 mb-6"):
        kpi_card(
            "Umsatz",
            f"{umsatz:,.2f} €",
            "trending_up",
            "text-emerald-500",
            "col-span-12 sm:col-span-6 lg:col-span-3",
            trend_text=revenue_trend[0],
            trend_direction=revenue_trend[1],
            trend_color=revenue_trend[2],
        )
        kpi_card(
            "Ausgaben",
            f"{kosten:,.2f} €",
            "trending_down",
            "text-rose-500",
            "col-span-12 sm:col-span-6 lg:col-span-3",
            trend_text=expense_trend[0],
            trend_direction=expense_trend[1],
            trend_color=expense_trend[2],
        )
        kpi_card(
            "Offen",
            f"{offen:,.2f} €",
            "schedule",
            "text-blue-500",
            "col-span-12 sm:col-span-6 lg:col-span-3",
            trend_text=open_trend[0],
            trend_direction=open_trend[1],
            trend_color=open_trend[2],
        )
        kpi_card(
            "Rechnungen",
            f"{len(invs):,}",
            "receipt_long",
            "text-slate-500",
            "col-span-12 sm:col-span-6 lg:col-span-3",
            trend_text=invoice_trend[0],
            trend_direction=invoice_trend[1],
            trend_color=invoice_trend[2],
        )

        with ui.card().classes(C_GLASS_CARD + " p-6 col-span-12 lg:col-span-8"):
            ui.label("Umsatzverlauf").classes(C_SECTION_TITLE + " mb-4")
            ui.echart({
                "tooltip": {"trigger": "axis"},
                "grid": {"left": "3%", "right": "3%", "top": "10%", "bottom": "3%", "containLabel": True},
                "xAxis": {"type": "category", "data": month_labels, "axisLabel": {"color": "#64748b"}},
                "yAxis": {"type": "value", "axisLabel": {"color": "#64748b"}},
                "series": [{
                    "data": month_totals,
                    "type": "line",
                    "smooth": True,
                    "symbol": "circle",
                    "symbolSize": 6,
                    "lineStyle": {"color": "#3b82f6", "width": 3},
                    "areaStyle": {"color": "rgba(59, 130, 246, 0.12)"},
                }],
            }).classes("w-full h-64")

        with ui.card().classes(C_GLASS_CARD + " p-6 col-span-12 lg:col-span-4"):
            ui.label("Profil & Assistent").classes(C_SECTION_TITLE + " mb-4")
            with ui.column().classes("gap-4"):
                ui.label(comp.name or "Unternehmen").classes("text-lg font-semibold text-slate-900")
                if user:
                    display_name = f"{user.first_name} {user.last_name}".strip()
                    ui.label(display_name or user.email).classes("text-sm text-slate-600")
                with ui.row().classes("gap-4"):
                    with ui.column().classes("gap-1"):
                        ui.label("Kunden").classes("text-xs font-semibold text-slate-500 uppercase tracking-wide")
                        ui.label(f"{len(customers):,}").classes(f"text-xl font-semibold text-slate-800 {C_NUMERIC}")
                    with ui.column().classes("gap-1"):
                        ui.label("Offene Rechnungen").classes("text-xs font-semibold text-slate-500 uppercase tracking-wide")
                        ui.label(f"{sum(1 for inv in invs if inv.status in (InvoiceStatus.OPEN, InvoiceStatus.SENT, InvoiceStatus.FINALIZED)):,}").classes(f"text-xl font-semibold text-slate-800 {C_NUMERIC}")
                ui.separator()
                ui.label("Assistent: Nächste Schritte").classes("text-sm font-semibold text-slate-700")
                with ui.column().classes("gap-2 text-sm text-slate-600"):
                    ui.label("• Zahlungserinnerungen für offene Rechnungen prüfen.")
                    ui.label("• Neue Ausgaben direkt nach dem Kauf erfassen.")
                    ui.label("• Umsatzverlauf monatlich vergleichen.")
