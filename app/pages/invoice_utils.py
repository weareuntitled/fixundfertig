from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from html import escape
from typing import Iterable, Mapping


def _to_decimal(value: float | int | str | None) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def compute_invoice_totals(
    items: Iterable[Mapping[str, object]],
    vat_enabled: bool,
    vat_rate: float,
) -> tuple[float, float, float]:
    net = Decimal("0")
    for item in items:
        quantity = _to_decimal(item.get("quantity"))
        unit_price = _to_decimal(item.get("unit_price"))
        net += quantity * unit_price

    net = net.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    vat = Decimal("0")

    if vat_enabled:
        vat_multiplier = _to_decimal(vat_rate) / Decimal("100")
        vat = (net * vat_multiplier).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    gross = (net + vat).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(net), float(vat), float(gross)


def build_invoice_preview_html(invoice_data: Mapping[str, object]) -> str:
    invoice_number = escape(str(invoice_data.get("invoice_number", "")))
    invoice_date = escape(str(invoice_data.get("invoice_date", "")))
    filename = escape(str(invoice_data.get("filename", "")))
    totals = invoice_data.get("totals", {}) if isinstance(invoice_data.get("totals"), dict) else {}

    net = escape(str(totals.get("net", 0)))
    vat = escape(str(totals.get("vat", 0)))
    gross = escape(str(totals.get("gross", 0)))
    filename_row = ""
    if filename:
        filename_row = (
            "<div class='text-neutral-400'>Dateiname</div>"
            f"<div class='font-medium text-neutral-100 break-all'>{filename}</div>"
        )

    return (
        "<div class='text-sm text-neutral-300'>"
        "<div class='grid grid-cols-[140px_1fr] gap-x-3 gap-y-1'>"
        "<div class='text-neutral-400'>Rechnungsnummer</div>"
        f"<div class='font-medium text-neutral-100'>{invoice_number}</div>"
        "<div class='text-neutral-400'>Rechnungsdatum</div>"
        f"<div class='font-medium text-neutral-100'>{invoice_date}</div>"
        f"{filename_row}"
        "</div>"
        "<div class='mt-3 grid grid-cols-[140px_1fr] gap-x-3 gap-y-1'>"
        "<div class='text-neutral-400'>Netto</div>"
        f"<div class='font-medium text-neutral-100'>{net} EUR</div>"
        "<div class='text-neutral-400'>USt</div>"
        f"<div class='font-medium text-neutral-100'>{vat} EUR</div>"
        "<div class='text-neutral-400'>Brutto</div>"
        f"<div class='font-semibold text-neutral-100'>{gross} EUR</div>"
        "</div>"
        "</div>"
    )
