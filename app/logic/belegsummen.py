"""Belegsummen (#505/#506): alle Beträge eines Belegs aus einer Quelle.

Rein rechnend, ohne Datenbank und ohne Darstellung. Gerechnet wird mit Decimal,
kaufmännisch auf Cent gerundet (ROUND_HALF_UP).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable

_CENT = Decimal("0.01")


def _dec(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _cents(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Position:
    """Eine Position: Menge und Einzelpreis netto."""

    quantity: Any
    unit_price: Any


@dataclass(frozen=True)
class Belegsummen:
    net: Decimal
    vat_rate: Decimal
    tax: Decimal
    gross: Decimal
    payable: Decimal


def belegsummen(positions: Iterable[Position], *, vat_rate: Any, charges_vat: bool = True) -> Belegsummen:
    rate = _dec(vat_rate) if charges_vat else Decimal("0")
    net = _cents(sum((_dec(p.quantity) * _dec(p.unit_price) for p in positions), Decimal("0")))
    tax = _cents(net * rate / 100)
    gross = net + tax
    return Belegsummen(net=net, vat_rate=rate, tax=tax, gross=gross, payable=gross)
