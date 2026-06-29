from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel

from dependencies import get_current_company, require_session_auth
from schemas.company import CompanyRead, CompanyUpdate
from services.companies import update_company
from services.email import send_email
from services.storage import cleanup_company_logos, company_dir, company_logo_path

logger = logging.getLogger(__name__)

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


class StripeTestResponse(BaseModel):
    success: bool
    message: str


@router.post("/test-stripe", response_model=StripeTestResponse)
def test_stripe_connection(
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
) -> StripeTestResponse:
    if not company.stripe_secret_key:
        return StripeTestResponse(success=False, message="Kein Stripe Secret Key hinterlegt.")
    try:
        import stripe  # type: ignore[import-untyped]
        stripe.api_key = company.stripe_secret_key
        stripe.Balance.retrieve()
        return StripeTestResponse(success=True, message="Stripe-Verbindung erfolgreich.")
    except Exception as e:
        logger.warning("Stripe test failed: %s", e)
        return StripeTestResponse(success=False, message=f"Stripe-Fehler: {e}")


class TestEmailRequest(BaseModel):
    to: str = ""


class TestEmailResponse(BaseModel):
    success: bool
    message: str


@router.post("/test-email", response_model=TestEmailResponse)
def test_email(
    payload: TestEmailRequest,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
) -> TestEmailResponse:
    recipient = (payload.to or "").strip() or company.email or ""
    if not recipient:
        return TestEmailResponse(success=False, message="Keine E-Mail-Adresse angegeben und keine Firmen-E-Mail hinterlegt.")

    smtp_config = {
        "host": company.smtp_server,
        "port": company.smtp_port or 587,
        "user": company.smtp_user,
        "password": company.smtp_password,
        "sender": company.default_sender_email or company.email or company.smtp_user,
    }

    missing = [k for k, v in smtp_config.items() if not v]
    if missing:
        return TestEmailResponse(success=False, message=f"SMTP unvollständig: {', '.join(missing)}")

    payment_link = ""
    if company.stripe_secret_key and company.payment_enabled:
        try:
            import stripe  # type: ignore[import-untyped]
            stripe.api_key = company.stripe_secret_key
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "eur",
                        "product_data": {"name": "Webentwicklung (Test)"},
                        "unit_amount": 149900,
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url="http://127.0.0.1:8000/settings?paid=1",
                cancel_url="http://127.0.0.1:8000/settings",
                client_reference_id="test-email",
            )
            payment_link = session.url or ""
        except Exception as e:
            logger.warning("Stripe link creation failed in test email: %s", e)

    invoice_nr = "T-2024-0001"
    invoice_date = "13.06.2026"
    due_date = "13.07.2026"
    amount = "1.499,00"
    customer_name = "Max Mustermann"

    text = (
        f"Rechnung {invoice_nr} von {company.name or 'FixundFertig'}\n"
        f"{'=' * 50}\n\n"
        f"Sehr geehrter Kunde,\n\n"
        f"anbei erhalten Sie Ihre Rechnung {invoice_nr} vom {invoice_date}.\n\n"
        f"Betrag: {amount} €\n"
        f"Fällig bis: {due_date}\n\n"
    )
    if payment_link:
        text += f"Bezahlen Sie jetzt bequem per Karte:\n{payment_link}\n\n"
    text += (
        f"Leistung: Webentwicklung (Test)\n"
        f"Anzahl: 1\n"
        f"Einzelpreis: {amount} €\n\n"
        f"Vielen Dank für Ihren Auftrag.\n\n"
        f"Mit freundlichen Grüßen\n"
        f"{company.name or 'FixundFertig'}"
    )

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Inter,-apple-system,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px;">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08);">
<tr><td style="padding:32px 32px 0;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="font-size:20px;font-weight:700;color:#001a42;">{company.name or 'FixundFertig'}</td>
<td align="right" style="font-size:12px;color:#6b7280;">Rechnung {invoice_nr}</td>
</tr>
</table>
<hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0;">
</td></tr>
<tr><td style="padding:0 32px;">
<p style="font-size:14px;color:#374151;margin:0 0 16px;">Sehr geehrter Kunde,</p>
<p style="font-size:14px;color:#374151;margin:0 0 16px;">vielen Dank für Ihren Auftrag. Im Folgenden erhalten Sie die Details Ihrer Rechnung.</p>
</td></tr>
<tr><td style="padding:0 32px;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;border-radius:8px;padding:16px;">
<tr><td style="font-size:12px;color:#6b7280;padding-bottom:8px;">Rechnungsnummer</td>
<td align="right" style="font-size:12px;color:#6b7280;padding-bottom:8px;">Datum</td></tr>
<tr><td style="font-size:16px;font-weight:600;color:#001a42;">{invoice_nr}</td>
<td align="right" style="font-size:16px;font-weight:600;color:#001a42;">{invoice_date}</td></tr>
</table>
</td></tr>
<tr><td style="padding:16px 32px 0;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr style="font-size:12px;color:#6b7280;border-bottom:1px solid #e5e7eb;">
<td style="padding-bottom:8px;">Leistung</td>
<td align="right" style="padding-bottom:8px;">Betrag</td>
</tr>
<tr style="font-size:14px;color:#374151;">
<td style="padding:8px 0;">Webentwicklung (Test) × 1</td>
<td align="right" style="padding:8px 0;">{amount} €</td>
</tr>
</table>
</td></tr>
<tr><td style="padding:12px 32px 0;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td style="font-size:12px;color:#6b7280;">Zwischensumme</td>
<td align="right" style="font-size:14px;color:#374151;">{amount} €</td></tr>
<tr><td style="font-size:12px;color:#6b7280;">MwSt. 19%</td>
<td align="right" style="font-size:14px;color:#374151;">239,21 €</td></tr>
<tr><td style="font-size:16px;font-weight:700;color:#001a42;padding-top:8px;border-top:2px solid #001a42;">Gesamtbetrag</td>
<td align="right" style="font-size:16px;font-weight:700;color:#001a42;padding-top:8px;border-top:2px solid #001a42;">{amount} €</td></tr>
</table>
</td></tr>
<tr><td style="padding:16px 32px;">
<p style="font-size:12px;color:#6b7280;margin:0;">Fällig bis: <strong style="color:#374151;">{due_date}</strong></p>
</td></tr>"""

    if payment_link:
        html += f"""
<tr><td style="padding:0 32px 16px;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;">
<p style="font-size:13px;color:#166534;margin:0 0 12px;font-weight:600;">Jetzt online bezahlen</p>
<a href="{payment_link}" target="_blank" style="display:inline-block;background:#001a42;color:#fff;font-size:14px;font-weight:600;padding:12px 32px;border-radius:8px;text-decoration:none;">Zahlungslink öffnen</a>
<p style="font-size:11px;color:#166534;margin:8px 0 0;">Sicher bezahlen per Karte (Stripe)</p>
</td></tr>
</table>
</td></tr>"""

    html += f"""
<tr><td style="padding:0 32px 32px;">
<p style="font-size:13px;color:#374151;margin:0 0 4px;">Mit freundlichen Grüßen</p>
<p style="font-size:14px;font-weight:600;color:#001a42;margin:0;">{company.name or 'FixundFertig'}</p>
</td></tr>
<tr><td style="padding:16px 32px;background:#f9fafb;border-top:1px solid #e5e7eb;">
<p style="font-size:11px;color:#9ca3af;margin:0;text-align:center;">Dies ist eine automatisch generierte Test-E-Mail von FixundFertig.</p>
</td></tr>
</table>
</td></tr></table>
</body>
</html>"""

    try:
        send_email(
            to=recipient,
            subject=f"Rechnung {invoice_nr} von {company.name or 'FixundFertig'} — {amount} €",
            text=text,
            html=html,
            smtp_config=smtp_config,
        )
    except Exception as e:
        logger.exception("Test email failed")
        return TestEmailResponse(success=False, message=f"E-Mail-Versand fehlgeschlagen: {e}")

    msg = f"Test-Rechnung an {recipient} gesendet."
    if payment_link:
        msg += " (mit Stripe-Zahlungslink)"
    return TestEmailResponse(success=True, message=msg)
