from __future__ import annotations

import json
import os
import re
from enum import Enum
from typing import Iterable, Optional


class DocumentSource(str, Enum):
    MANUAL = "manual"
    N8N = "n8n"


def _dedupe_keep_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def normalize_keywords(value: Iterable[str] | str | None) -> str:
    if value is None:
        return "[]"
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return "[]"
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            items = [piece.strip() for piece in re.split(r"[,;\n]+", raw) if piece.strip()]
            return json.dumps(_dedupe_keep_order(items), ensure_ascii=False)
        if isinstance(loaded, list):
            items = [str(item).strip() for item in loaded if str(item).strip()]
            return json.dumps(_dedupe_keep_order(items), ensure_ascii=False)
        return json.dumps([str(loaded).strip()], ensure_ascii=False)
    items = [str(item).strip() for item in value if str(item).strip()]
    return json.dumps(_dedupe_keep_order(items), ensure_ascii=False)


def safe_filename(value: str) -> str:
    name = (value or "").strip()
    if not name:
        return "document"
    name = os.path.basename(name)
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = name.strip("._-")
    return name or "document"


def build_display_title(
    vendor: Optional[str],
    doc_date: Optional[str],
    amount_total: Optional[float],
    currency: Optional[str],
    fallback_filename: Optional[str],
) -> str:
    parts: list[str] = []
    if vendor:
        parts.append(str(vendor).strip())
    if doc_date:
        parts.append(str(doc_date).strip())
    if amount_total is not None:
        amount_str = f"{amount_total:.2f}"
        if currency:
            amount_str = f"{amount_str} {currency}"
        parts.append(amount_str)
    title = " - ".join([part for part in parts if part])
    if title:
        return title
    fallback = (fallback_filename or "").strip()
    if fallback:
        return os.path.splitext(os.path.basename(fallback))[0] or "Dokument"
    return "Dokument"


def build_download_filename(title: Optional[str], mime: Optional[str]) -> str:
    base = safe_filename(title or "document")
    root, ext = os.path.splitext(base)
    mime_value = (mime or "").lower().strip()
    if mime_value in {"application/pdf", "application/x-pdf"} or mime_value.endswith("/pdf"):
        return f"{root or base}.pdf"
    return base if ext or root else "document"

