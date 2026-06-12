from __future__ import annotations

import importlib
import io
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


def _make_document(doc_id: int = 1, company_id: int = 1, filename: str = "test.pdf"):
    """Return a complete document-like object that `serialize_document` accepts.

    `serialize_document` accesses many fields — provide all defaults.
    """
    base = {
        "id": doc_id,
        "company_id": company_id,
        "filename": filename,
        "original_filename": filename,
        "mime": "application/pdf",
        "mime_type": "application/pdf",
        "size": 1024,
        "size_bytes": 1024,
        "sha256": "abc",
        "source": "MANUAL",
        "doc_type": "pdf",
        "document_type": "pdf",
        "title": "Test Doc",
        "description": "",
        "vendor": "",
        "doc_number": "",
        "doc_date": None,
        "invoice_date": None,
        "amount_total": None,
        "amount_net": None,
        "amount_tax": None,
        "currency": "",
        "keywords": "",
        "keywords_json": "[]",
        "storage_key": f"companies/{company_id}/documents/{doc_id}/{filename}",
        "storage_path": f"companies/{company_id}/documents/{doc_id}/{filename}",
        "created_at": "2026-06-10T10:00:00",
        "updated_at": "2026-06-10T10:00:00",
    }
    return SimpleNamespace(**base)


@pytest.fixture
def documents_app():
    app = _build_test_app()
    app.dependency_overrides[dependencies_module.require_session_auth] = lambda: 1
    return app, None


@pytest.mark.skipif(build_documents_router is None, reason="app.api.documents.router not yet implemented")
def test_upload_document_rejects_missing_file(documents_app) -> None:
    """RED: POST /api/documents/upload without file returns 422."""
    app, _ = documents_app
    session_mock = MagicMock()
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post("/api/documents/upload")
    assert response.status_code == 422


@pytest.mark.skipif(build_documents_router is None, reason="app.api.documents.router not yet implemented")
def test_upload_document_rejects_oversize(documents_app) -> None:
    """RED: POST with file > 15 MB returns 413."""
    app, _ = documents_app
    session_mock = MagicMock()
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    # 16 MB
    big = b"x" * (16 * 1024 * 1024)
    response = TestClient(app).post(
        "/api/documents/upload",
        files={"file": ("big.pdf", io.BytesIO(big), "application/pdf")},
    )
    assert response.status_code == 413


@pytest.mark.skipif(build_documents_router is None, reason="app.api.documents.router not yet implemented")
def test_upload_document_rejects_disallowed_extension(documents_app) -> None:
    """RED: POST with .exe returns 400."""
    app, _ = documents_app
    session_mock = MagicMock()
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post(
        "/api/documents/upload",
        files={"file": ("evil.exe", io.BytesIO(b"x"), "application/octet-stream")},
    )
    assert response.status_code == 400


@pytest.mark.skipif(build_documents_router is None, reason="app.api.documents.router not yet implemented")
def test_upload_document_succeeds(documents_app, monkeypatch) -> None:
    """RED: POST with valid PDF returns 201."""
    app, _ = documents_app

    # blob_storage is an external service — mock it to keep the test fast
    fake_storage = MagicMock()
    fake_storage.put_bytes.return_value = None
    monkeypatch.setattr(documents_module, "blob_storage", lambda: fake_storage)

    new_doc = _make_document(42, filename="uploaded.pdf")
    session_mock = MagicMock()
    session_mock.flush.return_value = None

    def capture_add(obj):
        obj.id = 42

    session_mock.add.side_effect = capture_add
    session_mock.refresh.return_value = new_doc
    comp = SimpleNamespace(id=1)
    app.dependency_overrides[dependencies_module.get_current_company] = lambda: comp
    app.dependency_overrides[dependencies_module.db_session] = _db_session_override(session_mock)
    response = TestClient(app).post(
        "/api/documents/upload",
        files={"file": ("uploaded.pdf", io.BytesIO(b"%PDF-1.4\nfake"), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body.get("original_filename") == "uploaded.pdf", f"body={body}"
    assert body["company_id"] == 1
    fake_storage.put_bytes.assert_called_once()
