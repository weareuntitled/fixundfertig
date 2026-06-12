from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.customer import (
    CustomerCreate,
    CustomerRead,
    CustomerUpdate,
)


def test_customer_create_minimal_valid() -> None:
    obj = CustomerCreate(name="Musterfirma")
    assert obj.name == "Musterfirma"
    assert obj.email == ""
    assert obj.country == ""
    assert obj.archived is False
    assert obj.short_code == ""


def test_customer_create_full_valid() -> None:
    obj = CustomerCreate(
        name="Musterfirma GmbH",
        vorname="Max",
        nachname="Mustermann",
        email="info@musterfirma.de",
        short_code="MF",
        strasse="Beispielweg 7",
        plz="10115",
        ort="Berlin",
        country="DE",
        recipient_name="Musterfirma Rechnungsstelle",
        recipient_street="Andere Str. 1",
        recipient_postal_code="20095",
        recipient_city="Hamburg",
    )
    assert obj.email == "info@musterfirma.de"
    assert obj.recipient_postal_code == "20095"
    assert obj.country == "DE"


def test_customer_create_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CustomerCreate(name="X", email="not-an-email")
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("email",) for e in errors)


def test_customer_create_allows_empty_email() -> None:
    obj = CustomerCreate(name="X", email="")
    assert obj.email == ""


def test_customer_create_name_max_length() -> None:
    with pytest.raises(ValidationError):
        CustomerCreate(name="x" * 201)


def test_customer_create_plz_too_long() -> None:
    with pytest.raises(ValidationError):
        CustomerCreate(name="X", plz="x" * 21)


def test_customer_create_archived_defaults_false() -> None:
    obj = CustomerCreate(name="X")
    assert obj.archived is False


def test_customer_create_does_not_accept_id_or_kdnr_or_offen_eur() -> None:
    """Server-managed fields must not be settable from the API."""
    with pytest.raises(ValidationError):
        CustomerCreate(name="X", id=42)
    with pytest.raises(ValidationError):
        CustomerCreate(name="X", kdnr=99)
    with pytest.raises(ValidationError):
        CustomerCreate(name="X", offen_eur=1234.5)


def test_customer_update_all_fields_optional() -> None:
    obj = CustomerUpdate()
    assert obj.model_dump(exclude_none=True) == {}


def test_customer_update_partial() -> None:
    obj = CustomerUpdate(email="new@example.com", archived=True)
    data = obj.model_dump(exclude_none=True)
    assert data == {"email": "new@example.com", "archived": True}


def test_customer_update_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        CustomerUpdate(email="bad")


def test_customer_read_includes_id_and_server_fields() -> None:
    obj = CustomerRead(
        id=42,
        company_id=7,
        kdnr=0,
        name="Musterfirma",
        email="x@y.de",
        offen_eur=123.45,
        archived=False,
    )
    assert obj.id == 42
    assert obj.kdnr == 0
    assert obj.offen_eur == 123.45


def test_customer_read_to_create_round_trip() -> None:
    """A Read response should be a valid input basis for an Update."""
    read = CustomerRead(
        id=1,
        company_id=1,
        kdnr=0,
        name="X",
        email="x@y.de",
        offen_eur=0.0,
        archived=False,
    )
    update = CustomerUpdate(**read.model_dump(exclude={"id", "company_id", "kdnr", "offen_eur"}))
    assert update.name == "X"
    assert update.email == "x@y.de"
