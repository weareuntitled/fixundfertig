from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

importlib.import_module("app.api")

documents_module = importlib.import_module("documents")
dependencies_module = importlib.import_module("dependencies")
build_documents_router = getattr(documents_module, "router", None)


def _build_test_app() -> FastAPI:
    app = FastAPI()
    if build_documents_router is not None:
        app.include_router(build_documents_router)
    return app


def _db_session_override(mock_session):
    def override():
        yield mock_session
    return override


def _make_document(doc_id: int = 1, company_id: int = 1, filename: str = "test.pdf", mime: str = "application/pdf"):
    return SimpleNamespace(
        id=doc_id,
        company_id=company_id,
        filename=filename,
        original_filename=filename,
        storage_key=f"companies/{company_id}/documents/{doc_id}/{filename}",
        storage_path=None,  # Path resolution happens at request time; tests use blob key
        mime=mime,
        mime_type=mime,
        size=1024,
        size_bytes=1024,
        sha256="abc",
        source="MANUAL",
        doc_type="pdf",
        document_type="pdf",
        title="Test Doc",
        description="",
        vendor="",
        doc_number="",
        doc_date=None,
        invoice_date=None,
        amount_total=None,
        amount_net=None,
        amount_tax=None,
        currency="",
        keywords="",
        keywords_json="",
        created_at="2026-06-10T10:00:00",
        updated_at="2026-06-10T10:00:00",
    )


def _make_company(company_id: int = 1, user_id: int = 1):
    return SimpleNamespace(
        id=company_id,
        name="Test Co",
        user_id=user_id,
    )


@pytest.fixture
def documents_app():
    app = _build_test_app()
    app.dependency_overrides[dependencies_module.require_session_auth] = lambda: 1
    return app, None


@pytest.mark.skipif(build_documents_router is None, reason="app.api.documents.router not yet implemented")
def test_list_documents_returns_empty(documents_app) -> None:
    app, _ = documents_app
    session_mock = MagicMock()
    session_mock.exec.return_value.all.return_value = []
    comp = _make_company()
    app.dependency_overrides[dependencies_module.get_current_company] = lambda: comp
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/documents")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.skipif(build_documents_router is None, reason="app.api.documents.router not yet implemented")
def test_list_documents_filters_by_query(documents_app) -> None:
    app, _ = documents_app
    session_mock = MagicMock()
    # Return one matching + one non-matching document; backfill is a no-op
    documents_module.backfill_document_fields = lambda *a, **k: None
    documents_module.document_matches_filters = lambda doc, **kw: "match" in (doc.title or "").lower()
    session_mock.exec.return_value.all.return_value = [
        _make_document(1, filename="match.pdf", mime="application/pdf"),
        _make_document(2, filename="other.pdf", mime="application/pdf"),
    ]
    comp = _make_company()
    app.dependency_overrides[dependencies_module.get_current_company] = lambda: comp
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    # Patch the documents on each doc
    session_mock.exec.return_value.all.return_value[0].title = "match"
    session_mock.exec.return_value.all.return_value[1].title = "other"
    response = TestClient(app).get("/api/documents", params={"q": "match"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "match"


@pytest.mark.skipif(build_documents_router is None, reason="app.api.documents.router not yet implemented")
def test_get_document_file_returns_404_when_not_found(documents_app) -> None:
    app, _ = documents_app
    session_mock = MagicMock()
    session_mock.get.return_value = None
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/documents/999/file")
    assert response.status_code == 404


@pytest.mark.skipif(build_documents_router is None, reason="app.api.documents.router not yet implemented")
def test_get_document_file_returns_403_when_wrong_company(documents_app) -> None:
    app, _ = documents_app
    doc = _make_document(1, company_id=99)  # belongs to company 99
    wrong_comp = _make_company(99, user_id=999)  # current_user_id=1 doesn't match company.user_id=999
    session_mock = MagicMock()
    # session.get(Document, 1) → doc; session.get(Company, 99) → wrong_comp
    def get_side_effect(cls, id_):
        if cls.__name__ == "Document":
            return doc
        return wrong_comp
    session_mock.get.side_effect = get_side_effect
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).get("/api/documents/1/file")
    assert response.status_code == 403


@pytest.mark.skipif(build_documents_router is None, reason="app.api.documents.router not yet implemented")
def test_delete_document_returns_404_when_not_found(documents_app) -> None:
    app, _ = documents_app
    session_mock = MagicMock()
    session_mock.get.return_value = None
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).delete("/api/documents/999")
    assert response.status_code == 404


@pytest.mark.skipif(build_documents_router is None, reason="app.api.documents.router not yet implemented")
def test_delete_document_succeeds(documents_app) -> None:
    app, _ = documents_app
    doc = _make_document(1, company_id=1)
    comp = _make_company(1, user_id=1)
    session_mock = MagicMock()
    session_mock.get.side_effect = lambda cls, id_: doc if cls.__name__ == "Document" else comp
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).delete("/api/documents/1")
    assert response.status_code == 200
    assert response.json() == {"status": "deleted"}
