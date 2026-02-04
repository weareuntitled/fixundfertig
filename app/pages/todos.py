from __future__ import annotations

from datetime import datetime

from nicegui import ui

from services.todos import (
    CreateTodoCommand,
    CreateTodoRequest,
    ListTodosQuery,
    TodoTitleEmptyError,
)
from styles import C_BTN_PRIM, C_CARD, C_INPUT, C_PAGE_TITLE


def _format_timestamp(value: datetime) -> str:
    return value.astimezone().strftime("%d.%m.%Y %H:%M")


def render_todos(session, company) -> None:  # noqa: ARG001
    ui.label("Todos").classes(C_PAGE_TITLE)

    command = CreateTodoCommand()
    query = ListTodosQuery()

    @ui.refreshable
    def todo_list() -> None:
        todos = query.execute()
        if not todos:
            ui.label("Noch keine Todos.").classes("text-sm text-slate-500")
            return
        with ui.column().classes("gap-2"):
            for todo in todos:
                with ui.row().classes("items-center justify-between gap-4"):
                    ui.label(todo.title).classes("text-sm text-slate-700")
                    ui.label(_format_timestamp(todo.created_at)).classes("text-xs text-slate-400")

    with ui.card().classes(f"{C_CARD} p-4 gap-3"):
        title_input = ui.input("Neues Todo").classes(C_INPUT)

        def handle_add() -> None:
            try:
                command.execute(CreateTodoRequest(title=title_input.value or ""))
            except TodoTitleEmptyError:
                ui.notify("Bitte einen Titel eingeben.", color="red")
                return
            title_input.value = ""
            todo_list.refresh()

        ui.button("Hinzufügen", on_click=handle_add).classes(C_BTN_PRIM)

    todo_list()
