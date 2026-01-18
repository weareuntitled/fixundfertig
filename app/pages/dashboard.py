from __future__ import annotations
from ._shared import *

# Auto generated page renderer

def render_dashboard(session, comp: Company) -> None:
    with ui.row().classes("w-full items-center justify-between mb-6"):
        ui.label("Welcome back, Dr. Smith").classes("text-3xl font-bold tracking-tight text-slate-900")
        ui.button("New invoice", icon="add", on_click=lambda: _open_invoice_editor(None)).classes(
            "rounded-full border border-slate-200 bg-white/50 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-white/70"
        )

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

    user = None
    current_user_id = get_current_user_id(session)
    if current_user_id:
        user = session.get(User, current_user_id)

    with ui.element("div").classes("w-full grid grid-cols-12 gap-6 mb-6"):
        kpi_card("Umsatz", f"{umsatz:,.2f} €", "trending_up", "text-emerald-500", "col-span-3")
        kpi_card("Ausgaben", f"{kosten:,.2f} €", "trending_down", "text-rose-500", "col-span-3")
        kpi_card("Offen", f"{offen:,.2f} €", "schedule", "text-blue-500", "col-span-3")
        kpi_card("Rechnungen", f"{len(invs):,}", "receipt_long", "text-slate-500", "col-span-3")

        with ui.card().classes(C_GLASS_CARD + " p-6 col-span-8"):
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

        with ui.card().classes(C_GLASS_CARD + " p-6 col-span-4"):
            ui.label("Profil & Assistent").classes(C_SECTION_TITLE + " mb-4")
            with ui.column().classes("gap-4"):
                ui.label(comp.name or "Unternehmen").classes("text-lg font-semibold text-slate-900")
                if user:
                    display_name = f"{user.first_name} {user.last_name}".strip()
                    ui.label(display_name or user.email).classes("text-sm text-slate-600")
                with ui.row().classes("gap-4"):
                    with ui.column().classes("gap-1"):
                        ui.label("Kunden").classes("text-xs font-semibold text-slate-500 uppercase tracking-wide")
                        ui.label(f"{len(customers):,}").classes("text-xl font-semibold text-slate-800")
                    with ui.column().classes("gap-1"):
                        ui.label("Offene Rechnungen").classes("text-xs font-semibold text-slate-500 uppercase tracking-wide")
                        ui.label(f"{sum(1 for inv in invs if inv.status in (InvoiceStatus.OPEN, InvoiceStatus.SENT, InvoiceStatus.FINALIZED)):,}").classes("text-xl font-semibold text-slate-800")
                ui.separator()
                ui.label("Assistent: Nächste Schritte").classes("text-sm font-semibold text-slate-700")
                with ui.column().classes("gap-2 text-sm text-slate-600"):
                    ui.label("• Zahlungserinnerungen für offene Rechnungen prüfen.")
                    ui.label("• Neue Ausgaben direkt nach dem Kauf erfassen.")
                    ui.label("• Umsatzverlauf monatlich vergleichen.")

    paid_invoices = [
        inv for inv in invs if inv.status in (InvoiceStatus.PAID, InvoiceStatus.FINALIZED)
    ]
    invoice_totals_by_month: dict[datetime, float] = {}
    for inv in paid_invoices:
        dt = _parse_iso_date(inv.date)
        if dt == datetime.min:
            continue
        month_key = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        invoice_totals_by_month[month_key] = invoice_totals_by_month.get(month_key, 0.0) + float(
            inv.total_brutto or 0
        )

    months_sorted = sorted(invoice_totals_by_month.keys())
    month_labels = [month.strftime("%m.%Y") for month in months_sorted]
    month_values = [round(invoice_totals_by_month[month], 2) for month in months_sorted]

    ui.label("Umsatzverlauf").classes(C_SECTION_TITLE + " mb-2")
    with ui.card().classes(C_CARD + " p-4 mb-6"):
        if not month_labels:
            ui.label("Noch keine bezahlten Rechnungen verfügbar.").classes("text-sm text-slate-500 mb-2")
        ui.echart(
            {
                "tooltip": {"trigger": "axis"},
                "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
                "xAxis": {"type": "category", "boundaryGap": False, "data": month_labels},
                "yAxis": {"type": "value"},
                "series": [
                    {
                        "data": month_values,
                        "type": "line",
                        "smooth": True,
                        "smoothMonotone": "x",
                        "showSymbol": False,
                        "lineStyle": {"width": 3},
                        "areaStyle": {
                            "color": {
                                "type": "linear",
                                "x": 0,
                                "y": 0,
                                "x2": 0,
                                "y2": 1,
                                "colorStops": [
                                    {"offset": 0, "color": "rgba(59, 130, 246, 0.45)"},
                                    {"offset": 1, "color": "rgba(59, 130, 246, 0.0)"},
                                ],
                            }
                        },
                    }
                ],
            }
        ).classes("w-full").style("height: 240px")

    with ui.grid(columns=4).classes("w-full gap-4 mb-8"):
        with ui.card().classes(C_CARD + " col-span-4 bg-white/70 border-white/60 backdrop-blur-md shadow-sm"):
            with ui.column().classes("w-full items-center gap-5 py-6"):
                ui.element("div").classes("h-20 w-20 rounded-full bg-blue-100/70 border border-white/80 shadow-inner")
                with ui.row().classes("items-center gap-4"):
                    ui.button(
                        "Neue Rechnung",
                        icon="add",
                        on_click=lambda: _open_invoice_editor(None),
                    ).classes(C_BTN_PRIM + " rounded-full px-6 py-3 text-base")
                    ui.button(
                        "Kunden ansehen",
                        icon="people",
                        on_click=lambda: (app.storage.user.__setitem__("page", "customers"), ui.navigate.to("/")),
                    ).classes(C_BTN_SEC + " rounded-full px-6 py-3 text-base")

    ui.label("Neueste Rechnungen").classes(C_SECTION_TITLE + " mb-2")
    with ui.card().classes(C_CARD + " p-0 overflow-hidden " + C_GLASS_CARD_HOVER):
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
