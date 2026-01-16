from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.orm import sessionmaker

APP_PATH = Path(__file__).resolve().parents[1] / "app"
if str(APP_PATH) not in sys.path:
    sys.path.append(str(APP_PATH))

from services import storage as storage_service
from services.documents_ingest import save_upload_bytes


def _load_app_modules():
    import importlib

    data_module = importlib.import_module("data")
    main_module = importlib.import_module("main")
    documents_module = importlib.import_module("services.documents")
    return data_module, main_module, documents_module


def _reset_storage_root(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    storage_service._STORAGE_ROOT = str(storage_root)
    storage_service._COMPANY_ROOT = str(storage_root / "companies")


def _reset_session(data_module, tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    SQLModel.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    data_module.engine = engine
    data_module.SessionLocal = SessionLocal


def test_save_upload_bytes_writes_file(tmp_path: Path) -> None:
    payload = b"ingest-test-bytes"
    destination = tmp_path / "uploads" / "file.bin"
    sha, size = save_upload_bytes(destination, payload)

    assert sha == hashlib.sha256(payload).hexdigest()
    assert size == len(payload)
    assert destination.exists()
    assert destination.read_bytes() == payload


def test_webhook_auth_failure_returns_401_403(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _reset_storage_root(tmp_path)
    data_module, main_module, _documents_module = _load_app_modules()
    _reset_session(data_module, tmp_path)

    client = TestClient(main_module.app)

    payload = {
        "event_id": "evt-missing-signature",
        "company_id": 1,
        "file_base64": base64.b64encode(b"demo").decode("utf-8"),
    }
    resp = client.post("/api/webhooks/n8n/ingest", json=payload)
    assert resp.status_code == 401

    with data_module.get_session() as session:
        company = data_module.Company(name="Test Co", n8n_enabled=False, n8n_secret="secret")
        session.add(company)
        session.commit()
        session.refresh(company)

    payload["company_id"] = int(company.id or 0)
    raw_body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = hmac.new(b"secret", f"{timestamp}.".encode("utf-8") + raw_body, hashlib.sha256).hexdigest()
    headers = {"Content-Type": "application/json", "X-Timestamp": timestamp, "X-Signature": signature}
    resp = client.post("/api/webhooks/n8n/ingest", content=raw_body, headers=headers)
    assert resp.status_code == 403


def test_webhook_success_stores_file_and_meta(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _reset_storage_root(tmp_path)
    data_module, main_module, documents_module = _load_app_modules()
    _reset_session(data_module, tmp_path)

    with data_module.get_session() as session:
        company = data_module.Company(name="Webhook Co", n8n_enabled=True, n8n_secret="secret")
        session.add(company)
        session.commit()
        session.refresh(company)

    file_bytes = b"webhook-bytes"
    payload = {
        "event_id": "evt-success",
        "company_id": int(company.id or 0),
        "file_name": "doc.txt",
        "file_base64": base64.b64encode(file_bytes).decode("utf-8"),
        "extracted": {"vendor": "ACME"},
    }
    raw_body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = hmac.new(b"secret", f"{timestamp}.".encode("utf-8") + raw_body, hashlib.sha256).hexdigest()
    headers = {"Content-Type": "application/json", "X-Timestamp": timestamp, "X-Signature": signature}

    client = TestClient(main_module.app)
    resp = client.post("/api/webhooks/n8n/ingest", content=raw_body, headers=headers)
    assert resp.status_code == 200

    with data_module.get_session() as session:
        document = session.exec(select(data_module.Document)).first()
        meta = session.exec(select(data_module.DocumentMeta)).first()

    assert document is not None
    assert meta is not None
    assert meta.document_id == int(document.id or 0)

    storage_path = documents_module.resolve_document_path(document.storage_path)
    assert storage_path
    assert Path(storage_path).exists()
    assert Path(storage_path).read_bytes() == file_bytes


def test_manual_upload_sets_storage_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _reset_storage_root(tmp_path)
    data_module, main_module, _documents_module = _load_app_modules()
    _reset_session(data_module, tmp_path)

    with data_module.get_session() as session:
        user = data_module.User(email="user@example.com", password_hash="hashed")
        session.add(user)
        session.commit()
        session.refresh(user)
        company = data_module.Company(user_id=int(user.id or 0), name="Manual Co")
        session.add(company)
        session.commit()
        session.refresh(company)

    main_module.app.storage.user.clear()
    main_module.app.storage.user["auth_user"] = user.email

    client = TestClient(main_module.app)
    resp = client.post(
        "/api/documents/upload",
        data={"company_id": str(int(company.id or 0))},
        files={"file": ("manual.pdf", b"%PDF-1.4 manual", "application/pdf")},
    )
    assert resp.status_code == 200

    with data_module.get_session() as session:
        document = session.exec(select(data_module.Document)).first()

    assert document is not None
    assert document.storage_key
    assert document.storage_key == document.storage_path
