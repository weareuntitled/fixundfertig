"""Zahlungsplan eines Angebots: geordnete Raten aus Prozent und Anlass.

Gespeichert wird nur die Liste ``[{"percent": 50.0, "label": "bei Auftrag"}, ...]``
als JSON-Text in ``invoice.payment_plan``. Die Beträge je Rate werden immer aus dem
Bruttobetrag des Dokuments berechnet (``installments_with_amounts``), nie gespeichert.
"""
from __future__ import annotations

import json
from typing import Any


def parse_payment_plan(raw: Any) -> list[dict[str, Any]]:
    """Installments from the stored JSON text, a list of dicts/models, or nothing."""
    if raw in (None, ""):
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    if not isinstance(raw, list):
        return []
    plan: list[dict[str, Any]] = []
    for entry in raw:
        if hasattr(entry, "model_dump"):
            entry = entry.model_dump()
        if not isinstance(entry, dict):
            continue
        try:
            percent = float(entry.get("percent") or 0)
        except (TypeError, ValueError):
            continue
        if percent <= 0:
            continue
        plan.append({"percent": percent, "label": str(entry.get("label") or "").strip()})
    return plan


def dump_payment_plan(plan: Any) -> str:
    """JSON text for the ``payment_plan`` column (amounts are never stored)."""
    return json.dumps(parse_payment_plan(plan), ensure_ascii=False)


def installment_amounts(gross: float, percents: list[float]) -> list[float]:
    """Gross amount per installment, rounded to cents.

    When the plan adds up to 100 %, the last installment takes the rounding rest so
    the amounts add up exactly to the gross total.
    """
    amounts = [round(gross * p / 100.0, 2) for p in percents]
    if amounts and abs(sum(percents) - 100.0) < 1e-6:
        amounts[-1] = round(gross - sum(amounts[:-1]), 2)
    return amounts


def installments_with_amounts(plan: Any, gross: float) -> list[dict[str, Any]]:
    rates = parse_payment_plan(plan)
    amounts = installment_amounts(gross, [rate["percent"] for rate in rates])
    return [rate | {"amount": amount} for rate, amount in zip(rates, amounts)]


def format_percent(percent: float) -> str:
    """50 -> "50 %", 33.33 -> "33,33 %"."""
    text = f"{percent:.2f}".rstrip("0").rstrip(".")
    return f"{text.replace('.', ',')} %"
