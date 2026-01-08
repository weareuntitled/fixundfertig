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
    totals = invoice_data.get("totals", {}) if isinstance(invoice_data.get("totals"), dict) else {}

    net = escape(str(totals.get("net", 0)))
    vat = escape(str(totals.get("vat", 0)))
    gross = escape(str(totals.get("gross", 0)))

    return (
        "<div class='text-sm text-gray-700'>"
        "<div><strong>Rechnungsnummer:</strong> "
        f"{invoice_number}</div>"
        "<div><strong>Rechnungsdatum:</strong> "
        f"{invoice_date}</div>"
        "<div class='mt-2'>"
        "<div><strong>Netto:</strong> "
        f"{net} EUR</div>"
        "<div><strong>USt:</strong> "
        f"{vat} EUR</div>"
        "<div><strong>Brutto:</strong> "
        f"{gross} EUR</div>"
        "</div>"
        "</div>"
    )
