"""Run the FixundFertig NiceGUI app."""

from nicegui import ui


SIDEBAR_ITEMS = [
    ("Dashboard", "home"),
    ("Rechnungen", "description"),
    ("Dokumente", "folder"),
    ("Einstellungen", "settings"),
]


INVOICE_STATS = [
    ("Umsatz diesen Monat", "4.250 €"),
    ("Offene Forderungen", "1.200 €"),
    ("Entwürfe", "2"),
]


DOCUMENTS = [
    {
        "title": "Rechnung #1009",
        "status": "Bezahlt",
        "status_color": "bg-emerald-100 text-emerald-700",
        "icon": "receipt_long",
    },
    {
        "title": "Rechnung #1010",
        "status": "Offen",
        "status_color": "bg-amber-100 text-amber-700",
        "icon": "receipt_long",
    },
    {
        "title": "Projektvertrag",
        "status": "Bezahlt",
        "status_color": "bg-emerald-100 text-emerald-700",
        "icon": "description",
    },
    {
        "title": "Angebot April",
        "status": "Offen",
        "status_color": "bg-amber-100 text-amber-700",
        "icon": "request_quote",
    },
    {
        "title": "SLA Dokument",
        "status": "Bezahlt",
        "status_color": "bg-emerald-100 text-emerald-700",
        "icon": "folder",
    },
    {
        "title": "Rechnung #1011",
        "status": "Offen",
        "status_color": "bg-amber-100 text-amber-700",
        "icon": "receipt_long",
    },
    {
        "title": "Leistungsnachweis",
        "status": "Bezahlt",
        "status_color": "bg-emerald-100 text-emerald-700",
        "icon": "task_alt",
    },
    {
        "title": "Onboarding Guide",
        "status": "Offen",
        "status_color": "bg-amber-100 text-amber-700",
        "icon": "menu_book",
    },
]


ui.add_head_html(
    """
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #F8FAFC; }
    </style>
    """
)

with ui.row().classes("min-h-screen w-full bg-slate-50 text-slate-900"):
    with ui.column().classes(
        "w-[250px] shrink-0 bg-white border-r border-slate-200 px-4 py-6 gap-2"
    ):
        ui.label("FixUndFertig").classes("text-lg font-semibold tracking-tight mb-6")
        for label, icon in SIDEBAR_ITEMS:
            is_active = label == "Rechnungen"
            button_classes = "w-full justify-start rounded-md px-3 py-2"
            if is_active:
                button_classes += " bg-slate-100 font-medium"
            (
                ui.button(label, icon=icon, on_click=lambda: None, color=None)
                .props("flat")
                .classes(button_classes)
            )

    with ui.column().classes("flex-1 px-8 py-6 gap-6"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Dashboard").classes("text-2xl font-semibold")
            with ui.row().classes("items-center gap-3"):
                ui.input(placeholder="Suchen...").classes(
                    "w-64 rounded-full bg-white border border-slate-200 px-4 py-2"
                )
                (
                    ui.button(icon="notifications", color=None)
                    .props("flat")
                    .classes("rounded-full bg-white border border-slate-200")
                )

        with ui.row().classes("w-full gap-4"):
            for title, value in INVOICE_STATS:
                with ui.card().classes(
                    "flex-1 rounded-xl border border-slate-200 bg-white shadow-sm p-4"
                ):
                    ui.label(title).classes("text-sm text-slate-500")
                    ui.label(value).classes("text-2xl font-semibold")

        ui.label("Aktuelle Dateien").classes("text-lg font-semibold")
        with ui.grid(columns=4).classes("w-full gap-4"):
            for document in DOCUMENTS:
                with ui.card().classes(
                    "rounded-xl border border-slate-200 bg-white shadow-sm p-4 flex flex-col gap-4"
                ):
                    ui.icon(document["icon"]).classes(
                        "text-slate-400 bg-slate-100 rounded-md p-2 w-10 h-10"
                    )
                    with ui.row().classes("items-center justify-between"):
                        ui.label(document["title"]).classes("font-medium")
                        ui.badge(document["status"]).classes(
                            f"{document['status_color']} rounded-full px-2 py-0.5 text-xs"
                        )
                    with ui.row().classes("items-center justify-end"):
                        ui.button(icon="more_horiz", color=None).props("flat").classes(
                            "rounded-md"
                        )


def run() -> None:
    ui.run(
        title="FixundFertig",
        host="0.0.0.0",
        port=8000,
        language="de",
        favicon="🚀",
    )


if __name__ in {"__main__", "__mp_main__"}:
    run()
