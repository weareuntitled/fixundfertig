from __future__ import annotations

from dataclasses import dataclass

from application.todo.commands.create_todo import CreateTodoCommand
from application.todo.queries.list_todos import ListTodosQuery
from application.todo.store import reset_todos


@dataclass(frozen=True)
class AppContainer:
    create_todo_command: CreateTodoCommand
    list_todos_query: ListTodosQuery


def create_app_container() -> AppContainer:
    reset_todos()
    return AppContainer(
        create_todo_command=CreateTodoCommand(),
        list_todos_query=ListTodosQuery(),
    )
