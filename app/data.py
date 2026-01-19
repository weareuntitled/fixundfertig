
from sqlalchemy import Column, Text, event, inspect
from sqlalchemy.orm import sessionmaker
from typing import Optional
from enum import Enum  # <--- WICHTIG: Das hat gefehlt!
from sqlmodel import Field, Session, SQLModel, create_engine, select, Relationship
from contextlib import contextmanager
from datetime import datetime
from pydantic import validator
import pandas as pd
import io
import os
from models.document import DocumentSource

# --- ENUMS ---

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
    # SQLModel relationships must use Relationship (not SQLAlchemy relationship/Mapped).
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user: Optional["User"] = Relationship(back_populates="tokens")

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
    n8n_secret: str = ""
    n8n_enabled: bool = False
    google_drive_folder_id: str = ""
    next_invoice_nr: int = 10000
    invoice_number_template: str = "{seq}"
    invoice_filename_template: str = "rechnung_{nr}"
    user: Optional["User"] = Relationship(back_populates="companies")

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

class Invoice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id")
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
    
    # File Info
    filename: str = ""
    original_filename: str = ""
    storage_key: str = ""
    storage_path: str = ""
    
    # Technical
    mime: str = ""
    mime_type: str = ""
    size: int = 0
    size_bytes: int = 0
    sha256: str = ""
    
    # Metadata
    source: str = "MANUAL"
    doc_type: str = ""
    document_type: str = ""
    
    # Extracted Content
    title: str = ""
    description: str = ""
    vendor: str = ""
    vendor_name: str = ""
    vendor_address_line1: str = ""
    vendor_postal_code: str = ""
    vendor_city: str = ""
    doc_date: Optional[str] = None
    invoice_date: Optional[str] = None
    amount_total: Optional[float] = None
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

# --- DATABASE SETUP ---
os.makedirs('./storage', exist_ok=True)
os.makedirs('./storage/invoices', exist_ok=True)

engine = create_engine("sqlite:///storage/database.db")
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

# Create Tables
SQLModel.metadata.create_all(engine)

@contextmanager
def get_session():
    with SessionLocal() as session:
        yield session

@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

@event.listens_for(Session, "before_flush")
def prevent_finalized_invoice_updates(session, flush_context, instances):
    for obj in session.dirty:
        if isinstance(obj, Invoice):
            state = inspect(obj)
            if not state.persistent:
                continue
            history = state.attrs.status.history
            old_status = history.deleted[0] if history.deleted else obj.status
            new_status = history.added[0] if history.added else obj.status
            if old_status == InvoiceStatus.FINALIZED and new_status not in (InvoiceStatus.CANCELLED, InvoiceStatus.OPEN, InvoiceStatus.SENT, InvoiceStatus.PAID):
                obj.status = InvoiceStatus.DRAFT

# --- SCHEMA MIGRATIONS (ENSURE COLUMNS EXIST) ---

def ensure_company_schema():
    with engine.begin() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(company)").fetchall()}
        if "user_id" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN user_id INTEGER")
        if "n8n_enabled" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN n8n_enabled INTEGER DEFAULT 0")
        if "n8n_secret" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN n8n_secret TEXT DEFAULT ''")
        if "n8n_webhook_url" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN n8n_webhook_url TEXT DEFAULT ''")
        if "business_type" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN business_type TEXT DEFAULT 'Einzelunternehmen'")
        if "is_small_business" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN is_small_business INTEGER DEFAULT 0")
        if "smtp_server" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN smtp_server TEXT DEFAULT ''")
        if "smtp_port" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN smtp_port INTEGER DEFAULT 587")
        if "smtp_user" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN smtp_user TEXT DEFAULT ''")
        if "smtp_password" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN smtp_password TEXT DEFAULT ''")
        if "default_sender_email" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN default_sender_email TEXT DEFAULT ''")
        if "google_drive_folder_id" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN google_drive_folder_id TEXT DEFAULT ''")
        if "invoice_number_template" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN invoice_number_template TEXT DEFAULT '{seq}'")
        if "invoice_filename_template" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN invoice_filename_template TEXT DEFAULT 'rechnung_{nr}'")
        if "first_name" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN first_name TEXT DEFAULT ''")
        if "last_name" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN last_name TEXT DEFAULT ''")
        if "street" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN street TEXT DEFAULT ''")
        if "postal_code" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN postal_code TEXT DEFAULT ''")
        if "city" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN city TEXT DEFAULT ''")
        if "country" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN country TEXT DEFAULT ''")
        if "email" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN email TEXT DEFAULT ''")
        if "phone" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN phone TEXT DEFAULT ''")
        if "tax_id" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN tax_id TEXT DEFAULT ''")
        if "vat_id" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN vat_id TEXT DEFAULT ''")
        if "bic" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN bic TEXT DEFAULT ''")
        if "bank_name" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN bank_name TEXT DEFAULT ''")
        if "iban" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN iban TEXT DEFAULT ''")
        if "next_invoice_nr" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN next_invoice_nr INTEGER DEFAULT 10000")

ensure_company_schema()

def ensure_customer_schema():
    with engine.begin() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(customer)").fetchall()}
        if "vat_id" not in columns: conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN vat_id TEXT DEFAULT ''")
        if "recipient_name" not in columns: conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN recipient_name TEXT DEFAULT ''")
        if "recipient_street" not in columns: conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN recipient_street TEXT DEFAULT ''")
        if "recipient_postal_code" not in columns: conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN recipient_postal_code TEXT DEFAULT ''")
        if "recipient_city" not in columns: conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN recipient_city TEXT DEFAULT ''")
        if "country" not in columns: conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN country TEXT DEFAULT ''")
        if "offen_eur" not in columns: conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN offen_eur REAL DEFAULT 0")
        if "archived" not in columns: conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN archived INTEGER DEFAULT 0")
        if "short_code" not in columns: conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN short_code TEXT DEFAULT ''")
        if "vorname" not in columns: conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN vorname TEXT DEFAULT ''")
        if "nachname" not in columns: conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN nachname TEXT DEFAULT ''")

ensure_customer_schema()

def ensure_invoice_schema():
    with engine.begin() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(invoice)").fetchall()}
        if "pdf_bytes" not in columns: conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN pdf_bytes BLOB")
        if "pdf_storage" not in columns: conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN pdf_storage TEXT DEFAULT ''")
        if "pdf_filename" not in columns: conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN pdf_filename TEXT DEFAULT ''")
        if "revision_nr" not in columns: conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN revision_nr INTEGER DEFAULT 0")
        if "updated_at" not in columns: 
            conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN updated_at TEXT DEFAULT ''")
            conn.exec_driver_sql("UPDATE invoice SET updated_at = datetime('now') WHERE updated_at IS NULL OR updated_at = ''")
        if "related_invoice_id" not in columns: conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN related_invoice_id INTEGER")
        if "delivery_date" not in columns: conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN delivery_date TEXT DEFAULT ''")
        if "recipient_name" not in columns: conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN recipient_name TEXT DEFAULT ''")
        if "recipient_street" not in columns: conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN recipient_street TEXT DEFAULT ''")
        if "recipient_postal_code" not in columns: conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN recipient_postal_code TEXT DEFAULT ''")
        if "recipient_city" not in columns: conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN recipient_city TEXT DEFAULT ''")

ensure_invoice_schema()

def ensure_invoice_revision_schema():
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS invoice_revision ("
            "invoice_id INTEGER NOT NULL,"
            "revision_nr INTEGER NOT NULL,"
            "changed_at TEXT DEFAULT (datetime('now')),"
            "reason TEXT DEFAULT '',"
            "snapshot_json TEXT DEFAULT '',"
            "pdf_filename_previous TEXT DEFAULT '',"
            "PRIMARY KEY (invoice_id, revision_nr)"
            ")"
        )
ensure_invoice_revision_schema()

def ensure_expense_schema():
    with engine.begin() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(expense)").fetchall()}
        if "source" not in columns: conn.exec_driver_sql("ALTER TABLE expense ADD COLUMN source TEXT DEFAULT ''")
        if "external_id" not in columns: conn.exec_driver_sql("ALTER TABLE expense ADD COLUMN external_id TEXT DEFAULT ''")
        if "webhook_url" not in columns: conn.exec_driver_sql("ALTER TABLE expense ADD COLUMN webhook_url TEXT DEFAULT ''")

ensure_expense_schema()

def ensure_audit_log_schema():
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS auditlog ("
            "id INTEGER PRIMARY KEY,"
            "timestamp TEXT,"
            "user_id INTEGER,"
            "action TEXT,"
            "invoice_id INTEGER,"
            "ip_address TEXT"
            ")"
        )
ensure_audit_log_schema()

def ensure_document_schema():
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS document ("
            "id INTEGER PRIMARY KEY,"
            "company_id INTEGER NOT NULL,"
            "filename TEXT DEFAULT '',"
            "storage_key TEXT DEFAULT '',"
            "created_at TEXT DEFAULT (datetime('now'))"
            ")"
        )
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(document)").fetchall()}
        
        for col in [
            "original_filename",
            "mime",
            "mime_type",
            "sha256",
            "source",
            "doc_type",
            "document_type",
            "storage_path",
            "title",
            "description",
            "vendor",
            "vendor_name",
            "vendor_address_line1",
            "vendor_postal_code",
            "vendor_city",
            "currency",
            "tax_treatment",
            "keywords_json",
        ]:
            if col not in columns:
                conn.exec_driver_sql(f"ALTER TABLE document ADD COLUMN {col} TEXT DEFAULT ''")
        
        if "size" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN size INTEGER DEFAULT 0")
        if "size_bytes" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN size_bytes INTEGER DEFAULT 0")
        if "amount_total" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN amount_total REAL")
        if "amount_net" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN amount_net REAL")
        if "amount_vat" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN amount_vat REAL")
        if "amount_gross" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN amount_gross REAL")
        if "doc_date" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN doc_date TEXT")
        if "invoice_date" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN invoice_date TEXT")
        if "net_amount" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN net_amount REAL")
        if "tax_amount" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN tax_amount REAL")
        if "gross_amount" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN gross_amount REAL")
        
        if "storage_key" in columns and "storage_path" in columns:
            conn.exec_driver_sql("UPDATE document SET storage_key = storage_path WHERE (storage_key IS NULL OR storage_key = '') AND storage_path IS NOT NULL AND storage_path != ''")

ensure_document_schema()

def log_audit_action(session, action, invoice_id=None, user_id=None, ip_address=""):
    entry = AuditLog(
        user_id=user_id,
        action=action,
        invoice_id=invoice_id,
        ip_address=ip_address or ""
    )
    session.add(entry)

def get_valid_token(session: Session, token_str: str, purpose: TokenPurpose) -> Optional[Token]:
    now = datetime.utcnow()
    statement = (
        select(Token)
        .where(Token.token == token_str)
        .where(Token.purpose == purpose)
        .where(Token.used_at.is_(None))
        .where(Token.expires_at > now)
    )
    return session.exec(statement).first()

# --- IMPORT LOGIC ---

def load_customer_import_dataframe(content, filename=""):
    file_name = str(filename or '').lower()
    if file_name.endswith('.csv'):
        try: return pd.read_csv(io.BytesIO(content)), ""
        except: return None, "Format Error"
    
    for engine in (None, 'openpyxl', 'xlrd'):
        try:
            return pd.read_excel(io.BytesIO(content), engine=engine), ""
        except: continue
    return None, "Format Error (Excel/CSV)"

def load_expense_import_dataframe(content, filename=""):
    return load_customer_import_dataframe(content, filename)

def load_invoice_import_dataframe(content, filename=""):
    return load_customer_import_dataframe(content, filename)

def parse_import_amount(value):
    try: return float(str(value or 0).replace('.','').replace(',','.'))
    except: return 0.0

def process_customer_import(content, session, comp_id, filename=""):
    df, err = load_customer_import_dataframe(content, filename)
    if err: return 0, err
    count = 0
    for _, row in df.iterrows():
        try:
            kdnr = row.get('Kundennummer') or row.get('Nr') or row.get('KdNr') or 0
            if not kdnr: continue
            
            exists = session.exec(select(Customer).where(Customer.kdnr == int(kdnr))).first()
            if not exists:
                c = Customer(
                    company_id=comp_id, 
                    kdnr=int(kdnr), 
                    name=str(row.get('Firmenname', '') or row.get('Firma', '')).replace('nan',''),
                    vorname=str(row.get('Vorname', '')).replace('nan',''),
                    nachname=str(row.get('Nachname', '')).replace('nan',''),
                    email=str(row.get('E-Mail', '') or row.get('Email', '')).replace('nan',''),
                    strasse=str(row.get('Strasse', '') or row.get('Straße', '') or row.get('1. Adresszeile', '')).replace('nan',''),
                    plz=str(row.get('PLZ', '') or row.get('Postleitzahl', '')).replace('nan',''),
                    ort=str(row.get('Ort', '') or row.get('Stadt', '')).replace('nan',''),
                    offen_eur=0.0
                )
                session.add(c)
                count += 1
        except: continue
    session.commit()
    return count, ""

def process_expense_import(content, session, comp_id, filename=""):
    df, err = load_expense_import_dataframe(content, filename)
    if err: return 0, err
    count = 0
    for _, row in df.iterrows():
        try:
            desc = f"{str(row.get('Lieferant', '') or row.get('Empfänger', '')).replace('nan','')} {str(row.get('Bemerkung', '') or row.get('Beschreibung', '')).replace('nan','')}".strip()
            exp = Expense(
                company_id=comp_id, 
                date=str(row.get('Datum', '')).replace('nan',''),
                category=str(row.get('Kategorie', 'Import')).replace('nan',''),
                description=desc, 
                amount=parse_import_amount(row.get('Betrag brutto', 0) or row.get('Betrag', 0)),
                source="IMPORT"
            )
            session.add(exp)
            count += 1
        except: continue
    session.commit()
    return count, ""

def process_invoice_import(content, session, comp_id, filename=""):
    df, err = load_invoice_import_dataframe(content, filename)
    if err: return 0, err
    count = 0
    for _, row in df.iterrows():
        try:
            nr = row.get('Rechnungsnummer') or row.get('Nr') or row.get('Rechnungs-Nr') or 0
            if not nr: continue
            
            kdnr = row.get('Kundennummer') or row.get('KdNr') or 0
            cust_id = 0
            if kdnr:
                cust = session.exec(select(Customer).where(Customer.kdnr == int(kdnr))).first()
                if cust: cust_id = cust.id
            
            inv = Invoice(
                company_id=comp_id,
                customer_id=cust_id,
                nr=str(nr),
                date=str(row.get('Datum', '') or row.get('Rechnungsdatum', '')).replace('nan',''),
                total_brutto=parse_import_amount(row.get('Betrag brutto', 0) or row.get('Gesamtbetrag', 0)),
                status=InvoiceStatus.OPEN
            )
            session.add(inv)
            count += 1
        except: continue
    session.commit()
    return count, ""
