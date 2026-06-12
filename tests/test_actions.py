"""TDD-Tests für app.actions.create_correction.

WICHTIG: Verwendet eine TEMP-DB statt der Live-DB (Regression-Fix:
Test-Pollution verschmutzte `storage/database.db` mit Test-Invoices).
"""
from __future__ import annotations

import importlib
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app"
if str(APP_PATH) not in __import__("sys").path:
    __import__("sys").path.append(str(APP_PATH))

data_module = importlib.import_module("data")
actions_module = importlib.import_module("actions")

create_correction = actions_module.create_correction
Company = data_module.Company
Customer = data_module.Customer
Invoice = data_module.Invoice
InvoiceItem = data_module.InvoiceItem
InvoiceStatus = data_module.InvoiceStatus


@pytest.fixture
def temp_db_engine(tmp_path):
    """Lenkt die `data` Engine auf eine temp-Datei um."""
    test_db_path = tmp_path / "test_actions.db"
    test_engine = create_engine(f"sqlite:///{test_db_path}")
    SQLModel.metadata.create_all(test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine, class_=Session, expire_on_commit=False)

    original_engine = data_module.engine
    original_session_local = data_module.SessionLocal
    original_get_session = data_module.get_session

    data_module.engine = test_engine
    data_module.SessionLocal = TestSessionLocal

    @contextmanager
    def _patched_get_session():
        s = TestSessionLocal()
        try:
            yield s
        finally:
            s.close()
    data_module.get_session = _patched_get_session

    try:
        yield test_engine
    finally:
        data_module.engine = original_engine
        data_module.SessionLocal = original_session_local
        data_module.get_session = original_get_session


def test_create_correction_creates_open_invoice(temp_db_engine) -> None:
    with data_module.get_session() as session:
        comp = Company(name="Corr GmbH", next_invoice_nr=200)
        session.add(comp)
        session.commit()
        session.refresh(comp)

        customer = Customer(
            company_id=int(comp.id),
            kdnr=1,
            name="Musterkunde",
            email="kunde@example.com",
        )
        session.add(customer)
        session.commit()
        session.refresh(customer)

        inv = Invoice(
            customer_id=int(customer.id),
            nr="200",
            date="2026-06-10",
            total_brutto=119.0,
            status=InvoiceStatus.OPEN,
        )
        session.add(inv)
        session.commit()
        session.refresh(inv)

        session.add(
            InvoiceItem(
                invoice_id=int(inv.id),
                description="Leistung",
                quantity=1,
                unit_price=119.0,
            )
        )
        session.commit()

        correction, err = create_correction(int(inv.id), use_negative_items=True)

        assert err == ""
        assert correction is not None

        with data_module.get_session() as verify:
            corr_db = verify.get(Invoice, int(correction.id))
            assert corr_db is not None
            assert corr_db.status == InvoiceStatus.OPEN
            assert corr_db.related_invoice_id == int(inv.id)
            assert corr_db.nr is not None
            assert corr_db.nr != ""
