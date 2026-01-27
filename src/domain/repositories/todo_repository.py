from __future__ import annotations

from typing import Any, Iterable, Optional, Protocol, runtime_checkable


@runtime_checkable
class TodoRepository(Protocol):
    """Repository interface for Todo entities."""

    def add(self, todo: Any) -> Any:
        ...

    def get(self, todo_id: str) -> Optional[Any]:
        ...

    def list(self) -> Iterable[Any]:
        ...

    def update(self, todo: Any) -> Any:
        ...

    def delete(self, todo_id: str) -> bool:
        ...
