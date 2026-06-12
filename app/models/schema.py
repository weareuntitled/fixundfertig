from sqlalchemy import Column, Text
from typing import Optional
from enum import Enum
from sqlmodel import Field, SQLModel, Relationship
from datetime import datetime
from pydantic import validator


class InvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    SENT = "SENT"
    PAID = "PAID"
    FINALIZED = "FINALIZED"
    CANCELLED = "CANCELLED"

class TokenPurpose(str, Enum):
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"
    READONLY_SHARE = "readonly_share"

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    username: Optional[str] = Field(default=None, index=True, unique=True)
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    password_hash: str
    is_active: bool = False
    is_email_verified: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tokens: list["Token"] = Relationship(back_populates="user")
    companies: list["Company"] = Relationship(back_populates="user")

    @validator("email", pre=True)
    def normalize_email(cls, value):
        if value is None:
            return value
        return value.strip().lower()

class Token(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    token: str = Field(index=True, unique=True)
    purpose: TokenPurpose
    expires_at: datetime
    used_at: Optional[datetime] = None
    single_use: bool = True
    scope_json: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user: Optional["User"] = Relationship(back_populates="tokens")

class InvitedEmail(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    invited_by_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    invited_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("email", pre=True)
    def normalize_email(cls, value):
        if value is None:
            return value
        return value.strip().lower()

class Company(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    name: str = "DanEP"
    first_name: str = ""
    last_name: str = ""
    business_type: str = "Einzelunternehmen"
    is_small_business: bool = False
    street: str = ""
    postal_code: str = ""
    city: str = ""
    country: str = ""
    email: str = ""
    phone: str = ""
    iban: str = ""
    bic: str = ""
    bank_name: str = ""
    tax_id: str = ""
    vat_id: str = ""
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    default_sender_email: str = ""
    n8n_webhook_url: str = ""
    n8n_webhook_url_test: str = ""
    n8n_webhook_url_prod: str = ""
    n8n_secret: str = ""
    n8n_enabled: bool = False
    google_drive_folder_id: str = ""
    next_invoice_nr: int = 10000
    invoice_number_template: str = "{seq}"
    invoice_filename_template: str = "rechnung_{nr}"
    user: Optional["User"] = Relationship(back_populates="companies")
    invoices: list["Invoice"] = Relationship(back_populates="company")
    customers: list["Customer"] = Relationship(back_populates="company")

class Customer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id")
    kdnr: int
    name: str
    vorname: str = ""
    nachname: str = ""
    email: str = ""
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
    short_code: str = ""

    @property
    def display_name(self):
        if self.name: return self.name
        return f"{self.vorname} {self.nachname}".strip()

    company: Optional["Company"] = Relationship(back_populates="customers")
    invoices: list["Invoice"] = Relationship(back_populates="customer")

class Invoice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id")
    company_id: int = Field(default=0, foreign_key="company.id")
    nr: Optional[str] = None
    title: str = "Rechnung"
    date: str
    delivery_date: str = ""
    recipient_name: str = ""
    recipient_street: str = ""
    recipient_postal_code: str = ""
    recipient_city: str = ""
    total_brutto: float
    status: InvoiceStatus = InvoiceStatus.DRAFT
    revision_nr: int = 0
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    related_invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    pdf_bytes: Optional[bytes] = Field(default=None)
    pdf_storage: str = ""
    pdf_filename: str = ""
    items: list["InvoiceItem"] = Relationship(
        back_populates="invoice",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    customer: Optional["Customer"] = Relationship(back_populates="invoices")
    company: Optional["Company"] = Relationship(back_populates="invoices")

class InvoiceRevision(SQLModel, table=True):
    invoice_id: int = Field(foreign_key="invoice.id", primary_key=True)
    revision_nr: int = Field(primary_key=True)
    changed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    reason: str = ""
    snapshot_json: str = ""
    pdf_filename_previous: str = ""

class InvoiceItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id")
    description: str
    quantity: float
    unit_price: float
    invoice: Optional["Invoice"] = Relationship(back_populates="items")

class InvoiceItemTemplate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id")
    title: str = ""
    description: str
    quantity: float = 1.0
    unit_price: float = 0.0

class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    user_id: Optional[int] = Field(default=None)
    action: str
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")
    ip_address: str = ""

class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id")
    date: str
    category: str
    description: str
    amount: float
    source: str = ""
    external_id: str = ""
    webhook_url: str = ""

class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id")
    filename: str = ""
    original_filename: str = ""
    storage_key: str = ""
    storage_path: str = ""
    mime: str = ""
    mime_type: str = ""
    size: int = 0
    size_bytes: int = 0
    sha256: str = ""
    source: str = "MANUAL"
    doc_type: str = ""
    document_type: str = ""
    title: str = ""
    description: str = ""
    vendor: str = ""
    doc_number: str = ""
    doc_date: Optional[str] = None
    invoice_date: Optional[str] = None
    amount_total: Optional[float] = None
    amount_net: Optional[float] = None
    amount_tax: Optional[float] = None
    net_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    gross_amount: Optional[float] = None
    currency: Optional[str] = None
    tax_treatment: str = ""
    keywords_json: str = "[]"
    created_at: datetime = Field(default_factory=datetime.utcnow)

class DocumentMeta(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    raw_payload_json: str = Field(default="{}", sa_column=Column(Text))
    line_items_json: str = Field(default="[]", sa_column=Column(Text))
    compliance_flags_json: str = Field(default="[]", sa_column=Column(Text))

class WebhookEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: str = Field(index=True, unique=True)
    source: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
