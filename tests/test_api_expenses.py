from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

importlib.import_module("app.api")

expenses_module = importlib.import_module("expenses")
dependencies_module = importlib.import_module("dependencies")
build_expenses_router = getattr(expenses_module, "router", None)


def _build_test_app() -> FastAPI:
    app = FastAPI()
    if build_expenses_router is not None:
        app.include_router(build_expenses_router)
    return app


def _db_session_override(mock_session):
    def override():
        yield mock_session
    return override


def _make_expense(expense_id: int = 1, company_id: int = 1, amount: float = 100.0):
    return SimpleNamespace(
        id=expense_id,
        company_id=company_id,
        date="2026-06-10",
        category="Sonstiges",
        description="Test-Ausgabe",
        amount=amount,
        source="MANUAL",
    )


@pytest.fixture
def expenses_app():
    app = _build_test_app()
    app.dependency_overrides[dependencies_module.require_session_auth] = lambda: 1
    return app, None


@pytest.mark.skipif(build_expenses_router is None, reason="app.api.expenses.router not yet implemented")
def test_list_expenses_returns_empty(expenses_app) -> None:
    """RED: GET /api/expenses with no expenses returns []."""
    app, _ = expenses_app
    session_mock = MagicMock()
    session_mock.exec.return_value.all.return_value = []
    comp = SimpleNamespace(id=1)
    app.dependency_overrides[dependencies_module.get_current_company] = lambda: comp
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/expenses")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.skipif(build_expenses_router is None, reason="app.api.expenses.router not yet implemented")
def test_list_expenses_returns_expenses(expenses_app) -> None:
    """RED: GET /api/expenses returns serialized list."""
    app, _ = expenses_app
    session_mock = MagicMock()
    session_mock.exec.return_value.all.return_value = [
        _make_expense(1, amount=50.0),
        _make_expense(2, amount=75.5),
    ]
    comp = SimpleNamespace(id=1)
    app.dependency_overrides[dependencies_module.get_current_company] = lambda: comp
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/expenses")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["amount"] == 50.0
    assert body[1]["category"] == "Sonstiges"


@pytest.mark.skipif(build_expenses_router is None, reason="app.api.expenses.router not yet implemented")
def test_create_expense_rejects_missing_required(expenses_app) -> None:
    """RED: POST /api/expenses without required fields returns 422."""
    app, _ = expenses_app
    session_mock = MagicMock()
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post("/api/expenses", json={})
    assert response.status_code == 422


@pytest.mark.skipif(build_expenses_router is None, reason="app.api.expenses.router not yet implemented")
def test_create_expense_rejects_zero_amount(expenses_app) -> None:
    """RED: POST with amount=0 returns 422 (Pydantic gt=0)."""
    app, _ = expenses_app
    session_mock = MagicMock()
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post(
        "/api/expenses",
        json={"date": "2026-06-10", "category": "Büro", "description": "Tinte", "amount": 0},
    )
    assert response.status_code == 422


@pytest.mark.skipif(build_expenses_router is None, reason="app.api.expenses.router not yet implemented")
def test_create_expense_succeeds(expenses_app) -> None:
    """RED: POST with valid payload returns 201 and the created expense."""
    app, _ = expenses_app

    def capture_add(obj):
        # SQLModel populates `id` on flush — simulate it
        obj.id = 42

    new_expense = _make_expense(42, amount=99.99)
    session_mock = MagicMock()
    session_mock.add.side_effect = capture_add
    session_mock.refresh.return_value = new_expense
    comp = SimpleNamespace(id=1)
    app.dependency_overrides[dependencies_module.get_current_company] = lambda: comp
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post(
        "/api/expenses",
        json={"date": "2026-06-10", "category": "Büro", "description": "Tinte", "amount": 99.99},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["amount"] == 99.99
    assert body["category"] == "Büro"


@pytest.mark.skipif(build_expenses_router is None, reason="app.api.expenses.router not yet implemented")
def test_delete_expense_returns_404_when_not_found(expenses_app) -> None:
    """RED: DELETE /api/expenses/{id} for missing id returns 404."""
    app, _ = expenses_app
    session_mock = MagicMock()
    session_mock.get.return_value = None
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).delete("/api/expenses/999")
    assert response.status_code == 404


@pytest.mark.skipif(build_expenses_router is None, reason="app.api.expenses.router not yet implemented")
def test_delete_expense_succeeds(expenses_app) -> None:
    """RED: DELETE existing expense returns 200 with status=deleted."""
    app, _ = expenses_app
    session_mock = MagicMock()
    session_mock.get.return_value = _make_expense(1)
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).delete("/api/expenses/1")
    assert response.status_code == 200
    assert response.json() == {"status": "deleted"}
