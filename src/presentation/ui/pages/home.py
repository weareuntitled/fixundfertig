from __future__ import annotations

from nicegui import ui

from styles import C_BTN_PRIM, C_CARD, C_INPUT, C_PAGE_TITLE
from src.presentation.controllers.todo_controller import create_todo, list_todos
from src.presentation.ui.viewmodels.todo_viewmodel import todos_to_viewmodels


def render_home() -> None:
    ui.label("Todo-Liste").classes(C_PAGE_TITLE)

    with ui.card().classes(f"{C_CARD} p-4 w-full"):
        title_input = ui.input("Titel", placeholder="Was steht an?").classes(C_INPUT)

        @ui.refreshable
        def todo_list() -> None:
            todos = todos_to_viewmodels(list_todos())
            if not todos:
                ui.label("Noch keine Todos.").classes("text-sm text-slate-500")
                return
            with ui.column().classes("w-full gap-2"):
                for todo in todos:
                    with ui.row().classes("w-full items-center justify-between border-b border-slate-100 py-2"):
                        ui.label(todo["title"]).classes("text-sm text-slate-700")

        def add_todo() -> None:
            title = (title_input.value or "").strip()
            if not title:
                ui.notify("Bitte gib einen Titel für das Todo ein.", color="orange")
                return
            create_todo(title)
            title_input.value = ""
            todo_list.refresh()

        with ui.row().classes("w-full gap-2 mt-2 items-center"):
            ui.button("Hinzufügen", on_click=add_todo).classes(C_BTN_PRIM)

        ui.separator().classes("my-3")
        todo_list()
