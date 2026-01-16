from __future__ import annotations

import hashlib
import os
from datetime import datetime


_ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789._-")


def _sanitize_filename(value: str) -> str:
    name = os.path.basename(value or "").strip() or "upload"
    cleaned: list[str] = []
    for ch in name.lower():
        if ch == " ":
            ch = "_"
        if ch in _ALLOWED_CHARS:
            cleaned.append(ch)
    result = "".join(cleaned).strip()
    return result or "upload"


def _mime_from_extension(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower().lstrip(".")
    if ext == "pdf":
        return "application/pdf"
    if ext in {"jpg", "jpeg"}:
        return "image/jpeg"
    if ext == "png":
        return "image/png"
    if ext == "gif":
        return "image/gif"
    if ext == "webp":
        return "image/webp"
    if ext == "heic":
        return "image/heic"
    return "application/octet-stream"


def save_upload_bytes(
    company_id: int | str,
    original_filename: str,
    content_bytes: bytes,
    mime: str | None,
) -> dict:
    sanitized = _sanitize_filename(original_filename)
    sha256 = hashlib.sha256(content_bytes).hexdigest()
    now = datetime.utcnow()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    storage_key = f"utc_{timestamp}_{sha256[:12]}_{sanitized}"
    base_dir = os.path.join(
        "storage",
        "documents",
        str(company_id),
        now.strftime("%Y"),
        now.strftime("%m"),
    )
    os.makedirs(base_dir, exist_ok=True)
    path = os.path.join(base_dir, storage_key)
    with open(path, "wb") as handle:
        handle.write(content_bytes)
    mime_value = (mime or "").strip() or _mime_from_extension(original_filename)
    return {
        "storage_key": storage_key,
        "path": path,
        "sha256": sha256,
        "size": len(content_bytes),
        "mime": mime_value,
    }
