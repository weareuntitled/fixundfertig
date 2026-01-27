from __future__ import annotations

from application.contracts.todo_dtos import TodoItemDto
from application.todo.store import list_todos


class ListTodosQuery:
    def execute(self) -> list[TodoItemDto]:
        return [
            TodoItemDto(id=item.id, title=item.title, created_at=item.created_at)
            for item in list_todos()
        ]
