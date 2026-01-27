from __future__ import annotations

from application.contracts.todo_dtos import CreateTodoRequest
from application.todo.commands.create_todo import CreateTodoCommand
from application.todo.queries.list_todos import ListTodosQuery

_COMMAND = CreateTodoCommand()
_QUERY = ListTodosQuery()


def create_todo(title: str) -> dict[str, int | str]:
    todo = _COMMAND.execute(CreateTodoRequest(title=title))
    return {"id": todo.id, "title": todo.title}


def list_todos() -> list[dict[str, int | str]]:
    return [{"id": todo.id, "title": todo.title} for todo in _QUERY.execute()]
