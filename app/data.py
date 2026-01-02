from sqlmodel import Field, Session, SQLModel, create_engine, select, Relationship
from sqlalchemy import event, inspect
from typing import Optional, List
from enum import Enum
import pandas as pd
import io
import os

# --- DB MODELLE ---
class InvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"
    CANCELLED = "CANCELLED"

class Company(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = "DanEP"
    first_name: str = ""
    last_name: str = ""
    street: str = ""
    postal_code: str = ""
    city: str = ""
    email: str = ""
    phone: str = ""
    iban: str = ""
    tax_id: str = ""
    vat_id: str = ""
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    next_invoice_nr: int = 10000

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
    vat_id: str = ""
    recipient_name: str = ""
    recipient_street: str = ""
    recipient_postal_code: str = ""
    recipient_city: str = ""
    offen_eur: float = 0.0
    
    @property
    def display_name(self):
        if self.name: return self.name
        return f"{self.vorname} {self.nachname}".strip()

class Invoice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id")
    nr: Optional[int] = None 
    title: str = "Rechnung"
    date: str
    delivery_date: str = ""
    recipient_name: str = ""
    recipient_street: str = ""
    recipient_postal_code: str = ""
    recipient_city: str = ""
    total_brutto: float
    status: str = "Entwurf"
    related_invoice_id: Optional[int] = Field(default=None, foreign_key="invoice.id")

class InvoiceItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id")
    description: str
    quantity: float
    unit_price: float

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
SQLModel.metadata.create_all(engine)

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
            if old_status == InvoiceStatus.FINALIZED and new_status != InvoiceStatus.CANCELLED:
                raise ValueError("FINALIZED invoices are immutable.")

def ensure_company_schema():
    with engine.connect() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(company)").fetchall()}
        if "first_name" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN first_name TEXT DEFAULT ''")
        if "last_name" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN last_name TEXT DEFAULT ''")
        if "street" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN street TEXT DEFAULT ''")
        if "postal_code" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN postal_code TEXT DEFAULT ''")
        if "city" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN city TEXT DEFAULT ''")
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
        if "next_invoice_nr" not in columns:
            conn.exec_driver_sql("ALTER TABLE company ADD COLUMN next_invoice_nr INTEGER DEFAULT 10000")

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
        if "offen_eur" not in columns:
            conn.exec_driver_sql("ALTER TABLE customer ADD COLUMN offen_eur REAL DEFAULT 0")

ensure_customer_schema()

def ensure_invoice_schema():
    with engine.connect() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(invoice)").fetchall()}
        if "delivery_date" not in columns:
            conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN delivery_date TEXT DEFAULT ''")
        if "recipient_name" not in columns:
            conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN recipient_name TEXT DEFAULT ''")
        if "recipient_street" not in columns:
            conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN recipient_street TEXT DEFAULT ''")
        if "recipient_postal_code" not in columns:
            conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN recipient_postal_code TEXT DEFAULT ''")
        if "recipient_city" not in columns:
            conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN recipient_city TEXT DEFAULT ''")

ensure_invoice_schema()

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

def ensure_invoice_schema():
    with engine.connect() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(invoice)").fetchall()}
        if "related_invoice_id" not in columns:
            conn.exec_driver_sql("ALTER TABLE invoice ADD COLUMN related_invoice_id INTEGER")

ensure_invoice_schema()

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
            status = InvoiceStatus.FINALIZED
            if str(row.get('Storniert?', '')).strip().lower() in ['ja', 'true', '1']: status = InvoiceStatus.CANCELLED
            inv = Invoice(
                customer_id=cust.id,
                nr=int(nr),
                date=str(row.get('Datum', '')),
                total_brutto=parse_import_amount(row.get('Betrag brutto', 0)),
                status=status
            )
            session.add(inv)
            count += 1
        except: continue
    session.commit()
    return count, ""
