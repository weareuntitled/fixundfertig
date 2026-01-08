from __future__ import annotations

from html import escape
from typing import Any, Iterable


def compute_invoice_totals(
    items: Iterable[dict[str, Any]],
    vat_enabled: bool,
    vat_rate: float,
) -> tuple[float, float, float]:
    net_total = 0.0
    vat_total = 0.0

    for item in items or []:
        quantity = float(item.get("quantity") or 0)
        unit_price = float(item.get("unit_price") or 0)
        line_net = quantity * unit_price
        net_total += line_net

        if vat_enabled:
            line_rate = float(item.get("tax_rate") or vat_rate or 0)
            vat_total += line_net * (line_rate / 100)

    net_total = round(net_total, 2)
    vat_total = round(vat_total, 2) if vat_enabled else 0.0
    gross_total = round(net_total + vat_total, 2)
    return net_total, vat_total, gross_total


def build_invoice_preview_html(invoice_data: dict[str, Any]) -> str:
    title = escape(str(invoice_data.get("title") or "Rechnung"))
    invoice_date = escape(str(invoice_data.get("invoice_date") or ""))
    service_from = escape(str(invoice_data.get("service_from") or ""))
    service_to = escape(str(invoice_data.get("service_to") or ""))
    intro_text = escape(str(invoice_data.get("intro_text") or ""))
    customer = invoice_data.get("customer") or {}
    items = invoice_data.get("items") or []
    vat_enabled = bool(invoice_data.get("show_tax"))
    default_vat_rate = float(invoice_data.get("vat_rate") or 0)

    net, vat, gross = compute_invoice_totals(items, vat_enabled, default_vat_rate)

    customer_lines = [
        str(customer.get("name") or ""),
        str(customer.get("street") or customer.get("address") or ""),
        " ".join(
            p for p in [str(customer.get("zip") or ""), str(customer.get("city") or "")] if p.strip()
        ).strip(),
    ]
    customer_html = "<br>".join(escape(line) for line in customer_lines if line.strip())

    rows_html = ""
    for item in items:
        desc = escape(str(item.get("description") or ""))
        qty = float(item.get("quantity") or 0)
        price = float(item.get("unit_price") or 0)
        tax_rate = float(item.get("tax_rate") or default_vat_rate or 0)
        rows_html += (
            "<tr>"
            f"<td class='text-left'>{desc}</td>"
            f"<td class='text-right'>{qty:g}</td>"
            f"<td class='text-right'>{price:,.2f}</td>"
            f"<td class='text-right'>{tax_rate:.0f}%</td>"
            "</tr>"
        )

    vat_row = ""
    if vat_enabled:
        vat_row = (
            "<tr>"
            "<td colspan='3' class='text-right'>USt</td>"
            f"<td class='text-right'>{vat:,.2f}</td>"
            "</tr>"
        )

    return (
        "<div class='space-y-4 text-sm'>"
        f"<div class='font-semibold text-lg'>{title}</div>"
        "<div class='flex flex-col gap-1'>"
        f"<div>Rechnungsdatum: {invoice_date}</div>"
        f"<div>Leistungszeitraum: {service_from} bis {service_to}</div>"
        "</div>"
        f"<div class='text-gray-700'>{customer_html}</div>"
        f"<div>{intro_text}</div>"
        "<table class='w-full text-sm border-collapse'>"
        "<thead>"
        "<tr class='border-b'>"
        "<th class='text-left py-2'>Beschreibung</th>"
        "<th class='text-right py-2'>Menge</th>"
        "<th class='text-right py-2'>Preis</th>"
        "<th class='text-right py-2'>USt</th>"
        "</tr>"
        "</thead>"
        "<tbody>"
        f"{rows_html}"
        "</tbody>"
        "<tfoot>"
        "<tr>"
        "<td colspan='3' class='text-right'>Netto</td>"
        f"<td class='text-right'>{net:,.2f}</td>"
        "</tr>"
        f"{vat_row}"
        "<tr class='font-semibold'>"
        "<td colspan='3' class='text-right'>Brutto</td>"
        f"<td class='text-right'>{gross:,.2f}</td>"
        "</tr>"
        "</tfoot>"
        "</table>"
        "</div>"
    )
