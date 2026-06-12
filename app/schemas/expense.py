# =========================
# APP/SCHEMAS/EXPENSE.PY
# =========================
"""
Pydantic v2 Schemas für Expense.

Source of Truth für `/api/expenses/*`-Endpoints.
Gespiegelt vom SQLModel `Expense` in `app/data.py:190-199`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExpenseCreate(BaseModel):
    """Input für POST /api/expenses."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    date: str = Field(min_length=10, max_length=20)
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    amount: float = Field(gt=0, le=10_000_000)

    @field_validator("date")
    @classmethod
    def _validate_iso_date(cls, v: str) -> str:
        from datetime import datetime
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError("Datum muss ISO-Format YYYY-MM-DD haben")
        return v


class ExpenseRead(BaseModel):
    """Output für GET /api/expenses (list) und POST /api/expenses (response)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    date: str
    category: str
    description: str = ""
    amount: float
    source: str = "MANUAL"


__all__ = ["ExpenseCreate", "ExpenseRead"]
