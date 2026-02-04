from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List


class TodoTitleEmptyError(ValueError):
    pass


@dataclass(frozen=True)
class Todo:
    title: str
    created_at: datetime


@dataclass(frozen=True)
class CreateTodoRequest:
    title: str


_TODOS: List[Todo] = []


def list_todos() -> List[Todo]:
    return list(_TODOS)


def create_todo(request: CreateTodoRequest) -> Todo:
    title = request.title.strip()
    if not title:
        raise TodoTitleEmptyError("title is required")
    todo = Todo(title=title, created_at=datetime.now(timezone.utc))
    _TODOS.append(todo)
    return todo


class CreateTodoCommand:
    def execute(self, request: CreateTodoRequest) -> Todo:
        return create_todo(request)


class ListTodosQuery:
    def execute(self) -> List[Todo]:
        return list_todos()
