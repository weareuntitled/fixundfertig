from __future__ import annotations
from ._shared import *
from datetime import datetime

# Auto generated page renderer

def render_dashboard(session, comp: Company) -> None:
    ui.label("Dashboard").classes(C_PAGE_TITLE + " mb-4")

    invs = session.exec(
        select(Invoice)
        .join(Customer, Invoice.customer_id == Customer.id)
        .where(Customer.company_id == comp.id)
    ).all()

    exps = session.exec(
        select(Expense).where(Expense.company_id == comp.id)
    ).all()

    umsatz = sum(float(i.total_brutto or 0) for i in invs if i.status in (InvoiceStatus.PAID, InvoiceStatus.FINALIZED))
    kosten = sum(float(e.amount or 0) for e in exps)
    offen = sum(float(i.total_brutto or 0) for i in invs if i.status in (InvoiceStatus.OPEN, InvoiceStatus.SENT, InvoiceStatus.FINALIZED))

    with ui.grid(columns=3).classes("w-full gap-4 mb-6"):
        kpi_card("Umsatz", f"{umsatz:,.2f} €", "trending_up", "text-emerald-500")
        kpi_card("Ausgaben", f"{kosten:,.2f} €", "trending_down", "text-rose-500")
        kpi_card("Offen", f"{offen:,.2f} €", "schedule", "text-blue-500")

    def shift_month(base: datetime, delta: int) -> datetime:
        month_index = base.month - 1 + delta
        year = base.year + month_index // 12
        month = month_index % 12 + 1
        return base.replace(year=year, month=month, day=1)

    now = datetime.now()
    month_starts = [shift_month(now, delta) for delta in range(-5, 1)]
    month_keys = [(m.year, m.month) for m in month_starts]
    month_labels = [m.strftime("%b") for m in month_starts]
    totals = [0.0 for _ in month_starts]

    for inv in invs:
        if inv.status not in (InvoiceStatus.PAID, InvoiceStatus.FINALIZED):
            continue
        inv_date = _parse_iso_date(inv.date)
        key = (inv_date.year, inv_date.month)
        if key in month_keys:
            totals[month_keys.index(key)] += float(inv.total_brutto or 0)

    with ui.card().classes(C_CARD + " " + C_CARD_HOVER + " p-4 mb-6"):
        ui.label("Umsatzentwicklung").classes(C_SECTION_TITLE + " mb-2")
        ui.echart(
            {
                "tooltip": {"trigger": "axis"},
                "grid": {"left": "8%", "right": "6%", "top": "12%", "bottom": "10%"},
                "xAxis": {
                    "type": "category",
                    "data": month_labels,
                    "axisLine": {"lineStyle": {"color": "#cbd5f5"}},
                    "axisLabel": {"color": "#64748b"},
                },
                "yAxis": {
                    "type": "value",
                    "axisLabel": {"color": "#64748b", "formatter": "{value} €"},
                    "splitLine": {"lineStyle": {"color": "rgba(148, 163, 184, 0.2)"}},
                },
                "series": [
                    {
                        "data": [round(total, 2) for total in totals],
                        "type": "line",
                        "smooth": True,
                        "symbol": "circle",
                        "symbolSize": 6,
                        "lineStyle": {"width": 2, "color": "#3b82f6"},
                        "itemStyle": {"color": "#3b82f6"},
                        "areaStyle": {
                            "color": {
                                "type": "linear",
                                "x": 0,
                                "y": 0,
                                "x2": 0,
                                "y2": 1,
                                "colorStops": [
                                    {"offset": 0, "color": "rgba(59, 130, 246, 0.35)"},
                                    {"offset": 1, "color": "rgba(59, 130, 246, 0.02)"},
                                ],
                            }
                        },
                    }
                ],
            }
        ).classes("w-full h-56")

    ui.label("Neueste Rechnungen").classes(C_SECTION_TITLE + " mb-2")
    with ui.card().classes(C_CARD + " " + C_CARD_HOVER + " p-0 overflow-hidden"):
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
