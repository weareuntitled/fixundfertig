"""Zahlungsplan eines Angebots: geordnete Raten aus Prozent und Anlass.

Gespeichert wird nur die Liste ``[{"percent": 50.0, "label": "bei Auftrag"}, ...]``
als JSON-Text in ``invoice.payment_plan``. Die Beträge je Rate werden immer aus dem
Bruttobetrag des Dokuments berechnet (``installments_with_amounts``), nie gespeichert.
"""
from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

_CENTS = Decimal("0.01")


def round_cents(value: float) -> float:
    """Kaufmännisch auf Cent runden (half-up): 0,125 -> 0,13; 2,345 -> 2,35.

    ``Decimal(str(value))`` nutzt die geschriebene Zahl statt ihrer Binär-
    Annäherung. Dieselbe Regel gilt im Frontend (``roundCents`` in
    ``frontend/src/lib/payment-plan.ts``), damit Anzeige, Backend und PDF
    denselben Cent zeigen.
    """
    return float(Decimal(str(float(value))).quantize(_CENTS, rounding=ROUND_HALF_UP))


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
    amounts = [round_cents(gross * p / 100.0) for p in percents]
    if amounts and abs(sum(percents) - 100.0) < 1e-6:
        amounts[-1] = round_cents(gross - sum(amounts[:-1]))
    return amounts


def installments_with_amounts(plan: Any, gross: float) -> list[dict[str, Any]]:
    rates = parse_payment_plan(plan)
    amounts = installment_amounts(gross, [rate["percent"] for rate in rates])
    return [rate | {"amount": amount} for rate, amount in zip(rates, amounts)]


def format_percent(percent: float) -> str:
    """50 -> "50 %", 33.33 -> "33,33 %"."""
    text = f"{percent:.2f}".rstrip("0").rstrip(".")
    return f"{text.replace('.', ',')} %"
