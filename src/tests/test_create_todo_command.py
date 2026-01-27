from __future__ import annotations

import pytest

from application.contracts.todo_dtos import CreateTodoRequest
from application.todo.commands.create_todo import CreateTodoCommand
from application.todo.errors import TodoTitleEmptyError


def test_create_todo_command_rejects_empty_title(in_memory_todo_repo) -> None:
    command = CreateTodoCommand()

    with pytest.raises(TodoTitleEmptyError):
        command.execute(CreateTodoRequest(title="   "))
