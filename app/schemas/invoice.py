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


InvoiceStatus = Literal["DRAFT", "OPEN", "SENT", "PAID", "FINALIZED", "CANCELLED", "ACCEPTED", "REJECTED"]
DocumentType = Literal["INVOICE", "QUOTE"]


class InvoiceItem(BaseModel):
    """Eine Rechnungsposition (description + quantity + unit_price)."""

    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    description: str = Field(min_length=1, max_length=500)
    quantity: float = Field(gt=0, le=100000)
    unit_price: float = Field(ge=0, le=1_000_000_000)


class PaymentInstallment(BaseModel):
    """Eine Rate des Zahlungsplans eines Angebots (Prozent vom Bruttobetrag + Anlass)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    percent: float = Field(gt=0, le=100)
    label: str = Field(default="", max_length=200)


class PaymentInstallmentRead(PaymentInstallment):
    """Rate mit ihrem Betrag, berechnet aus dem Bruttobetrag (nicht gespeichert)."""

    model_config = ConfigDict(extra="ignore")

    amount: float = 0.0


class InvoiceDraft(BaseModel):
    """Input für POST /api/invoices (create) und /api/invoices/preview-pdf.

    Enthält alle vom Client kontrollierten Felder. Server-managed Felder
    (id, nr, status, total_brutto, updated_at, pdf_*) sind nicht enthalten.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    customer_id: int = Field(gt=0)
    document_type: DocumentType = "INVOICE"
    title: str = Field(default="Rechnung", max_length=200)
    subject: str = Field(default="", max_length=200)
    date: str = Field(default="", max_length=20)
    delivery_date: str = Field(default="", max_length=20)
    service_from: str = Field(default="", max_length=20)
    service_to: str = Field(default="", max_length=20)
    valid_until: str = Field(default="", max_length=20)
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
    payment_plan: list[PaymentInstallment] = Field(default_factory=list)

    @field_validator("date", "delivery_date", "service_from", "service_to", "valid_until")
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


class InvoiceAttachmentRead(BaseModel):
    """Ein Beleg, der an eine Rechnung angehängt ist."""

    id: int
    document_id: int
    title: str = ""
    filename: str = ""
    mime: str = ""
    size: int = 0
    created_at: str = ""


class InvoiceAttachmentCreate(BaseModel):
    """Input für POST /api/invoices/{id}/attachments."""

    model_config = ConfigDict(extra="forbid")

    document_id: int = Field(gt=0)


class LinkedInvoiceRead(BaseModel):
    """Eine aus einem Angebot entstandene Rechnung (Liste am Angebot)."""

    id: int
    nr: str | None = None
    status: InvoiceStatus = "DRAFT"
    total_brutto: float = 0.0
    # Abschlagsrechnung (#490): Rate des Zahlungsplans, die damit abgerechnet wurde.
    installment_index: int | None = None
    is_down_payment: bool = False
    # Schlussrechnung (#491): eigener Marker, keine Abschlagsrechnung.
    is_final_invoice: bool = False


class FinalDeductionRead(BaseModel):
    """Eine von der Schlussrechnung abgezogene Abschlagsrechnung (#496)."""

    id: int
    nr: str = ""
    date: str = ""
    net: float = 0.0
    tax: float = 0.0
    total: float = 0.0


class FinalBreakdownRead(BaseModel):
    """Gesamtleistung, Abzüge und Restbetrag einer Schlussrechnung, wie im PDF (#496)."""

    net: float
    tax: float
    gross: float
    deductions: list[FinalDeductionRead] = Field(default_factory=list)
    rest_net: float
    rest_tax: float
    rest: float


class InvoiceRead(BaseModel):
    """Output für GET /api/invoices[/...]. Vollständiger Record inkl. server-managed Felder."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    document_type: DocumentType = "INVOICE"
    nr: str | None = None
    title: str = "Rechnung"
    subject: str = ""
    date: str = ""
    delivery_date: str = ""
    valid_until: str = ""
    recipient_name: str = ""
    recipient_street: str = ""
    recipient_postal_code: str = ""
    recipient_city: str = ""
    legacy: bool = False
    total_brutto: float
    status: InvoiceStatus = "DRAFT"
    revision_nr: int = 0
    updated_at: str = ""
    related_invoice_id: int | None = None
    quote_id: int | None = None
    quote_nr: str | None = None
    # Abschlagsrechnung (#490): Index der abgerechneten Rate, sonst None.
    down_payment_index: int | None = None
    # Schlussrechnung (#491): eigener Marker.
    is_final_invoice: bool = False
    # Schlussrechnung (#496): Aufschlüsselung für die Rechnungsseite, sonst None.
    final_breakdown: FinalBreakdownRead | None = None
    linked_invoices: list[LinkedInvoiceRead] = Field(default_factory=list)
    payment_link_url: str = ""
    payment_provider: str = ""
    items: list[InvoiceItem] = Field(default_factory=list)
    attachments: list[InvoiceAttachmentRead] = Field(default_factory=list)
    payment_plan: list[PaymentInstallmentRead] = Field(default_factory=list)


class InvoiceSendRequest(BaseModel):
    """Optional personal text and receipt selection for the email that carries the invoice."""

    message: str = Field(default="", max_length=2000)
    include_attachments: bool = False


class InvoiceStatusUpdate(BaseModel):
    """Input für PUT /api/invoices/{id}/status."""

    model_config = ConfigDict(extra="forbid")

    status: InvoiceStatus
    reason: str = Field(default="", max_length=500)


class InvoiceUpdate(BaseModel):
    """Input für PUT /api/invoices/{id} — Header-Felder aktualisieren."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, max_length=200)
    subject: str | None = Field(default=None, max_length=200)
    date: str | None = Field(default=None, max_length=20)
    delivery_date: str | None = Field(default=None, max_length=20)
    service_from: str | None = Field(default=None, max_length=20)
    service_to: str | None = Field(default=None, max_length=20)
    valid_until: str | None = Field(default=None, max_length=20)
    recipient_name: str | None = Field(default=None, max_length=200)
    recipient_street: str | None = Field(default=None, max_length=200)
    recipient_postal_code: str | None = Field(default=None, max_length=20)
    recipient_city: str | None = Field(default=None, max_length=100)
    intro_text: str | None = Field(default=None, max_length=2000)
    payment_plan: list[PaymentInstallment] | None = None
    reason: str = Field(default="", max_length=500)


class BulkStatusUpdate(BaseModel):
    """Input für POST /api/invoices/bulk-status."""

    model_config = ConfigDict(extra="forbid")

    invoice_ids: list[int] = Field(min_length=1)
    status: InvoiceStatus


class DownPaymentRequest(BaseModel):
    """Input für POST /api/invoices/{quote_id}/down-payment (#490)."""

    model_config = ConfigDict(extra="forbid")

    installment_index: int


__all__ = [
    "InvoiceItem",
    "InvoiceDraft",
    "InvoiceRead",
    "InvoiceStatusUpdate",
    "InvoiceUpdate",
    "BulkStatusUpdate",
    "DownPaymentRequest",
    "InvoiceStatus",
    "PaymentInstallment",
    "PaymentInstallmentRead",
]
