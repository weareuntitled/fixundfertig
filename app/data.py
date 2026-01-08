
from sqlalchemy import event, inspect
from typing import Optional, List
from enum import Enum  # <--- WICHTIG: Das hat gefehlt!
from sqlmodel import Field, Session, SQLModel, create_engine, select, Relationship
from contextlib import contextmanager
from datetime import datetime
import pandas as pd
import io
import os

# --- DB MODELLE ---
class InvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    SENT = "SENT"
    PAID = "PAID"
    FINALIZED = "FINALIZED"
    CANCELLED = "CANCELLED"

class Company(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
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

os.makedirs('./storage', exist_ok=True)
os.makedirs('./storage/invoices', exist_ok=True)
engine = create_engine("sqlite:///storage/database.db")
# TODO: Replace SQLModel.metadata.create_all with Alembic migrations when schema evolves.
# For now this guarantees new tables (e.g., future auth_* tables) exist in SQLite.
SQLModel.metadata.create_all(engine)

@contextmanager
def get_session():
    with Session(engine) as session:
        yield session

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

def ensure_company_schema():
    with engine.connect() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(company)").fetchall()}
        if "first_name" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN first_name TEXT DEFAULT ''")
        if "last_name" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN last_name TEXT DEFAULT ''")
        if "business_type" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN business_type TEXT DEFAULT 'Einzelunternehmen'")
        if "is_small_business" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN is_small_business INTEGER DEFAULT 0")
        conn.exec_driver_sql(
            "UPDATE company SET business_type = 'Einzelunternehmen' "
            "WHERE business_type IS NULL OR business_type = ''"
        )
        conn.exec_driver_sql(
            "UPDATE company SET is_small_business = 0 "
            "WHERE is_small_business IS NULL"
        )
        if "street" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN street TEXT DEFAULT ''")
        if "postal_code" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN postal_code TEXT DEFAULT ''")
        if "city" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN city TEXT DEFAULT ''")
        if "country" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN country TEXT DEFAULT ''")
        if "email" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN email TEXT DEFAULT ''")
        if "phone" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN phone TEXT DEFAULT ''")
        if "tax_id" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN tax_id TEXT DEFAULT ''")
        if "vat_id" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN vat_id TEXT DEFAULT ''")
        if "smtp_server" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN smtp_server TEXT DEFAULT ''")
        if "smtp_port" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN smtp_port INTEGER DEFAULT 587")
        if "smtp_user" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN smtp_user TEXT DEFAULT ''")
        if "smtp_password" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN smtp_password TEXT DEFAULT ''")
        if "default_sender_email" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN default_sender_email TEXT DEFAULT ''")
        if "n8n_webhook_url" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN n8n_webhook_url TEXT DEFAULT ''")
        if "n8n_secret" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN n8n_secret TEXT DEFAULT ''")
        if "n8n_enabled" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN n8n_enabled INTEGER DEFAULT 0")
        if "google_drive_folder_id" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN google_drive_folder_id TEXT DEFAULT ''")
        if "next_invoice_nr" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN next_invoice_nr INTEGER DEFAULT 10000")
        if "invoice_number_template" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN invoice_number_template TEXT DEFAULT '{seq}'")
        if "invoice_filename_template" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN invoice_filename_template TEXT DEFAULT 'rechnung_{nr}'")

ensure_company_schema()

def ensure_customer_schema():
    with engine.connect() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(customer)").fetchall()}
        if "vat_id" not in columns:
            conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN vat_id TEXT DEFAULT ''")
        if "recipient_name" not in columns:
            conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN recipient_name TEXT DEFAULT ''")
        if "recipient_street" not in columns:
            conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN recipient_street TEXT DEFAULT ''")
        if "recipient_postal_code" not in columns:
            conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN recipient_postal_code TEXT DEFAULT ''")
        if "recipient_city" not in columns:
            conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN recipient_city TEXT DEFAULT ''")
        if "country" not in columns:
            conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN country TEXT DEFAULT ''")
        if "offen_eur" not in columns:
            conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN offen_eur REAL DEFAULT 0")
        if "archived" not in columns:
            conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN archived INTEGER DEFAULT 0")
        if "short_code" not in columns:
            conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN short_code TEXT DEFAULT ''")

ensure_customer_schema()

def ensure_invoice_schema():
    with engine.connect() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(invoice)").fetchall()}
        if "pdf_bytes" not in columns:
            conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN pdf_bytes BLOB")
        if "pdf_storage" not in columns:
            conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN pdf_storage TEXT DEFAULT ''")
        if "pdf_filename" not in columns:
            conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN pdf_filename TEXT DEFAULT ''")
        if "revision_nr" not in columns:
            conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN revision_nr INTEGER DEFAULT 0")
        if "updated_at" not in columns:
            conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN updated_at TEXT DEFAULT ''")
            conn.exec_driver_sql("UPDATE invoice SET updated_at = datetime('now') WHERE updated_at IS NULL OR updated_at = ''")
        if "related_invoice_id" not in columns:
            conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN related_invoice_id INTEGER")
        old_status_count = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM invoice WHERE status IN ('Entwurf','Bezahlt','Offen','FINALIZED')"
        ).fetchone()[0]
        if old_status_count > 0:
            conn.exec_driver_sql("UPDATE invoice SET status = 'DRAFT' WHERE status = 'Entwurf'")
            conn.exec_driver_sql("UPDATE invoice SET status = 'PAID' WHERE status = 'Bezahlt'")
            conn.exec_driver_sql("UPDATE invoice SET status = 'OPEN' WHERE status = 'Offen'")
            conn.exec_driver_sql("UPDATE invoice SET status = 'OPEN' WHERE status = 'FINALIZED'")

ensure_invoice_schema()

def ensure_invoice_revision_schema():
    with engine.connect() as conn:
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
    with engine.connect() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(expense)").fetchall()}
        if "source" not in columns:
            conn.exec_driver_sql("ALTER TABLE expense ADD COLUMN source TEXT DEFAULT ''")
        if "external_id" not in columns:
            conn.exec_driver_sql("ALTER TABLE expense ADD COLUMN external_id TEXT DEFAULT ''")
        if "webhook_url" not in columns:
            conn.exec_driver_sql("ALTER TABLE expense ADD COLUMN webhook_url TEXT DEFAULT ''")

ensure_expense_schema()

def ensure_audit_log_schema():
    with engine.connect() as conn:
        conn.exec_driver_sql(
            "CREATE TRIGGER IF NOT EXISTS auditlog_no_update "
            "BEFORE UPDATE ON auditlog "
            "BEGIN SELECT RAISE(ABORT, 'Audit log is append-only'); END;"
        )
        conn.exec_driver_sql(
            "CREATE TRIGGER IF NOT EXISTS auditlog_no_delete "
            "BEFORE DELETE ON auditlog "
            "BEGIN SELECT RAISE(ABORT, 'Audit log is append-only'); END;"
        )

ensure_audit_log_schema()

def log_audit_action(session, action, invoice_id=None, user_id=None, ip_address=""):
    entry = AuditLog(
        user_id=user_id,
        action=action,
        invoice_id=invoice_id,
        ip_address=ip_address or ""
    )
    session.add(entry)

# --- IMPORT LOGIC ---
def load_customer_import_dataframe(content, filename=""):
    file_name = str(filename or '').lower()
    if file_name.endswith('.csv'):
        file_type = 'csv'
    elif file_name.endswith('.xls') or file_name.endswith('.xlsx'):
        file_type = 'excel'
    elif content[:4] == b'PK\x03\x04' or content[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        file_type = 'excel'
    else:
        file_type = 'csv'

    if file_type == 'csv':
        try: return pd.read_csv(io.BytesIO(content)), ""
        except: return None, "Format Error"

    missing_engine = False
    for engine in (None, 'openpyxl', 'xlrd'):
        try:
            if engine:
                return pd.read_excel(io.BytesIO(content), engine=engine), ""
            return pd.read_excel(io.BytesIO(content)), ""
        except ImportError:
            missing_engine = True
            continue
        except:
            continue
    if missing_engine: return None, "Excel-Import benötigt openpyxl oder xlrd."
    return None, "Format Error"

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
            kdnr = row.get('Kundennummer') or row.get('Nr') or 0
            if not kdnr: continue
            firma = str(row.get('Firmenname', ''))
            if str(firma) == 'nan': firma = ""
            
            exists = session.exec(select(Customer).where(Customer.kdnr == int(kdnr))).first()
            if not exists:
                c = Customer(
                    company_id=comp_id, kdnr=int(kdnr), 
                    name=firma,
                    vorname=str(row.get('Vorname', '')).replace('nan',''),
                    nachname=str(row.get('Nachname', '')).replace('nan',''),
                    email=str(row.get('E-Mail', '')).replace('nan',''),
                    strasse=str(row.get('1. Adresszeile', '')).replace('nan',''),
                    plz=str(row.get('Postleitzahl', '')).replace('nan',''),
                    ort=str(row.get('Ort', '')).replace('nan',''),
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
            desc = f"{row.get('Lieferant', '')} {row.get('Bemerkung', '')}".replace('nan','').strip()
            exp = Expense(
                company_id=comp_id, date=str(row.get('Datum', '')),
                category=str(row.get('Kategorie', 'Import')),
                description=desc, 
                amount=parse_import_amount(row.get('Betrag brutto', 0))
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
            kdnr = row.get('Kundennummer') or 0
            cust = None
            if kdnr:
                cust = session.exec(select(Customer).where(Customer.kdnr == int(kdnr))).first()
            if not cust: continue
            status = InvoiceStatus.OPEN
            is_storniert = str(row.get('Storniert?', '')).strip().lower() in ['ja', 'true', '1']
            if is_storniert: status = InvoiceStatus.CANCELLED
            if str(row.get('Zahldatum', '')).strip(): status = InvoiceStatus.PAID
            inv = Invoice(
                customer_id=cust.id,
                nr=str(nr),
                date=str(row.get('Datum', '')),
                total_brutto=parse_import_amount(row.get('Betrag brutto', 0)),
                status=status
            )
            session.add(inv)
            session.flush()
            if is_storniert:
                log_audit_action(session, "INVOICE_CANCELLED", invoice_id=inv.id)
            count += 1
        except: continue
    session.commit()
    return count, ""
