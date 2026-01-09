from __future__ import annotations

import os
import shutil


_STORAGE_ROOT = "storage"
_COMPANY_ROOT = os.path.join(_STORAGE_ROOT, "companies")


def company_dir(company_id: int | str) -> str:
    return os.path.join(_COMPANY_ROOT, str(company_id))


def company_logo_path(company_id: int | str) -> str:
    return os.path.join(company_dir(company_id), "logo.png")


def company_upload_dir(company_id: int | str) -> str:
    return os.path.join(company_dir(company_id), "uploads")


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
