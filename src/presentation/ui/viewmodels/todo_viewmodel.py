from __future__ import annotations

from collections.abc import Iterable


def todo_to_viewmodel(todo: dict[str, int | str]) -> dict[str, int | str]:
    return {"id": todo["id"], "title": todo["title"]}


def todos_to_viewmodels(todos: Iterable[dict[str, int | str]]) -> list[dict[str, int | str]]:
    return [todo_to_viewmodel(todo) for todo in todos]
