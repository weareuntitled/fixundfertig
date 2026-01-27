from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from application.contracts.todo_dtos import CreateTodoRequest
from application.todo.queries.list_todos import ListTodosQuery
from composition_root import create_app_container
from presentation.controllers import todo_controller


def test_todo_flow_create_and_list() -> None:
    container = create_app_container()
    command = container.create_todo_command
    query = container.list_todos_query

    titles = ["Einkaufen", "Rechnung senden", "Follow-up"]
    created_items = [command.execute(CreateTodoRequest(title=title)) for title in titles]

    listed_items = query.execute()

    assert [item.title for item in listed_items] == titles
    assert [item.id for item in listed_items] == [item.id for item in created_items]
    assert [item.created_at for item in listed_items] == [
        item.created_at for item in created_items
    ]


def test_todo_flow_via_controller() -> None:
    create_app_container()

    todo_controller.create_todo("Onboarding abschließen")
    todo_controller.create_todo("Rechnung prüfen")

    listed_items = ListTodosQuery().execute()

    assert [item.title for item in listed_items] == [
        "Onboarding abschließen",
        "Rechnung prüfen",
    ]
    assert [todo["title"] for todo in todo_controller.list_todos()] == [
        "Onboarding abschließen",
        "Rechnung prüfen",
    ]
