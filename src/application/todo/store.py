from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count


@dataclass
class TodoItem:
    id: int
    title: str
    created_at: datetime


_TODO_ITEMS: list[TodoItem] = []
_NEXT_ID = count(1)


def add_todo(title: str) -> TodoItem:
    item = TodoItem(id=next(_NEXT_ID), title=title, created_at=datetime.now(timezone.utc))
    _TODO_ITEMS.append(item)
    return item


def list_todos() -> list[TodoItem]:
    return list(_TODO_ITEMS)


def reset_todos() -> None:
    _TODO_ITEMS.clear()
    global _NEXT_ID
    _NEXT_ID = count(1)
