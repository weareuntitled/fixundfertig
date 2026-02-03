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

    doc_items = [
        {
            "title": "March Invoice – ACME Studio",
            "date": "Mar 12, 2024",
            "type": "Invoice",
            "status": "Paid",
            "icon": "description",
            "accent": "bg-blue-100 text-blue-600",
        },
        {
            "title": "Receipt – Office Supplies",
            "date": "Mar 08, 2024",
            "type": "Receipt",
            "status": "Pending",
            "icon": "receipt_long",
            "accent": "bg-orange-100 text-orange-600",
        },
        {
            "title": "Product Shoot – Asset Pack",
            "date": "Mar 05, 2024",
            "type": "Image",
            "status": "Paid",
            "icon": "image",
            "accent": "bg-emerald-100 text-emerald-600",
        },
        {
            "title": "Travel Invoice – April",
            "date": "Apr 02, 2024",
            "type": "PDF",
            "status": "Pending",
            "icon": "picture_as_pdf",
            "accent": "bg-slate-100 text-slate-700",
        },
        {
            "title": "Studio Rent – Q1",
            "date": "Mar 28, 2024",
            "type": "Invoice",
            "status": "Paid",
            "icon": "description",
            "accent": "bg-violet-100 text-violet-600",
        },
        {
            "title": "Client Receipt – Catering",
            "date": "Mar 23, 2024",
            "type": "Receipt",
            "status": "Pending",
            "icon": "receipt_long",
            "accent": "bg-amber-100 text-amber-700",
        },
        {
            "title": "Workshop Photos – Batch 4",
            "date": "Mar 19, 2024",
            "type": "Image",
            "status": "Paid",
            "icon": "image",
            "accent": "bg-teal-100 text-teal-700",
        },
        {
            "title": "Insurance Policy – Renewal",
            "date": "Mar 15, 2024",
            "type": "PDF",
            "status": "Pending",
            "icon": "picture_as_pdf",
            "accent": "bg-rose-100 text-rose-600",
        },
    ]

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
                ):
                    ui.button(icon="more_horiz").props("flat round dense").classes(
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
