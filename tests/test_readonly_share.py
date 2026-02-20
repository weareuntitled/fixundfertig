from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.orm import sessionmaker

APP_PATH = Path(__file__).resolve().parents[1] / "app"
if str(APP_PATH) not in sys.path:
    sys.path.append(str(APP_PATH))


def _load_modules():
    import importlib

    data_module = importlib.import_module("data")
    auth_module = importlib.import_module("services.auth")
    main_module = importlib.import_module("main")
    return data_module, auth_module, main_module


def _reset_session(data_module, tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    SQLModel.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    data_module.engine = engine
    data_module.SessionLocal = SessionLocal


def test_readonly_token_valid_single_use_and_expired(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    data_module, auth_module, _main_module = _load_modules()
    _reset_session(data_module, tmp_path)

    with data_module.get_session() as session:
        user = data_module.User(email="owner@example.com", username="owner", password_hash="x", is_active=True, is_email_verified=True)
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = int(user.id or 0)

    token, _ = auth_module.create_readonly_share_token(user_id, expires_in=timedelta(hours=1), single_use=True)
    first = auth_module.validate_readonly_share_token(token)
    second = auth_module.validate_readonly_share_token(token)
    assert first is not None
    assert second is None

    persistent_token, _ = auth_module.create_readonly_share_token(user_id, expires_in=timedelta(hours=1), single_use=False)
    assert auth_module.validate_readonly_share_token(persistent_token) is not None
    assert auth_module.validate_readonly_share_token(persistent_token) is not None

    with data_module.get_session() as session:
        expired = data_module.Token(
            user_id=user_id,
            token="expired-token",
            purpose=data_module.TokenPurpose.READONLY_SHARE,
            expires_at=datetime.utcnow() - timedelta(minutes=1),
            single_use=True,
            scope_json="{}",
        )
        session.add(expired)
        session.commit()

    assert auth_module.validate_readonly_share_token("expired-token") is None


def test_readonly_mode_blocks_document_mutation_and_share_viewer_redirect(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    data_module, _auth_module, main_module = _load_modules()
    _reset_session(data_module, tmp_path)

    with data_module.get_session() as session:
        user = data_module.User(email="owner@example.com", username="owner", password_hash="x", is_active=True, is_email_verified=True)
        session.add(user)
        session.commit()
        session.refresh(user)

        company = data_module.Company(user_id=int(user.id or 0), name="Test Co")
        session.add(company)
        session.commit()
        session.refresh(company)

        document = data_module.Document(company_id=int(company.id or 0), filename="x.pdf", original_filename="x.pdf")
        session.add(document)
        session.commit()
        session.refresh(document)

    client = TestClient(main_module.app)
    main_module.app.storage.user["auth_user"] = "owner@example.com"
    main_module.app.storage.user["readonly_mode"] = True
    main_module._require_api_auth = lambda: None

    blocked = client.delete(f"/api/documents/{int(document.id or 0)}")
    assert blocked.status_code == 403

    share_token, _ = _auth_module.create_readonly_share_token(
        int(user.id or 0),
        expires_in=timedelta(hours=1),
        single_use=True,
        scope={"invoice_id": 123},
    )
    redirect = client.get(f"/share/read/{share_token}", follow_redirects=False)
    assert redirect.status_code == 302
    assert redirect.headers.get("location") == "/viewer/invoice/123"
