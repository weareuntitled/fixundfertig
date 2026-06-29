from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session

from data import Company, Invoice

logger = logging.getLogger(__name__)


def _stripe() -> Any:
    """Lazy-import stripe so the module loads without it installed."""
    import stripe  # type: ignore[import-untyped]
    return stripe


def create_payment_link(
    invoice_id: int,
    company: Company,
    session: Session,
) -> str | None:
    """Create a Stripe Checkout Session for an invoice. Returns payment URL or None if not configured."""
    if not company.stripe_secret_key:
        logger.info("Stripe not configured for company %s", company.id)
        return None

    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        return None

    stripe = _stripe()
    stripe.api_key = company.stripe_secret_key

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {
                    "name": f"Rechnung {invoice.nr or invoice.id}",
                    "description": invoice.title,
                },
                "unit_amount": int(invoice.total_brutto * 100),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"https://app.fixundfertig.de/invoice/{invoice.id}?paid=1",
        cancel_url=f"https://app.fixundfertig.de/invoice/{invoice.id}",
        client_reference_id=str(invoice.id),
    )

    invoice.payment_link_url = checkout_session.url
    invoice.payment_provider = "stripe"
    session.add(invoice)
    session.commit()

    return checkout_session.url


def check_payment(
    invoice_id: int,
    company: Company,
    session: Session,
) -> bool:
    """Check Stripe for a completed payment on this invoice. Updates status to PAID if found."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice or not invoice.payment_link_url:
        return False

    if not company.stripe_secret_key:
        return False

    stripe = _stripe()
    stripe.api_key = company.stripe_secret_key

    sessions = stripe.checkout.Session.list(
        client_reference_id=str(invoice_id),
        limit=1,
    )

    if not sessions.data:
        return False

    checkout_session = sessions.data[0]

    if checkout_session.payment_status == "paid" or checkout_session.status == "complete":
        invoice.status = "PAID"
        invoice.revision_nr = int(invoice.revision_nr or 0) + 1
        session.add(invoice)
        session.commit()
        logger.info("Invoice %s marked PAID via Stripe check", invoice_id)
        return True

    return False
