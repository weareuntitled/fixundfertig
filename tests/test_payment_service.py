from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "app"))

payment_module = importlib.import_module("services.payment")
create_payment_link = payment_module.create_payment_link
check_payment = payment_module.check_payment


# --- create_payment_link ---


def test_create_payment_link_requires_stripe_key(monkeypatch) -> None:
    company = MagicMock()
    company.stripe_secret_key = ""

    result = create_payment_link(invoice_id=1, company=company, session=MagicMock())
    assert result is None


def test_create_payment_link_returns_url(monkeypatch) -> None:
    fake_stripe_session = SimpleNamespace(url="https://checkout.stripe.com/pay/cs_test_abc123")

    def mock_stripe_create(**kw):
        return fake_stripe_session

    def mock_stripe():
        stripe = SimpleNamespace()
        stripe.checkout = SimpleNamespace()
        stripe.checkout.Session = SimpleNamespace()
        stripe.checkout.Session.create = mock_stripe_create
        return stripe

    monkeypatch.setattr(payment_module, "_stripe", mock_stripe)

    invoice = MagicMock()
    invoice.id = 1
    invoice.nr = "RE-1001"
    invoice.total_brutto = 250.0
    invoice.title = "Rechnung #1001"
    invoice.payment_link_url = ""
    invoice.payment_provider = ""
    company = MagicMock()
    company.id = 1
    company.stripe_secret_key = "sk_test_xxx"
    company.stripe_publishable_key = "pk_test_xxx"
    session_mock = MagicMock()
    session_mock.get.side_effect = lambda model, id: invoice

    url = create_payment_link(invoice_id=1, company=company, session=session_mock)

    assert url == "https://checkout.stripe.com/pay/cs_test_abc123"
    assert invoice.payment_link_url == url
    assert invoice.payment_provider == "stripe"


# --- check_payment ---


def test_check_payment_returns_false_when_no_link() -> None:
    invoice = MagicMock()
    invoice.payment_link_url = ""
    company = MagicMock()
    session_mock = MagicMock()
    session_mock.get.return_value = invoice

    result = check_payment(invoice_id=1, company=company, session=session_mock)
    assert result is False


def test_check_payment_updates_status_when_paid(monkeypatch) -> None:
    fake_completed_session = SimpleNamespace(
        payment_status="paid",
        status="complete",
    )

    def mock_stripe_list(**kw):
        return SimpleNamespace(data=[fake_completed_session])

    def mock_stripe():
        stripe = SimpleNamespace()
        stripe.checkout = SimpleNamespace()
        stripe.checkout.Session = SimpleNamespace()
        stripe.checkout.Session.list = mock_stripe_list
        return stripe

    monkeypatch.setattr(payment_module, "_stripe", mock_stripe)

    invoice = MagicMock()
    invoice.payment_link_url = "https://checkout.stripe.com/pay/cs_test_abc123"
    invoice.payment_provider = "stripe"
    invoice.status = "SENT"
    invoice.revision_nr = 0
    company = MagicMock()
    company.stripe_secret_key = "sk_test_xxx"
    session_mock = MagicMock()
    session_mock.get.return_value = invoice

    result = check_payment(invoice_id=1, company=company, session=session_mock)

    assert result is True
    assert invoice.status == "PAID"
    assert invoice.payment_provider == "stripe"


def test_check_payment_returns_false_when_unpaid(monkeypatch) -> None:
    fake_unpaid_session = SimpleNamespace(
        payment_status="unpaid",
        status="open",
    )

    def mock_stripe_list(**kw):
        return SimpleNamespace(data=[fake_unpaid_session])

    def mock_stripe():
        stripe = SimpleNamespace()
        stripe.checkout = SimpleNamespace()
        stripe.checkout.Session = SimpleNamespace()
        stripe.checkout.Session.list = mock_stripe_list
        return stripe

    monkeypatch.setattr(payment_module, "_stripe", mock_stripe)

    invoice = MagicMock()
    invoice.payment_link_url = "https://checkout.stripe.com/pay/cs_test_abc123"
    invoice.payment_provider = "stripe"
    invoice.status = "SENT"
    invoice.revision_nr = 0
    company = MagicMock()
    company.stripe_secret_key = "sk_test_xxx"
    session_mock = MagicMock()
    session_mock.get.return_value = invoice

    result = check_payment(invoice_id=1, company=company, session=session_mock)

    assert result is False
    assert invoice.status == "SENT"  # unchanged
