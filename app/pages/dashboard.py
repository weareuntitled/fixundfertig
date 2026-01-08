from __future__ import annotations
from ._shared import *

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
