from __future__ import annotations
from ._shared import *

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

    def _invoice_sort_date(invoice: Invoice) -> datetime:
        if invoice.updated_at:
            parsed = _parse_iso_date(invoice.updated_at)
            if parsed != datetime.min:
                return parsed
        return _parse_iso_date(invoice.date)

    def _invoice_display_date(invoice: Invoice) -> str:
        display_date = (invoice.date or "").strip()
        if display_date:
            return display_date
        parsed = _invoice_sort_date(invoice)
        return parsed.strftime("%Y-%m-%d") if parsed != datetime.min else ""

    def _document_display_date(doc: Document) -> str:
        for value in (doc.doc_date, doc.invoice_date):
            if (value or "").strip():
                return str(value).strip()
        created_at = doc.created_at if isinstance(doc.created_at, datetime) else datetime.min
        return created_at.strftime("%Y-%m-%d") if created_at != datetime.min else ""

    def _document_sort_date(doc: Document) -> datetime:
        date_value = (doc.doc_date or "").strip() or (doc.invoice_date or "").strip()
        if date_value:
            parsed = _parse_iso_date(date_value)
            if parsed != datetime.min:
                return parsed
        return doc.created_at if isinstance(doc.created_at, datetime) else datetime.min

    def _document_status(doc: Document) -> str:
        amount_total = doc.amount_total
        if amount_total is None and doc.gross_amount is not None:
            amount_total = doc.gross_amount
        has_vendor = bool((doc.vendor or "").strip())
        return "Paid" if amount_total is not None or has_vendor else "Pending"

    def _document_icon(mime_value: str, filename: str) -> tuple[str, str]:
        lower_mime = (mime_value or "").lower()
        lower_name = (filename or "").lower()
        if "pdf" in lower_mime or lower_name.endswith(".pdf"):
            return "picture_as_pdf", "bg-rose-100 text-rose-600"
        if lower_mime.startswith("image/") or lower_name.endswith((".png", ".jpg", ".jpeg")):
            return "image", "bg-emerald-100 text-emerald-600"
        return "insert_drive_file", "bg-slate-100 text-slate-700"

    def _load_doc_items() -> list[dict]:
        invoice_rows = session.exec(
            select(Invoice)
            .join(Customer, Invoice.customer_id == Customer.id)
            .where(Customer.company_id == int(comp.id or 0))
            .order_by(Invoice.id.desc())
        ).all()
        invoice_items: list[dict] = []
        for inv in invoice_rows:
            customer = session.get(Customer, int(inv.customer_id)) if inv.customer_id else None
            customer_name = customer.display_name if customer else ""
            title = inv.title or "Rechnung"
            if customer_name:
                title = f"{title} – {customer_name}"
            invoice_items.append(
                {
                    "title": title,
                    "date": _invoice_display_date(inv),
                    "type": "Invoice",
                    "status": "Paid" if inv.status == InvoiceStatus.PAID else "Pending",
                    "icon": "description",
                    "accent": "bg-blue-100 text-blue-600",
                    "sort_date": _invoice_sort_date(inv),
                    "on_click": lambda _, invoice_id=int(inv.id): _open_invoice_detail(invoice_id),
                }
            )

        document_rows = session.exec(
            select(Document)
            .where(Document.company_id == int(comp.id or 0))
            .order_by(Document.created_at.desc())
        ).all()
        document_items: list[dict] = []
        for doc in document_rows:
            if doc.id is None:
                continue
            filename = doc.original_filename or doc.filename or doc.title or "Dokument"
            mime_value = doc.mime or doc.mime_type or ""
            icon_name, accent = _document_icon(mime_value, filename)
            doc_type = (doc.doc_type or doc.document_type or "").strip() or "Document"
            doc_id = int(doc.id)
            open_url = f"/api/documents/{doc_id}/file"
            document_items.append(
                {
                    "title": doc.title or filename,
                    "date": _document_display_date(doc),
                    "type": doc_type.capitalize(),
                    "status": _document_status(doc),
                    "icon": icon_name,
                    "accent": accent,
                    "sort_date": _document_sort_date(doc),
                    "on_click": lambda _, url=open_url: ui.navigate.to(url),
                }
            )

        items = invoice_items + document_items
        items.sort(key=lambda item: item["sort_date"], reverse=True)
        return items[:8]

    doc_items = _load_doc_items()

    status_badge = {
        "Paid": "bg-emerald-100 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full text-xs font-semibold",
        "Pending": "bg-orange-100 text-orange-700 border border-orange-200 px-2 py-0.5 rounded-full text-xs font-semibold",
    }

    filters = ["All", "Paid", "Pending"]
    active_filter = {"value": "All"}

    def set_filter(value: str) -> None:
        active_filter["value"] = value
        render_cards.refresh()

    with ui.row().classes("w-full items-center justify-between mb-6 flex-col lg:flex-row gap-4"):
        with ui.column().classes("gap-1"):
            ui.label("Dashboard").classes("text-3xl font-bold tracking-tight text-slate-900")
            ui.label(f"Welcome back, {greeting_name}").classes("text-sm text-slate-500")
        with ui.row().classes(
            "rounded-full bg-white/80 backdrop-blur-md border border-white/60 shadow-sm p-1 gap-1"
        ):
            for value in filters:
                is_active = active_filter["value"] == value
                cls = (
                    "px-4 py-1.5 rounded-full text-sm font-semibold transition-all "
                    + ("bg-slate-900 text-white shadow-sm" if is_active else "text-slate-600 hover:text-slate-900")
                )
                ui.button(value, on_click=lambda v=value: set_filter(v)).props("flat dense").classes(cls)

    @ui.refreshable
    def render_cards() -> None:
        if active_filter["value"] == "All":
            visible_items = doc_items
        else:
            visible_items = [item for item in doc_items if item["status"] == active_filter["value"]]

        with ui.element("div").classes("w-full grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6"):
            for item in visible_items:
                with ui.element("div").classes(
                    "group relative bg-white rounded-[24px] p-5 shadow-sm hover:-translate-y-1 "
                    "hover:shadow-2xl transition-all duration-200"
                ).on("click", item["on_click"]):
                    ui.button(icon="more_horiz").props("flat round dense no-parent-event").classes(
                        "absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition text-slate-500 hover:text-slate-800"
                    )
                    with ui.column().classes("gap-4"):
                        with ui.element("div").classes(
                            "h-28 rounded-2xl bg-slate-50 flex items-center justify-center"
                        ):
                            with ui.element("div").classes(
                                f"w-16 h-16 rounded-full {item['accent']} flex items-center justify-center"
                            ):
                                ui.icon(item["icon"]).classes("text-3xl")
                        with ui.column().classes("gap-2"):
                            ui.label(item["title"]).classes("text-base font-semibold text-slate-900 truncate")
                            with ui.row().classes("items-center justify-between gap-2"):
                                ui.label(item["date"]).classes("text-xs text-slate-500")
                                ui.label(item["type"]).classes(
                                    "bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded-full text-xs font-semibold"
                                )
                            ui.label(item["status"]).classes(status_badge[item["status"]])

    render_cards()
