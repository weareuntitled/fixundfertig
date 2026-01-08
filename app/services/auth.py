from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime

DATA_PATH = "storage/auth_test.json"


def _load_store() -> dict:
    if not os.path.exists(DATA_PATH):
        return {"users": {}, "verify_tokens": {}, "reset_tokens": {}, "sessions": {}}
    with open(DATA_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_store(store: dict) -> None:
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    tmp_path = f"{DATA_PATH}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(store, handle, indent=2, sort_keys=True)
    os.replace(tmp_path, DATA_PATH)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_user_pending(email: str, username: str, password: str) -> dict:
    email_normalized = (email or "").strip().lower()
    username_clean = (username or "").strip()
    if not email_normalized:
        raise ValueError("Email is required")
    if not password:
        raise ValueError("Password is required")

    store = _load_store()
    if email_normalized in store["users"]:
        raise ValueError("User already exists")
    if username_clean:
        for user in store["users"].values():
            if (user.get("username") or "").strip().lower() == username_clean.lower():
                raise ValueError("Username already exists")

    user_id = uuid.uuid4().hex
    store["users"][email_normalized] = {
        "id": user_id,
        "email": email_normalized,
        "username": username_clean,
        "password_hash": _hash_password(password),
        "verified": False,
    }
    _save_store(store)
    return store["users"][email_normalized]


def create_verify_email_token(user_id: str) -> str:
    store = _load_store()
    target_email = None
    for email, user in store["users"].items():
        if user.get("id") == user_id:
            target_email = email
            break
    if not target_email:
        raise ValueError("User not found")

    token = uuid.uuid4().hex
    store["verify_tokens"][token] = target_email
    _save_store(store)
    return token


def verify_email(token: str) -> bool:
    store = _load_store()
    email = store["verify_tokens"].pop(token, None)
    if not email:
        return False
    user = store["users"].get(email)
    if not user:
        return False
    user["verified"] = True
    store["users"][email] = user
    _save_store(store)
    return True


def verify_password(email: str, password: str) -> bool:
    store = _load_store()
    user, _ = _find_user_by_identifier(store, email)
    if not user:
        return False
    return user.get("password_hash") == _hash_password(password or "")


def login_user(email: str) -> bool:
    store = _load_store()
    user, email_normalized = _find_user_by_identifier(store, email)
    if not user or not email_normalized:
        return False
    store.setdefault("sessions", {})
    store["sessions"][email_normalized] = {"last_login": datetime.now().isoformat()}
    _save_store(store)
    return True


def request_password_reset(email: str) -> str | None:
    store = _load_store()
    email_normalized = (email or "").strip().lower()
    if email_normalized not in store["users"]:
        return None
    token = uuid.uuid4().hex
    store["reset_tokens"][token] = email_normalized
    _save_store(store)
    return token


def reset_password(token: str, new_password: str) -> bool:
    store = _load_store()
    email = store["reset_tokens"].pop(token, None)
    if not email:
        return False
    user = store["users"].get(email)
    if not user:
        return False
    user["password_hash"] = _hash_password(new_password or "")
    store["users"][email] = user
    _save_store(store)
    return True


def _find_user_by_identifier(store: dict, identifier: str) -> tuple[dict | None, str | None]:
    identifier_clean = (identifier or "").strip().lower()
    if not identifier_clean:
        return None, None
    if identifier_clean in store["users"]:
        return store["users"][identifier_clean], identifier_clean
    for email, user in store["users"].items():
        if (user.get("username") or "").strip().lower() == identifier_clean:
            return user, email
    return None, None
