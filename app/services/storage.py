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


def ensure_company_dirs(company_id: int | str) -> None:
    os.makedirs(company_upload_dir(company_id), exist_ok=True)


def delete_company_dirs(company_id: int | str) -> None:
    shutil.rmtree(company_dir(company_id), ignore_errors=True)
