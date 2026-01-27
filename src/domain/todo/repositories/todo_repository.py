from typing import Protocol

from src.domain.todo.entities.todo import Todo


class TodoRepository(Protocol):
    def add(self, todo: Todo) -> None:
        ...

    def list(self) -> list[Todo]:
        ...

    def get_by_id(self, todo_id: str) -> Todo | None:
        ...
