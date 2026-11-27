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


def _plan_not_over_100(plan: list[PaymentInstallment] | None) -> list[PaymentInstallment] | None:
    """Ein Zahlungsplan über 100 % fordert mehr als das Angebot (#495): nicht speicherbar."""
    if not plan:
        return plan
    total = round(sum(rate.percent for rate in plan), 2)
    if total > 100:
        text = f"{total:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        raise ValueError(f"Die Raten ergeben zusammen {text} %, mehr als 100 %. Bitte kürzen.")
    return plan


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

    _check_plan = field_validator("payment_plan")(_plan_not_over_100)

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


class BillingActionRead(BaseModel):
    """Eine Abrechnungsaktion eines Angebots: erlaubt, oder gesperrt mit Grund (#495).

    `invoice_id`/`invoice_nr` nennen die Rechnung, die die Aktion sperrt (für einen Link).
    """

    allowed: bool = True
    reason: str = ""
    invoice_id: int | None = None
    invoice_nr: str | None = None


class QuoteBillingRead(BaseModel):
    """Erlaubte Abrechnungsaktionen eines Angebots (`logic.quote_billing.quote_billing`)."""

    convert: BillingActionRead
    down_payment: BillingActionRead
    final_invoice: BillingActionRead
    # Das Angebot ist gesendet, nicht angenommen: Abrechnen nimmt es an, die Oberfläche fragt nach.
    requires_acceptance: bool = False


class QuoteSettlementRead(BaseModel):
    """Abrechnungsstand eines Angebots (#499): abgerechnet, gesamt, offen.

    `billed_brutto` ist die Summe der gestellten Rechnungen zum Angebot (brutto),
    `total_brutto` der Bruttobetrag des Angebots, `open_brutto` der Rest.
    """

    billed_brutto: float = 0.0
    total_brutto: float = 0.0
    open_brutto: float = 0.0
    billed_count: int = 0


class InvoiceRead(BaseModel):
    """Output für GET /api/invoices[/...]. Vollständiger Record inkl. server-managed Felder."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    document_type: DocumentType = "INVOICE"
    nr: str | None = None
    title: str = "Rechnung"
    subject: str = ""
    intro_text: str = ""
    date: str = ""
    delivery_date: str = ""
    valid_until: str = ""
    recipient_name: str = ""
    recipient_street: str = ""
    recipient_postal_code: str = ""
    recipient_city: str = ""
    legacy: bool = False
    total_brutto: float
    # Nettobetrag aus den Positionen und der Steuersatz des Dokuments (#499):
    # damit zeigt die Angebotsseite Netto, USt und Gesamt statt einer Summe.
    total_net: float = 0.0
    vat_rate: float = 0.0
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
    # Nur Angebote: welche Abrechnungsaktionen erlaubt sind; sonst None.
    billing: QuoteBillingRead | None = None
    # Nur Angebote: wie viel vom Angebot schon abgerechnet ist; sonst None.
    settlement: QuoteSettlementRead | None = None


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

    customer_id: int | None = Field(default=None, gt=0)
    vat_rate: float | None = Field(default=None, ge=0, le=100)
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

    _check_plan = field_validator("payment_plan")(_plan_not_over_100)


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
