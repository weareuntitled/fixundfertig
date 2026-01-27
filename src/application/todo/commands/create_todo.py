from __future__ import annotations

from application.contracts.todo_dtos import CreateTodoRequest, TodoItemDto
from application.todo.errors import TodoTitleEmptyError
from application.todo.store import add_todo


class CreateTodoCommand:
    def execute(self, request: CreateTodoRequest) -> TodoItemDto:
        title = (request.title or "").strip()
        if not title:
            raise TodoTitleEmptyError("Todo title cannot be empty.")
        item = add_todo(title)
        return TodoItemDto(id=item.id, title=item.title, created_at=item.created_at)
