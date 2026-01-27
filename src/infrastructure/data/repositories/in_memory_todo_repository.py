from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from src.domain.repositories.todo_repository import TodoRepository


class InMemoryTodoRepository(TodoRepository):
    """Simple in-memory repository backed by a dict."""

    def __init__(self, initial_items: Optional[Iterable[Any]] = None) -> None:
        self._items: Dict[str, Any] = {}
        if initial_items:
            for item in initial_items:
                self.add(item)

    def add(self, todo: Any) -> Any:
        todo_id = self._extract_id(todo)
        self._items[todo_id] = todo
        return todo

    def get(self, todo_id: str) -> Optional[Any]:
        return self._items.get(todo_id)

    def list(self) -> Iterable[Any]:
        return list(self._items.values())

    def update(self, todo: Any) -> Any:
        todo_id = self._extract_id(todo)
        if todo_id not in self._items:
            raise KeyError(f"Todo with id '{todo_id}' not found")
        self._items[todo_id] = todo
        return todo

    def delete(self, todo_id: str) -> bool:
        if todo_id in self._items:
            del self._items[todo_id]
            return True
        return False

    @staticmethod
    def _extract_id(todo: Any) -> str:
        if hasattr(todo, "id"):
            return str(getattr(todo, "id"))
        if isinstance(todo, dict) and "id" in todo:
            return str(todo["id"])
        raise ValueError("Todo items must provide an 'id' attribute or key")
