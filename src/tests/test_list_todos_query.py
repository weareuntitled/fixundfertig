from __future__ import annotations

from application.contracts.todo_dtos import CreateTodoRequest
from application.todo.commands.create_todo import CreateTodoCommand
from application.todo.queries.list_todos import ListTodosQuery


def test_list_todos_query_returns_items(in_memory_todo_repo) -> None:
    creator = CreateTodoCommand()
    creator.execute(CreateTodoRequest(title="Erstes Todo"))
    creator.execute(CreateTodoRequest(title="Zweites Todo"))

    result = ListTodosQuery().execute()

    assert [item.id for item in result] == [1, 2]
    assert [item.title for item in result] == ["Erstes Todo", "Zweites Todo"]
