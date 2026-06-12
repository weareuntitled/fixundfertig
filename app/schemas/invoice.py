# =========================
# APP/SCHEMAS/INVOICE.PY
# =========================
"""
Pydantic v2 Schemas für Invoice.

Source of Truth für `/api/invoices/*`-Endpoints.
Gespiegelt vom SQLModel `Invoice` und `InvoiceItem` in `app/data.py:139-170`.

Status-Enum: DRAFT, OPEN, SENT, PAID, FINALIZED, CANCELLED.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


InvoiceStatus = Literal["DRAFT", "OPEN", "SENT", "PAID", "FINALIZED", "CANCELLED"]


class InvoiceItem(BaseModel):
    """Eine Rechnungsposition (description + quantity + unit_price)."""

    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    description: str = Field(min_length=1, max_length=500)
    quantity: float = Field(gt=0, le=100000)
    unit_price: float = Field(ge=0, le=1_000_000_000)


class InvoiceDraft(BaseModel):
    """Input für POST /api/invoices (create) und /api/invoices/preview-pdf.

    Enthält alle vom Client kontrollierten Felder. Server-managed Felder
    (id, nr, status, total_brutto, updated_at, pdf_*) sind nicht enthalten.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    customer_id: int = Field(gt=0)
    title: str = Field(default="Rechnung", max_length=200)
    date: str = Field(default="", max_length=20)
    delivery_date: str = Field(default="", max_length=20)
    service_from: str = Field(default="", max_length=20)
    service_to: str = Field(default="", max_length=20)
    recipient_name: str = Field(default="", max_length=200)
    recipient_street: str = Field(default="", max_length=200)
    recipient_postal_code: str = Field(default="", max_length=20)
    recipient_city: str = Field(default="", max_length=100)
    vat_rate: float = Field(default=19.0, ge=0, le=100)
    ust_enabled: bool = Field(default=True)
    intro_text: str = Field(default="", max_length=2000)
    items: list[InvoiceItem] = Field(default_factory=list)
    notes: str = Field(default="", max_length=2000)
    status: InvoiceStatus = "OPEN"

    @field_validator("date", "delivery_date", "service_from", "service_to")
    @classmethod
    def _validate_iso_date(cls, v: str) -> str:
        if not v:
            return v
        from datetime import datetime
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError("Datum muss ISO-Format YYYY-MM-DD haben")
        return v


class InvoiceRead(BaseModel):
    """Output für GET /api/invoices[/...]. Vollständiger Record inkl. server-managed Felder."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    nr: str | None = None
    title: str = "Rechnung"
    date: str = ""
    delivery_date: str = ""
    recipient_name: str = ""
    recipient_street: str = ""
    recipient_postal_code: str = ""
    recipient_city: str = ""
    total_brutto: float
    status: InvoiceStatus = "DRAFT"
    revision_nr: int = 0
    updated_at: str = ""
    related_invoice_id: int | None = None
    items: list[InvoiceItem] = Field(default_factory=list)


class InvoiceStatusUpdate(BaseModel):
    """Input für PUT /api/invoices/{id}/status."""

    model_config = ConfigDict(extra="forbid")

    status: InvoiceStatus
    reason: str = Field(default="", max_length=500)


__all__ = [
    "InvoiceItem",
    "InvoiceDraft",
    "InvoiceRead",
    "InvoiceStatusUpdate",
    "InvoiceStatus",
]
