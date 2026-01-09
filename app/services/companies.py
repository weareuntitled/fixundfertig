from typing import Any

from sqlmodel import select

from data import (
    Company,
    Customer,
    Document,
    Expense,
    Invoice,
    InvoiceItem,
    InvoiceItemTemplate,
    InvoiceRevision,
    get_session,
)


ALLOWED_COMPANY_FIELDS = {
    "name",
    "first_name",
    "last_name",
    "business_type",
    "is_small_business",
    "street",
    "postal_code",
    "city",
    "country",
    "email",
    "phone",
    "iban",
    "bic",          
    "bank_name",    
    "tax_id",
    "vat_id",
    "smtp_server",
    "smtp_port",
    "smtp_user",
    "smtp_password",
    "default_sender_email",
    "n8n_webhook_url",
    "n8n_secret",
    "n8n_enabled",
    "google_drive_folder_id",
    "next_invoice_nr",
    "invoice_number_template",
    "invoice_filename_template",
}


def list_companies(user_id: int) -> list[Company]:
    with get_session() as session:
        return session.exec(select(Company).where(Company.user_id == user_id)).all()


def create_company(user_id: int, name: str, **kwargs: Any) -> Company:
    with get_session() as session:
        existing = session.exec(select(Company).where(Company.user_id == user_id)).all()
        if len(existing) >= 4:
            raise ValueError("Company limit reached for user.")

        filtered = {key: value for key, value in kwargs.items() if key in ALLOWED_COMPANY_FIELDS}
        company = Company(name=name, user_id=user_id, **filtered)
        session.add(company)
        session.commit()
        session.refresh(company)
        return company


def update_company(user_id: int, company_id: int, patch: dict[str, Any]) -> Company:
    with get_session() as session:
        company = session.exec(
            select(Company).where(
                Company.id == company_id,
                Company.user_id == user_id,
            )
        ).first()
        if not company:
            raise ValueError("Company not found for user.")

        for key, value in patch.items():
            if key in ALLOWED_COMPANY_FIELDS:
                setattr(company, key, value)

        session.add(company)
        session.commit()
        session.refresh(company)
        return company


def delete_company(user_id: int, company_id: int) -> None:
    with get_session() as session:
        company = session.exec(
            select(Company).where(
                Company.id == company_id,
                Company.user_id == user_id,
            )
        ).first()
        if not company:
            raise ValueError("Company not found for user.")

        customer_ids = session.exec(
            select(Customer.id).where(Customer.company_id == company_id)
        ).all()
        if customer_ids:
            invoices = session.exec(
                select(Invoice).where(Invoice.customer_id.in_(customer_ids))
            ).all()
            invoice_ids = [invoice.id for invoice in invoices if invoice.id is not None]

            if invoice_ids:
                for item in session.exec(
                    select(InvoiceItem).where(InvoiceItem.invoice_id.in_(invoice_ids))
                ).all():
                    session.delete(item)
                for revision in session.exec(
                    select(InvoiceRevision).where(InvoiceRevision.invoice_id.in_(invoice_ids))
                ).all():
                    session.delete(revision)
                for invoice in invoices:
                    session.delete(invoice)

        for customer in session.exec(
            select(Customer).where(Customer.company_id == company_id)
        ).all():
            session.delete(customer)

        for template in session.exec(
            select(InvoiceItemTemplate).where(InvoiceItemTemplate.company_id == company_id)
        ).all():
            session.delete(template)

        for expense in session.exec(
            select(Expense).where(Expense.company_id == company_id)
        ).all():
            session.delete(expense)

        for document in session.exec(
            select(Document).where(Document.company_id == company_id)
        ).all():
            session.delete(document)

        session.delete(company)
        session.commit()
