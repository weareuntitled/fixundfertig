from __future__ import annotations

import os
import shutil


_STORAGE_ROOT = "storage"
_COMPANY_ROOT = os.path.join(_STORAGE_ROOT, "companies")


def company_dir(company_id: int | str) -> str:
    return os.path.join(_COMPANY_ROOT, str(company_id))


def company_logo_path(company_id: int | str, ext: str | None = None) -> str:
    if ext:
        safe_ext = ext.lower().lstrip(".")
        if safe_ext == "jpeg":
            safe_ext = "jpg"
        if safe_ext not in {"png", "jpg"}:
            safe_ext = "png"
        return os.path.join(company_dir(company_id), f"logo.{safe_ext}")
    for candidate in ("png", "jpg"):
        path = os.path.join(company_dir(company_id), f"logo.{candidate}")
        if os.path.exists(path):
            return path
    return os.path.join(company_dir(company_id), "logo.png")


def cleanup_company_logos(company_id: int | str, keep_ext: str) -> None:
    keep_ext = keep_ext.lower().lstrip(".")
    if keep_ext == "jpeg":
        keep_ext = "jpg"
    for candidate in ("png", "jpg"):
        if candidate == keep_ext:
            continue
        path = os.path.join(company_dir(company_id), f"logo.{candidate}")
        if os.path.exists(path):
            os.remove(path)


def company_upload_dir(company_id: int | str) -> str:
    return os.path.join(company_dir(company_id), "uploads")

def company_documents_dir(company_id: int | str) -> str:
    return os.path.join(company_dir(company_id), "documents")


def company_documents_dir(company_id: int | str) -> str:
    return os.path.join(company_dir(company_id), "documents")


def company_document_dir(company_id: int | str, document_id: int | str) -> str:
    return os.path.join(company_documents_dir(company_id), str(document_id))


def company_document_path(company_id: int | str, document_id: int | str, filename: str) -> str:
    return os.path.join(company_document_dir(company_id, document_id), filename)


def ensure_company_dirs(company_id: int | str) -> None:
    os.makedirs(company_upload_dir(company_id), exist_ok=True)
    os.makedirs(company_documents_dir(company_id), exist_ok=True)


def delete_company_dirs(company_id: int | str) -> None:
    shutil.rmtree(company_dir(company_id), ignore_errors=True)
