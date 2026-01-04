from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import httpx


def build_payload(event: str, company_id: int | str, data: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
    payload = {
        "event": event,
        "company_id": str(company_id),
        "ts": int(time.time()),
        "data": data,
    }
    raw_body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    return raw_body, headers


def post_to_n8n(
    webhook_url: str,
    secret: str,
    event: str,
    company_id: int | str,
    data: dict[str, Any],
    timeout_s: float = 8.0,
) -> httpx.Response:
    webhook_url = (webhook_url or "").strip()
    secret = (secret or "").strip()
    if not webhook_url:
        raise ValueError("Missing webhook_url")
    if not secret:
        raise ValueError("Missing secret")

    raw_body, headers = build_payload(event, company_id, data)
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    headers.update({"X-API-KEY": secret, "X-Signature": signature})

    resp = httpx.post(webhook_url, content=raw_body, headers=headers, timeout=timeout_s)
    resp.raise_for_status()
    return resp
