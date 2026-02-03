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

    mock_items = [
        {"title": "Invoice 2024-081", "type": "PDF", "badge": "Invoice", "date": "13 Mar 2024", "status": "Paid"},
        {"title": "Receipt - Office Supplies", "type": "Receipt", "badge": "Receipt", "date": "11 Mar 2024", "status": "Pending"},
        {"title": "Website Hero Shots", "type": "Image", "badge": "Image", "date": "10 Mar 2024", "status": "Paid"},
        {"title": "Invoice 2024-079", "type": "PDF", "badge": "Invoice", "date": "08 Mar 2024", "status": "Pending"},
        {"title": "Taxi Receipt - Berlin", "type": "Receipt", "badge": "Receipt", "date": "06 Mar 2024", "status": "Paid"},
        {"title": "Brand Moodboard", "type": "Image", "badge": "Image", "date": "04 Mar 2024", "status": "Paid"},
        {"title": "Invoice 2024-076", "type": "PDF", "badge": "Invoice", "date": "02 Mar 2024", "status": "Pending"},
        {"title": "Camera Receipt - Q1", "type": "Receipt", "badge": "Receipt", "date": "28 Feb 2024", "status": "Paid"},
    ]

    filter_state = {"value": "All"}

    def filter_items() -> list[dict]:
        active = filter_state["value"]
        if active == "All":
            return mock_items
        mapping = {"PDFs": "PDF", "Images": "Image", "Receipts": "Receipt"}
        return [item for item in mock_items if item["type"] == mapping.get(active, active)]

    with ui.row().classes("w-full items-center justify-between mb-8 flex-col lg:flex-row gap-4"):
        with ui.column().classes("gap-1"):
            ui.label("Dashboard").classes("text-3xl font-bold tracking-tight text-slate-900")
            ui.label(f"Welcome back, {greeting_name}.").classes("text-sm text-slate-500")

        with ui.row().classes(
            "items-center gap-1 bg-white/80 backdrop-blur rounded-full p-1 shadow-sm border border-white/80"
        ):
            for option in ["All", "PDFs", "Images", "Receipts"]:
                active = filter_state["value"] == option
                button_cls = (
                    "px-4 py-1.5 rounded-full text-sm font-semibold transition-all"
                    + (" bg-slate-900 text-white" if active else " text-slate-600 hover:text-slate-900")
                )

                def _set_filter(value: str = option) -> None:
                    filter_state["value"] = value
                    grid_view.refresh()

                ui.button(option, on_click=_set_filter).props("flat").classes(button_cls)

    @ui.refreshable
    def grid_view() -> None:
        with ui.element("div").classes("w-full grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6"):
            for item in filter_items():
                icon_map = {
                    "PDF": ("description", "bg-indigo-100 text-indigo-600"),
                    "Image": ("image", "bg-emerald-100 text-emerald-600"),
                    "Receipt": ("receipt_long", "bg-amber-100 text-amber-700"),
                }
                icon_name, icon_style = icon_map.get(item["type"], ("description", "bg-slate-100 text-slate-600"))
                status_class = (
                    "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    if item["status"] == "Paid"
                    else "bg-amber-50 text-amber-700 border border-amber-200"
                )

                with ui.element("div").classes(
                    "group bg-white rounded-[24px] p-5 border border-white/70 shadow-sm hover:-translate-y-1 "
                    "hover:shadow-2xl transition-all duration-200 flex flex-col gap-4"
                ):
                    with ui.element("div").classes(
                        "flex items-center justify-center h-32 rounded-2xl bg-slate-50/80"
                    ):
                        with ui.element("div").classes(f"w-16 h-16 rounded-full {icon_style} flex items-center justify-center"):
                            ui.icon(icon_name).classes("text-3xl")

                    with ui.column().classes("gap-3"):
                        ui.label(item["title"]).classes("text-base font-semibold text-slate-900 truncate")
                        with ui.row().classes("items-center justify-between gap-2"):
                            ui.label(item["date"]).classes("text-xs text-slate-500")
                            ui.label(item["badge"]).classes(
                                "bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded-full text-xs font-medium"
                            )
                        with ui.row().classes("items-center justify-between"):
                            ui.label(item["status"]).classes(
                                f"{status_class} px-2 py-0.5 rounded-full text-xs font-semibold"
                            )
                            ui.button(icon="more_horiz").props("flat round").classes(
                                "opacity-0 group-hover:opacity-100 transition text-slate-500 hover:text-slate-900"
                            )

    grid_view()
