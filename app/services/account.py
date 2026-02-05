from __future__ import annotations

import logging
import os
from typing import Iterable

from sqlmodel import select

from data import (
    AuditLog,
    Company,
    Customer,
    Document,
    Expense,
    Invoice,
    InvoiceItem,
    InvoiceItemTemplate,
    InvoiceRevision,
    Token,
    User,
    get_session,
)
from services.auth import _hash_password, _verify_password_hash
from services.storage import delete_company_dirs

logger = logging.getLogger(__name__)


def _normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def _resolve_invoice_pdf_path(filename: str | None) -> str:
    if not filename:
        return ""
    if os.path.isabs(filename) or str(filename).startswith("storage/"):
        return filename
    return f"storage/invoices/{filename}"


def _cleanup_company_storage(company_id: int, invoice_paths: Iterable[str]) -> None:
    removed = 0
    for path in invoice_paths:
        if not path:
            continue
        try:
            if os.path.exists(path):
                os.remove(path)
                removed += 1
        except OSError:
            logger.warning(
                "delete_account.storage_cleanup_failed",
                extra={"company_id": company_id, "path": path},
            )
    logger.info(
        "delete_account.storage_cleanup_complete",
        extra={"company_id": company_id, "removed": removed},
    )


def update_user_profile(
    user_id: int,
    first_name: str,
    last_name: str,
    phone: str,
    email: str | None = None,
) -> User:
    with get_session() as session:
        user = session.get(User, int(user_id))
        if not user:
            raise ValueError("User not found")

        if email is not None:
            email_normalized = _normalize_email(email)
            if not email_normalized:
                raise ValueError("Email is required")
            existing = session.exec(
                select(User)
                .where(User.email == email_normalized)
                .where(User.id != user.id)
            ).first()
            if existing:
                raise ValueError("Email already in use")
            user.email = email_normalized

        user.first_name = (first_name or "").strip()
        user.last_name = (last_name or "").strip()
        user.phone = (phone or "").strip()
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def change_password(user_id: int, current_password: str, new_password: str) -> None:
    if not new_password:
        raise ValueError("New password is required")
    with get_session() as session:
        user = session.get(User, int(user_id))
        if not user:
            raise ValueError("User not found")
        if not _verify_password_hash(current_password or "", user.password_hash):
            raise ValueError("Current password is incorrect")
        user.password_hash = _hash_password(new_password)
        session.add(user)
        session.commit()


def delete_account(user_id: int) -> None:
    with get_session() as session:
        user = session.get(User, int(user_id))
        if not user:
            raise ValueError("User not found")

        other_user_exists = session.exec(
            select(User).where(User.id != user.id)
        ).first()
        companies = []
        if other_user_exists:
            logger.warning(
                "delete_account.multiple_users",
                extra={"user_id": user.id},
            )
        else:
            companies = session.exec(select(Company)).all()

        company_ids = [comp.id for comp in companies if comp.id is not None]
        customers = (
            session.exec(select(Customer).where(Customer.company_id.in_(company_ids))).all()
            if company_ids
            else []
        )
        customer_ids = [customer.id for customer in customers if customer.id is not None]
        invoices = (
            session.exec(select(Invoice).where(Invoice.customer_id.in_(customer_ids))).all()
            if customer_ids
            else []
        )
        invoice_ids = [inv.id for inv in invoices if inv.id is not None]
        invoice_items = (
            session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id.in_(invoice_ids))).all()
            if invoice_ids
            else []
        )
        invoice_revisions = (
            session.exec(select(InvoiceRevision).where(InvoiceRevision.invoice_id.in_(invoice_ids))).all()
            if invoice_ids
            else []
        )
        invoice_templates = (
            session.exec(
                select(InvoiceItemTemplate).where(
                    InvoiceItemTemplate.company_id.in_(company_ids)
                )
            ).all()
            if company_ids
            else []
        )
        expenses = (
            session.exec(select(Expense).where(Expense.company_id.in_(company_ids))).all()
            if company_ids
            else []
        )
        documents = (
            session.exec(select(Document).where(Document.company_id.in_(company_ids))).all()
            if company_ids
            else []
        )

        invoice_paths = [
            _resolve_invoice_pdf_path(inv.pdf_filename) for inv in invoices if inv.pdf_filename
        ]

        tokens = session.exec(select(Token).where(Token.user_id == user.id)).all()
        audit_logs = session.exec(select(AuditLog).where(AuditLog.user_id == user.id)).all()
        for log in audit_logs:
            log.user_id = None
            session.add(log)

        for item in invoice_items:
            session.delete(item)
        for revision in invoice_revisions:
            session.delete(revision)
        for inv in invoices:
            session.delete(inv)
        for customer in customers:
            session.delete(customer)
        for template in invoice_templates:
            session.delete(template)
        for expense in expenses:
            session.delete(expense)
        for document in documents:
            session.delete(document)
        for company in companies:
            session.delete(company)
        for token in tokens:
            session.delete(token)
        session.delete(user)

        try:
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error(
                "delete_account.failed",
                exc_info=exc,
                extra={"user_id": user.id},
            )
            raise

    for company_id in company_ids:
        _cleanup_company_storage(company_id, invoice_paths)
        try:
            delete_company_dirs(company_id)
        except Exception:
            pass
