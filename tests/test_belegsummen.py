"""Belegsummen (#506): alle Beträge eines Belegs aus einer Quelle.

Reine Wertetests am Interface des Moduls: Positionen, Steuersatz und Abzüge
hinein, erwartete Beträge heraus.
"""
from __future__ import annotations

import sys
from decimal import Decimal as D
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from logic.belegsummen import Position, belegsummen  # noqa: E402


def test_19_percent_net_tax_gross():
    summen = belegsummen([Position(quantity=2, unit_price=50)], vat_rate=19)
    assert summen.net == D("100.00")
    assert summen.vat_rate == D("19")
    assert summen.tax == D("19.00")
    assert summen.gross == D("119.00")
    assert summen.payable == D("119.00")


def test_7_percent():
    summen = belegsummen([Position(quantity=1, unit_price=200)], vat_rate=7)
    assert (summen.net, summen.vat_rate, summen.tax, summen.gross) == (D("200.00"), D("7"), D("14.00"), D("214.00"))


def test_0_percent_has_no_tax():
    summen = belegsummen([Position(quantity=3, unit_price=40)], vat_rate=0)
    assert (summen.net, summen.vat_rate, summen.tax, summen.gross) == (D("120.00"), D("0"), D("0.00"), D("120.00"))


def test_small_business_charges_no_vat_whatever_the_rate():
    summen = belegsummen([Position(quantity=1, unit_price=100)], vat_rate=19, charges_vat=False)
    assert (summen.vat_rate, summen.tax, summen.gross, summen.payable) == (D("0"), D("0.00"), D("100.00"), D("100.00"))


def test_vat_switched_off_on_the_document_equals_no_vat():
    summen = belegsummen([Position(quantity=2, unit_price=50)], vat_rate=19, charges_vat=False)
    assert summen.gross == summen.net == D("100.00")
