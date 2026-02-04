from __future__ import annotations

from nicegui import ui

from styles import C_CARD, C_PAGE_TITLE


def render_home() -> None:
    ui.label("Home").classes(C_PAGE_TITLE)

    with ui.card().classes(f"{C_CARD} p-4 w-full"):
        ui.label("Willkommen zurück!").classes("text-sm text-slate-700")
        ui.label("Deine Todos findest du jetzt im eigenen Bereich.").classes(
            "text-xs text-slate-500"
        )
