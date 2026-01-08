from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable


_DECIMAL_PLACES = Decimal("0.01")


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_DECIMAL_PLACES, rounding=ROUND_HALF_UP)


def calculate_invoice_totals(
    items: Iterable[dict[str, Any]] | None,
    *,
    ust_enabled: bool,
    is_small_business: bool = False,
    allow_negative: bool = True,
) -> dict[str, float]:
    net = Decimal("0")
    tax = Decimal("0")

    for item in items or []:
        qty = _to_decimal(item.get("quantity", 0) or 0)
        unit_price = _to_decimal(item.get("unit_price", 0) or 0)
        tax_rate = _to_decimal(item.get("tax_rate", 0) or 0)

        if not allow_negative and (qty < 0 or unit_price < 0 or tax_rate < 0):
            raise ValueError("Negative values are not allowed in invoice items")

        line_net = qty * unit_price
        net += line_net

        if (not is_small_business) and ust_enabled and tax_rate > 0:
            tax += line_net * (tax_rate / Decimal("100"))

    net_q = _quantize(net)
    tax_q = _quantize(tax)
    gross_q = _quantize(net + tax)

    return {
        "net": float(net_q),
        "vat": float(tax_q),
        "gross": float(gross_q),
    }


def build_invoice_preview_html(invoice_number: str, invoice_date: str, totals: dict[str, float]) -> str:
    number = (invoice_number or "").strip()
    date = (invoice_date or "").strip()
    net = totals.get("net", 0.0)
    vat = totals.get("vat", 0.0)
    gross = totals.get("gross", 0.0)

    return (
        "<div class='invoice-preview'>"
        f"<div class='invoice-meta'>Rechnung {number}</div>"
        f"<div class='invoice-date'>{date}</div>"
        "<div class='invoice-totals'>"
        f"<span class='net'>Netto: {net:.2f}</span>"
        f"<span class='vat'>USt: {vat:.2f}</span>"
        f"<span class='gross'>Gesamt: {gross:.2f}</span>"
        "</div>"
        "</div>"
    )
