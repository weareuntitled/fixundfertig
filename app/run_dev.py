"""Dev launcher: sets local environment variables before starting the app.

FF_PORT moves the app off port 8000 (e.g. when something else holds it);
point the Vite proxy at it with VITE_BACKEND_URL.
"""
import os
import runpy

os.environ.setdefault("FF_ENV", "development")
os.environ.setdefault("FF_ALLOW_LOCALHOST", "1")
os.environ.setdefault("FF_ALLOW_BROWSER_INSPECT", "1")
os.environ.setdefault("FF_DEV_AUTO_LOGIN", "1")  # /api/auth/me signs in the first user
os.environ.setdefault("STORAGE_SECRET", "dev-only-secret-not-for-production-use-0123456789")

if os.getenv("FF_PORT"):
    from nicegui import ui

    _run = ui.run
    ui.run = lambda *args, **kwargs: _run(*args, **{**kwargs, "port": int(os.environ["FF_PORT"])})



def _seed_dev_data() -> None:
    """Empty dev database: one user, company, customer and invoice so the UI has something to show."""
    from sqlmodel import select

    from data import Company, Customer, Invoice, InvoiceItem, User, get_session
    from services.auth import _hash_password

    with get_session() as session:
        if session.exec(select(User)).first():
            return
        user = User(
            email="dev@example.com", username="dev", password_hash=_hash_password(os.urandom(12).hex()),
            is_active=True, is_email_verified=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        company = Company(user_id=user.id, name="Dev Company", street="Musterstraße 1", postal_code="10115", city="Berlin")
        session.add(company)
        session.commit()
        session.refresh(company)
        customer = Customer(company_id=company.id, kdnr=1, name="Beispiel Kunde", email="kunde@example.com")
        session.add(customer)
        session.commit()
        session.refresh(customer)
        invoice = Invoice(
            company_id=company.id, customer_id=customer.id, nr=10000, date="2026-10-26",
            recipient_name=customer.name, total_brutto=300.0, status="OPEN",
        )
        session.add(invoice)
        session.commit()
        session.refresh(invoice)
        session.add(InvoiceItem(invoice_id=invoice.id, description="DJ-Set", quantity=2, unit_price=150.0))
        session.commit()


if os.environ["FF_DEV_AUTO_LOGIN"] == "1":
    _seed_dev_data()

runpy.run_path("main.py", run_name="__main__")
