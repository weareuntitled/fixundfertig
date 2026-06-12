from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from dependencies import get_current_company, require_session_auth
from schemas.company import CompanyRead, CompanyUpdate
from services.companies import update_company
from services.storage import cleanup_company_logos, company_dir, company_logo_path

router = APIRouter(prefix="/api/company", tags=["company"])


def _logo_url(company) -> str:
    rel = company_logo_path(company.id)
    return f"/{rel.replace(os.sep, '/')}" if os.path.exists(rel) else ""


def _company_read(company) -> CompanyRead:
    data = CompanyRead.model_validate(company)
    data.logo_url = _logo_url(company)
    return data


@router.get("", response_model=CompanyRead)
def get_company(
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
) -> CompanyRead:
    return _company_read(company)


@router.put("", response_model=CompanyRead)
def update_current_company(
    payload: CompanyUpdate,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
) -> CompanyRead:
    try:
        updated = update_company(
            user_id=int(_user_id),
            company_id=int(company.id),
            patch=payload.patch_dict(),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return _company_read(updated)


@router.post("/logo", response_model=CompanyRead)
async def upload_logo(
    file: UploadFile,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
) -> CompanyRead:
    ext = (file.filename or "logo.png").rsplit(".", 1)[-1].lower()
    if ext not in {"png", "jpg", "jpeg"}:
        raise HTTPException(status_code=400, detail="Nur PNG/JPG erlaubt")

    os.makedirs(company_dir(company.id), exist_ok=True)

    dest = company_logo_path(company.id, ext)
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)

    cleanup_company_logos(company.id, ext)
    return _company_read(company)
