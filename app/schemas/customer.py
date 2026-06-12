# =========================
# APP/SCHEMAS/CUSTOMER.PY
# =========================
"""
Pydantic v2 Schemas für Customer.

Source of Truth für die `/api/customers/*`-Endpoints.
Diese Schemas ersetzen den 14-kwargs-Smell in `pages/_shared.py:insert_customer()`
(siehe docs/audit_ux.md A2) — die API nimmt jetzt ein einzelnes `CustomerCreate`
statt vieler Keyword-Argumente.

Field-Konventionen (gespiegelt vom SQLModel in `app/data.py:113-137`):
- `id`, `kdnr`, `offen_eur`: server-managed, NICHT in Create/Update
- `name`, `vorname`, `nachname`: mindestens eines sollte gesetzt sein (per UI erzwungen)
- `email`: optional, EmailStr-Validierung wenn gesetzt
- `recipient_*`: optionaler Rechnungs-Override (siehe audit_ux.md U1)

Zod-Mirror (Client): `frontend/src/lib/schemas/customer.ts` (in M3 zu erstellen).
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_optional_email(value: str | None) -> str | None:
    """Accept empty string or a basic email shape. Reject other non-empty strings."""
    if value is None or value == "":
        return value if value is not None else ""
    if not _EMAIL_PATTERN.match(value):
        raise ValueError("Ungültiges E-Mail-Format")
    return value


class CustomerCreate(BaseModel):
    """Input für POST /api/customers. Alle Felder mit sinnvollen Defaults."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(default="", max_length=200)
    vorname: str = Field(default="", max_length=100)
    nachname: str = Field(default="", max_length=100)
    email: str = Field(default="")
    short_code: str = Field(default="", max_length=20)
    strasse: str = Field(default="", max_length=200)
    plz: str = Field(default="", max_length=20)
    ort: str = Field(default="", max_length=100)
    country: str = Field(default="", max_length=2)
    vat_id: str = Field(default="", max_length=30)
    recipient_name: str = Field(default="", max_length=200)
    recipient_street: str = Field(default="", max_length=200)
    recipient_postal_code: str = Field(default="", max_length=20)
    recipient_city: str = Field(default="", max_length=100)
    archived: bool = Field(default=False)

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        return _validate_optional_email(v) or ""


class CustomerUpdate(BaseModel):
    """Input für PUT/PATCH /api/customers/{id}. Alle Felder optional (Partial-Update)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, max_length=200)
    vorname: str | None = Field(default=None, max_length=100)
    nachname: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None)
    short_code: str | None = Field(default=None, max_length=20)
    strasse: str | None = Field(default=None, max_length=200)
    plz: str | None = Field(default=None, max_length=20)
    ort: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=2)
    vat_id: str | None = Field(default=None, max_length=30)
    recipient_name: str | None = Field(default=None, max_length=200)
    recipient_street: str | None = Field(default=None, max_length=200)
    recipient_postal_code: str | None = Field(default=None, max_length=20)
    recipient_city: str | None = Field(default=None, max_length=100)
    archived: bool | None = Field(default=None)

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str | None) -> str | None:
        return _validate_optional_email(v)


class CustomerRead(BaseModel):
    """Output für GET /api/customers[/...] — vollständiger Record inkl. server-managed Felder.

    Defaults sind gesetzt, damit `CustomerRead.model_validate(sqlmodel)` und
    partielle Konstruktion in Tests ohne alle 18 Felder funktionieren.
    Server liefert immer vollständige Records (alle Felder explizit gesetzt).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    kdnr: int = 0
    name: str = ""
    vorname: str = ""
    nachname: str = ""
    email: str = ""
    short_code: str = ""
    strasse: str = ""
    plz: str = ""
    ort: str = ""
    country: str = ""
    vat_id: str = ""
    recipient_name: str = ""
    recipient_street: str = ""
    recipient_postal_code: str = ""
    recipient_city: str = ""
    offen_eur: float = 0.0
    archived: bool = False


__all__ = ["CustomerCreate", "CustomerUpdate", "CustomerRead"]
