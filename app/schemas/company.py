"""Schemas für /api/company + /api/auth/profile."""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class CompanyRead(BaseModel):
    """Read-Modell: alle Felder der Company, die im Settings-Hub angezeigt werden."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    first_name: str = ""
    last_name: str = ""
    business_type: str = ""
    is_small_business: bool = False
    street: str = ""
    postal_code: str = ""
    city: str = ""
    country: str = "Deutschland"
    email: str = ""
    phone: str = ""
    iban: str = ""
    bic: str = ""
    bank_name: str = ""
    tax_id: str = ""
    vat_id: str = ""
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    default_sender_email: str = ""
    n8n_webhook_url: str = ""
    n8n_webhook_url_test: str = ""
    n8n_webhook_url_prod: str = ""
    n8n_secret: str = ""
    n8n_enabled: bool = False
    google_drive_folder_id: str = ""
    next_invoice_nr: int = 10000
    invoice_number_template: str = "{seq}"
    invoice_filename_template: str = "rechnung_{nr}"
    logo_url: str = ""


class CompanyUpdate(BaseModel):
    """Update-Patch: alle Felder optional."""
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    business_type: str | None = None
    is_small_business: bool | None = None
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str | None = None
    email: str | None = None
    phone: str | None = None
    iban: str | None = None
    bic: str | None = None
    bank_name: str | None = None
    tax_id: str | None = None
    vat_id: str | None = None
    smtp_server: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    default_sender_email: str | None = None
    n8n_webhook_url: str | None = None
    n8n_webhook_url_test: str | None = None
    n8n_webhook_url_prod: str | None = None
    n8n_secret: str | None = None
    n8n_enabled: bool | None = None
    google_drive_folder_id: str | None = None
    next_invoice_nr: int | None = None
    invoice_number_template: str | None = None
    invoice_filename_template: str | None = None

    def patch_dict(self) -> dict:
        """Nicht-None-Felder als Patch (drop None)."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class UserProfileRead(BaseModel):
    """Read-Modell: User-Stammdaten für /settings/account."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    is_active: bool = True


class UserProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")] | None = None

    def patch_dict(self) -> dict:
        return {k: v for k, v in self.model_dump().items() if v is not None}
