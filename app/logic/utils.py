from __future__ import annotations

import csv
import io
import os
import re
from typing import Any, List

from sqlmodel import Session


def project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def storage_dir() -> str:
    return os.path.join(project_root(), "storage")


def invoices_dir() -> str:
    return os.path.join(storage_dir(), "invoices")


def safe_filename(name: str) -> str:
    name = (name or "").strip() or "export"
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"[^a-zA-Z0-9äöüÄÖÜß _\.\(\)\[\]\-]+", "_", name)
    name = name.replace("/", "_").replace("\\", "_").replace(":", "_")
    return name[:120] if len(name) > 120 else name


def csv_bytes(rows: List[List[Any]], header: List[str]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(header)
    for r in rows:
        writer.writerow([("" if v is None else v) for v in r])
    return buf.getvalue().encode("utf-8-sig")


def parse_export_args(args, kwargs, *, needs_ids: bool = True):
    """Einheitliches Parsen der (session, company_id, [ids]) Signatur."""
    session = kwargs.get("session")
    company_id = kwargs.get("company_id") or kwargs.get("comp_id")
    ids = kwargs.get("invoice_ids") or kwargs.get("document_ids") or kwargs.get("ids")

    if args:
        if isinstance(args[0], Session):
            session = args[0]
        if len(args) > 1 and isinstance(args[1], int):
            company_id = int(args[1])
        if needs_ids and len(args) > 2 and isinstance(args[2], list):
            ids = [int(x) for x in args[2]]

    if session is None:
        raise ValueError("session fehlt")
    if company_id is None:
        raise ValueError("company_id fehlt")
    return session, int(company_id), ids
