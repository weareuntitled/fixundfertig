from __future__ import annotations

_TODOS: list[dict[str, int | str]] = []
_NEXT_ID = 1


def create_todo(title: str) -> dict[str, int | str]:
    global _NEXT_ID
    todo = {"id": _NEXT_ID, "title": title}
    _TODOS.append(todo)
    _NEXT_ID += 1
    return todo


def list_todos() -> list[dict[str, int | str]]:
    return list(_TODOS)
