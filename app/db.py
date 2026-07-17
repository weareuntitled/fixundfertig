from sqlalchemy import event, inspect
from sqlalchemy.orm import sessionmaker
from typing import Optional
from sqlmodel import Session, SQLModel, create_engine, select
from contextlib import contextmanager
from datetime import datetime
import pandas as pd
import io
import os

from env import load_env
from models.schema import (
    Invoice, InvoiceStatus, Customer, Expense,
    AuditLog, Token, TokenPurpose,
)

load_env()

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip() or "sqlite:///storage/database.db"

os.makedirs("./storage", exist_ok=True)
os.makedirs("./storage/invoices", exist_ok=True)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

SQLModel.metadata.create_all(engine)


def ensure_token_schema():
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS token ("
            "id INTEGER PRIMARY KEY,"
            "user_id INTEGER NOT NULL,"
            "token TEXT UNIQUE,"
            "purpose TEXT NOT NULL,"
            "expires_at TEXT NOT NULL,"
            "used_at TEXT,"
            "single_use BOOLEAN DEFAULT 1,"
            "scope_json TEXT DEFAULT '',"
            "created_at TEXT"
            ")"
        )
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(token)").fetchall()}
        if "single_use" not in columns:
            conn.exec_driver_sql("ALTER TABLE token ADD COLUMN single_use BOOLEAN DEFAULT 1")
        if "scope_json" not in columns:
            conn.exec_driver_sql("ALTER TABLE token ADD COLUMN scope_json TEXT DEFAULT ''")

ensure_token_schema()

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

def ensure_company_schema():
    with engine.begin() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(company)").fetchall()}
        if "user_id" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN user_id INTEGER")
        if "n8n_enabled" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN n8n_enabled INTEGER DEFAULT 0")
        if "n8n_secret" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN n8n_secret TEXT DEFAULT ''")
        if "n8n_webhook_url" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN n8n_webhook_url TEXT DEFAULT ''")
        if "n8n_webhook_url_test" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN n8n_webhook_url_test TEXT DEFAULT ''")
        if "n8n_webhook_url_prod" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN n8n_webhook_url_prod TEXT DEFAULT ''")
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
        if "payment_enabled" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN payment_enabled INTEGER DEFAULT 0")
        if "stripe_secret_key" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN stripe_secret_key TEXT DEFAULT ''")
        if "stripe_publishable_key" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN stripe_publishable_key TEXT DEFAULT ''")
        if "paypal_email" not in columns: conn.exec_driver_sql("ALTER TABLE company ADD COLUMN paypal_email TEXT DEFAULT ''")

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
        if "company_id" not in columns:
            conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN company_id INTEGER DEFAULT 0")
            conn.exec_driver_sql("""
                UPDATE invoice
                SET company_id = (SELECT company_id FROM customer WHERE customer.id = invoice.customer_id)
                WHERE company_id = 0 OR company_id IS NULL
            """)

def ensure_invoice_subject_field():
    with engine.begin() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(invoice)").fetchall()}
        if "subject" not in columns: conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN subject TEXT DEFAULT ''")

ensure_invoice_subject_field()

def ensure_invoice_legacy_field():
    with engine.begin() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(invoice)").fetchall()}
        if "legacy" not in columns: conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN legacy INTEGER DEFAULT 0")

ensure_invoice_legacy_field()

def ensure_invoice_payment_fields():
    with engine.begin() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(invoice)").fetchall()}
        if "payment_link_url" not in columns: conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN payment_link_url TEXT DEFAULT ''")
        if "payment_provider" not in columns: conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN payment_provider TEXT DEFAULT ''")

ensure_invoice_payment_fields()

def reconcile_invoice_revision_schema():
    with engine.begin() as conn:
        tables = {
            str(row[0])
            for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        has_modern = "invoicerevision" in tables
        has_legacy = "invoice_revision" in tables
        if not has_legacy:
            return
        if has_modern:
            legacy_count = conn.exec_driver_sql("SELECT COUNT(*) FROM invoice_revision").scalar() or 0
            if int(legacy_count) > 0:
                conn.exec_driver_sql(
                    "INSERT OR IGNORE INTO invoicerevision "
                    "(invoice_id, revision_nr, changed_at, reason, snapshot_json, pdf_filename_previous) "
                    "SELECT invoice_id, revision_nr, changed_at, reason, snapshot_json, pdf_filename_previous "
                    "FROM invoice_revision"
                )
            conn.exec_driver_sql("DROP TABLE invoice_revision")

reconcile_invoice_revision_schema()

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

def ensure_invited_email_schema():
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS invitedemail ("
            "id INTEGER PRIMARY KEY,"
            "email TEXT UNIQUE,"
            "invited_by_user_id INTEGER,"
            "invited_at TEXT DEFAULT (datetime('now'))"
            ")"
        )
ensure_invited_email_schema()

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
            "original_filename", "mime", "mime_type", "sha256", "source",
            "doc_type", "document_type", "storage_path", "title",
            "description", "vendor", "doc_number", "currency",
            "tax_treatment", "keywords_json",
        ]:
            if col not in columns:
                conn.exec_driver_sql(f"ALTER TABLE document ADD COLUMN {col} TEXT DEFAULT ''")
        if "size" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN size INTEGER DEFAULT 0")
        if "size_bytes" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN size_bytes INTEGER DEFAULT 0")
        if "amount_total" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN amount_total REAL")
        if "amount_net" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN amount_net REAL")
        if "amount_tax" not in columns: conn.exec_driver_sql("ALTER TABLE document ADD COLUMN amount_tax REAL")
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
