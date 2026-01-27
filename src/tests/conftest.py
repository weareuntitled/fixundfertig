from __future__ import annotations

from itertools import count
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from application.todo import store
from infrastructure.data.repositories.in_memory_todo_repository import (
    InMemoryTodoRepository,
)


@pytest.fixture()
def in_memory_todo_repo(monkeypatch: pytest.MonkeyPatch) -> InMemoryTodoRepository:
    repo = InMemoryTodoRepository()
    monkeypatch.setattr(store, "_REPOSITORY", repo)
    monkeypatch.setattr(store, "_NEXT_ID", count(1))
    return repo
