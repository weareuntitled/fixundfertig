from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CreateTodoRequest:
    title: str


@dataclass(frozen=True)
class TodoItemDto:
    id: int
    title: str
    created_at: datetime
