from dataclasses import dataclass

from src.domain.todo.exceptions.todo_exceptions import TodoTitleEmptyError


@dataclass(frozen=True)
class Todo:
    id: str
    title: str
    completed: bool = False

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise TodoTitleEmptyError("Todo title must not be empty.")
