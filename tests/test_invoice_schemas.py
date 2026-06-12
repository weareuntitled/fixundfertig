from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.invoice import (
    InvoiceDraft,
    InvoiceItem,
    InvoiceRead,
    InvoiceStatusUpdate,
)


def test_invoice_item_minimal_valid() -> None:
    item = InvoiceItem(description="Design", quantity=1, unit_price=100.0)
    assert item.description == "Design"
    assert item.quantity == 1
    assert item.unit_price == 100.0


def test_invoice_item_rejects_empty_description() -> None:
    with pytest.raises(ValidationError):
        InvoiceItem(description="", quantity=1, unit_price=100.0)


def test_invoice_item_rejects_zero_quantity() -> None:
    with pytest.raises(ValidationError):
        InvoiceItem(description="X", quantity=0, unit_price=100.0)


def test_invoice_item_rejects_negative_price() -> None:
    with pytest.raises(ValidationError):
        InvoiceItem(description="X", quantity=1, unit_price=-1.0)


def test_invoice_draft_minimal_valid() -> None:
    draft = InvoiceDraft(customer_id=1, items=[])
    assert draft.customer_id == 1
    assert draft.items == []
    assert draft.vat_rate == 19.0  # default


def test_invoice_draft_with_items() -> None:
    draft = InvoiceDraft(
        customer_id=1,
        date="2026-06-10",
        delivery_date="2026-06-10",
        items=[
            InvoiceItem(description="Design", quantity=2, unit_price=500.0),
            InvoiceItem(description="Druck", quantity=1, unit_price=50.0),
        ],
        vat_rate=7.0,
    )
    assert len(draft.items) == 2
    assert draft.vat_rate == 7.0


def test_invoice_draft_rejects_empty_customer_id() -> None:
    with pytest.raises(ValidationError):
        InvoiceDraft(customer_id=0, items=[])


def test_invoice_draft_rejects_invalid_vat_rate() -> None:
    with pytest.raises(ValidationError):
        InvoiceDraft(customer_id=1, items=[], vat_rate=-5)
    with pytest.raises(ValidationError):
        InvoiceDraft(customer_id=1, items=[], vat_rate=150)


def test_invoice_draft_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        InvoiceDraft(customer_id=1, items=[], evil="x")


def test_invoice_status_update_minimal() -> None:
    update = InvoiceStatusUpdate(status="OPEN")
    assert update.status == "OPEN"
    assert update.reason == ""


def test_invoice_status_update_with_reason() -> None:
    update = InvoiceStatusUpdate(status="CANCELLED", reason="Storno auf Kundenwunsch")
    assert update.reason == "Storno auf Kundenwunsch"


def test_invoice_status_update_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        InvoiceStatusUpdate(status="BOGUS")


def test_invoice_read_includes_id_and_status() -> None:
    inv = InvoiceRead(
        id=1,
        customer_id=1,
        nr="2026-001",
        title="Rechnung",
        date="2026-06-10",
        total_brutto=1190.0,
        status="OPEN",
        items=[InvoiceItem(description="X", quantity=1, unit_price=1000.0)],
    )
    assert inv.id == 1
    assert inv.nr == "2026-001"
    assert inv.status == "OPEN"


def test_invoice_read_to_draft_round_trip() -> None:
    """A Read response should be reusable as a draft for updates / re-finalization."""
    read = InvoiceRead(
        id=1,
        customer_id=1,
        date="2026-06-10",
        total_brutto=1190.0,
        status="DRAFT",
    )
    draft = InvoiceDraft(**read.model_dump(
        exclude={"id", "nr", "status", "total_brutto", "revision_nr", "updated_at", "related_invoice_id", "items"}
    ))
    assert draft.customer_id == 1
    assert draft.date == "2026-06-10"
