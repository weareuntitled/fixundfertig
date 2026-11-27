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
class Abschlag:
    """Eingabe: eine gestellte Abschlagsrechnung, die eine Schlussrechnung abzieht.

    Netto und Steuer kommen so, wie sie beim Anlegen der Schlussrechnung
    festgehalten wurden; das Modul lädt nichts nach.
    """

    id: int
    nr: str
    net: Any
    tax: Any
    date: str = ""


@dataclass(frozen=True)
class Abzug:
    """Ergebnis: ein Abzug der Schlussrechnung, auf Cent gerundet."""

    id: int
    nr: str
    date: str
    net: Decimal
    tax: Decimal
    gross: Decimal


@dataclass(frozen=True)
class Belegsummen:
    """Alle Beträge eines Belegs. Ohne Abzüge ist der Rest gleich der Gesamtleistung."""

    positions_net: tuple[Decimal, ...]
    net: Decimal
    vat_rate: Decimal
    tax: Decimal
    gross: Decimal
    is_final_invoice: bool
    deductions: tuple[Abzug, ...]
    sum_net: Decimal
    sum_tax: Decimal
    sum_gross: Decimal
    rest_net: Decimal
    rest_tax: Decimal
    rest_gross: Decimal
    payable: Decimal


def _abzug(row: Abschlag) -> Abzug:
    net, tax = _cents(_dec(row.net)), _cents(_dec(row.tax))
    return Abzug(id=int(row.id), nr=str(row.nr), date=str(row.date or ""), net=net, tax=tax, gross=net + tax)


def belegsummen(
    positions: Iterable[Position],
    *,
    vat_rate: Any,
    charges_vat: bool = True,
    deductions: Iterable[Abschlag] | None = None,
) -> Belegsummen:
    """Beträge eines Belegs.

    ``charges_vat`` ist falsch für Kleinunternehmer und Belege mit abgeschalteter
    USt; dann gilt 0 %. ``deductions`` ist nur bei einer Schlussrechnung gesetzt
    (auch leer); zahlbar ist dann der Restbetrag.
    """
    rate = _dec(vat_rate) if charges_vat else Decimal("0")
    lines = [_dec(p.quantity) * _dec(p.unit_price) for p in positions]
    net = _cents(sum(lines, Decimal("0")))
    tax = _cents(net * rate / 100)
    gross = net + tax
    abzuege = tuple(_abzug(row) for row in deductions or ())
    sum_net = sum((a.net for a in abzuege), Decimal("0"))
    sum_tax = sum((a.tax for a in abzuege), Decimal("0"))
    sum_gross = sum_net + sum_tax
    return Belegsummen(
        positions_net=tuple(_cents(line) for line in lines),
        net=net, vat_rate=rate, tax=tax, gross=gross,
        is_final_invoice=deductions is not None,
        deductions=abzuege,
        sum_net=sum_net, sum_tax=sum_tax, sum_gross=sum_gross,
        rest_net=net - sum_net, rest_tax=tax - sum_tax, rest_gross=gross - sum_gross,
        payable=gross - sum_gross,
    )


def legacy_vat_rate(positions: Iterable[Position], *, stored_gross: Any) -> Decimal:
    """Steuersatz eines Altbelegs ohne gespeicherten Satz, in Prozent.

    Altbelege tragen nur ihren Bruttobetrag; der Satz ergibt sich aus Brutto
    und dem Netto der Positionen, auf 0,1 % gerundet. Nur diese Stelle leitet ab.
    """
    net = sum((_dec(p.quantity) * _dec(p.unit_price) for p in positions), Decimal("0"))
    gross = _dec(stored_gross)
    if net <= 0 or gross <= net + Decimal("0.005"):
        return Decimal("0")
    return ((gross - net) / net * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
