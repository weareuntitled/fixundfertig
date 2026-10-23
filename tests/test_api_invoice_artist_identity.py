"""Artist identity through the invoice API, using real PDFs and an isolated DB."""
from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from test_invoice_pdf_buergerlicher_name import _extract_strings, _extract_text

importlib.import_module("app.api")
invoices = importlib.import_module("invoices")
dependencies = importlib.import_module("dependencies")
data = importlib.import_module("data")


@pytest.fixture
def artist_api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        company = data.Company(
            name="Daniel S.", first_name="Daniel", last_name="Beispiel",
            business_type="DJ / Producer", street="Musterstraße 1",
            postal_code="10115", city="Berlin", country="Deutschland",
            account_holder="Anderer Kontoinhaber", iban="DE89370400440532013000",
            tax_id="123/456/78901", is_small_business=True,
        )
        session.add(company)
        session.commit()
        customer = data.Customer(company_id=company.id, kdnr=1, name="Club Beispiel")
        session.add(customer)
        session.commit()
        app = FastAPI()
        app.include_router(invoices.router)
        app.dependency_overrides[dependencies.require_session_auth] = lambda: 1
        app.dependency_overrides[dependencies.get_current_company] = lambda: company

        def db_session():
            yield session

        app.dependency_overrides[dependencies.db_session] = db_session
        payload = {
            "customer_id": customer.id, "date": "2026-10-23",
            "recipient_name": "Club Beispiel", "vat_rate": 0,
            "items": [{"description": "DJ-Set Daniel S.", "quantity": 2, "unit_price": 150}],
        }
        with TestClient(app) as client:
            yield client, company, payload, session
    engine.dispose()


def test_preview_names_the_artist_and_legal_issuer(artist_api):
    client, company, payload, _ = artist_api
    response = client.post("/api/invoices/preview-pdf", json=payload)
    assert response.status_code == 200, response.text
    text = _extract_text(response.content)
    assert "DANIEL S. · DJ / Producer" in text
    assert "Rechnungsaussteller: Daniel Beispiel" in text
    assert "Musterstraße 1" in text
    assert "10115 Berlin" in text
    assert "Daniel S. ist der Künstlername von Daniel Beispiel." in text.replace("\n", " ")
    assert "DJ-Set Daniel S. (Daniel Beispiel)" in text
    assert "Rechnungsaussteller: Anderer Kontoinhaber" not in text
    assert "Kontoinhaber: Anderer Kontoinhaber" in text
    assert "danep" not in text.lower()
    assert company.next_invoice_nr == 10000
    assert client.get("/api/invoices").json() == []


@pytest.mark.parametrize("descriptions", [
    ["DJ-Set Daniel S."],
    ["Musikalische Begleitung"],
    ["DJ-Set Daniel S. (Daniel Beispiel)", "Technik"],
])
def test_new_invoice_download_matches_preview_identity(artist_api, descriptions):
    client, _, payload, _ = artist_api
    payload["items"] = [
        {"description": description, "quantity": 2, "unit_price": 150}
        for description in descriptions
    ]
    preview = client.post("/api/invoices/preview-pdf", json=payload)
    created = client.post("/api/invoices", json=payload)
    assert created.status_code == 201, created.text
    invoice = created.json()
    downloaded = client.get(f"/api/invoices/{invoice['id']}/download")
    assert downloaded.status_code == 200
    assert [item["description"] for item in invoice["items"]] == descriptions
    assert invoice["total_brutto"] == 300 * len(descriptions)
    for pdf in (preview.content, downloaded.content):
        text = " ".join(_extract_text(pdf).split())
        assert "DANIEL S. · DJ / Producer" in text
        assert text.count("Daniel S. ist der Künstlername von Daniel Beispiel.") == 1
        assert "Rechnungsaussteller: Daniel Beispiel" in text
        assert "(Daniel Beispiel) (Daniel Beispiel)" not in text
    assert client.get(f"/api/invoices/{invoice['id']}/preview-pdf").content == downloaded.content


@pytest.mark.parametrize("status", ["DRAFT", "SENT"])
def test_company_rebranding_keeps_existing_pdf_and_revision(artist_api, status):
    client, company, payload, session = artist_api
    company.name = "danep"
    payload["status"] = status
    created = client.post("/api/invoices", json=payload)
    assert created.status_code == 201, created.text
    invoice = created.json()
    url = f"/api/invoices/{invoice['id']}"
    before = client.get(f"{url}/download").content
    assert "DANEP" in _extract_text(before)
    company.name = "Daniel S."
    session.add(company)
    session.commit()
    assert client.get(f"{url}/download").content == before
    assert client.get(f"{url}/preview-pdf").content == before
    assert client.get(url).json() == invoice


def test_personal_wordmark_does_not_embed_a_previous_logo(artist_api, tmp_path, monkeypatch):
    import base64
    from services import storage

    client, company, payload, _ = artist_api
    monkeypatch.setattr(storage, "_COMPANY_ROOT", str(tmp_path))
    logo_dir = tmp_path / str(company.id)
    logo_dir.mkdir()
    (logo_dir / "logo.png").write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9s8AAAAASUVORK5CYII="
    ))
    pdf = client.post("/api/invoices/preview-pdf", json=payload).content
    assert "/Subtype /Image" not in pdf.decode("latin-1")
    assert "DANIEL S." in _extract_text(pdf)


def test_preview_uses_the_current_company_identity(artist_api):
    client, company, payload, _ = artist_api
    company.name = "Luna Live"
    company.first_name = "Lena"
    company.last_name = "Muster"
    text = " ".join(_extract_text(client.post("/api/invoices/preview-pdf", json=payload).content).split())
    assert "LUNA LIVE" in text
    assert "Rechnungsaussteller: Lena Muster" in text
    assert "Luna Live ist der Künstlername von Lena Muster." in text
    assert "Daniel Beispiel" not in text


def test_preview_wraps_long_issuer_and_bank_details(artist_api):
    client, company, payload, _ = artist_api
    company.first_name = "Daniel Alexander Maximilian"
    company.last_name = "Beispielmann-Sonnenfeld"
    company.account_holder = "Daniel Alexander Maximilian Beispielmann-Sonnenfeld"
    company.street = "An der außergewöhnlich langen Musterstraße 123 Hinterhaus"
    response = client.post("/api/invoices/preview-pdf", json=payload)
    assert response.status_code == 200
    lines = _extract_strings(response.content)
    text = " ".join(lines)
    assert "Rechnungsaussteller: Daniel Alexander Maximilian Beispielmann-Sonnenfeld" in text
    assert "Kontoinhaber: Daniel Alexander Maximilian Beispielmann-Sonnenfeld" in text
    assert "Kontoinhaber: Daniel Alexander Maximilian Beispielmann-Sonnenfeld" not in lines


def test_ordinary_company_is_not_relabelled_as_its_owners_artist_name(artist_api):
    client, company, payload, _ = artist_api
    company.name = "Muster GmbH"
    company.business_type = "GmbH"
    response = client.post("/api/invoices/preview-pdf", json=payload)
    text = _extract_text(response.content)
    assert "Muster GmbH" in text
    assert "ist der Künstlername" not in text
    assert "Rechnungsaussteller: Daniel Beispiel" not in text


def test_preview_breaks_a_long_unbroken_surname(artist_api):
    client, company, payload, _ = artist_api
    surname = "Beispielmann-Sonnenfeld-Langnamensfamilie-Musterhausen"
    company.last_name = surname
    company.account_holder = surname
    response = client.post("/api/invoices/preview-pdf", json=payload)
    lines = _extract_strings(response.content)
    assert surname in "".join(lines)
    assert not any(surname in line for line in lines)
