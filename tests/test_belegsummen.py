"""Belegsummen (#506): alle Beträge eines Belegs aus einer Quelle.

Reine Wertetests am Interface des Moduls: Positionen, Steuersatz und Abzüge
hinein, erwartete Beträge heraus.
"""
from __future__ import annotations

import sys
from decimal import Decimal as D
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from logic.belegsummen import Abschlag, Position, belegsummen, legacy_vat_rate  # noqa: E402


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


def test_quantity_zero_counts_zero():
    summen = belegsummen(
        [Position(quantity=0, unit_price=100), Position(quantity=1, unit_price=10)], vat_rate=19
    )
    assert summen.positions_net == (D("0.00"), D("10.00"))
    assert summen.gross == D("11.90")


def test_negative_positions_reduce_the_amounts():
    summen = belegsummen(
        [Position(quantity=1, unit_price=100), Position(quantity=-1, unit_price=10)], vat_rate=19
    )
    assert (summen.net, summen.tax, summen.gross) == (D("90.00"), D("17.10"), D("107.10"))


def test_fully_negative_document():
    summen = belegsummen([Position(quantity=-1, unit_price=10)], vat_rate=19)
    assert (summen.net, summen.tax, summen.gross) == (D("-10.00"), D("-1.90"), D("-11.90"))


def test_empty_positions_are_all_zero():
    summen = belegsummen([], vat_rate=19)
    assert (summen.net, summen.tax, summen.gross, summen.payable) == (D("0"), D("0"), D("0"), D("0"))
    assert summen.positions_net == ()


def test_net_rounds_half_up_to_cents():
    # 1,5 × 33,33 = 49,995 → 50,00 (binäre Fließkommazahlen ergäben 49,99)
    summen = belegsummen([Position(quantity=1.5, unit_price=33.33)], vat_rate=19)
    assert (summen.net, summen.tax, summen.gross) == (D("50.00"), D("9.50"), D("59.50"))


def test_tax_rounds_half_up_and_gross_is_net_plus_tax():
    # 10,50 × 19 % = 1,995 → 2,00
    summen = belegsummen([Position(quantity=1, unit_price=10.50)], vat_rate=19)
    assert (summen.tax, summen.gross) == (D("2.00"), D("12.50"))
    # 9,99 × 19 % = 1,8981 → 1,90
    summen = belegsummen([Position(quantity=1, unit_price=9.99)], vat_rate=19)
    assert (summen.tax, summen.gross) == (D("1.90"), D("11.89"))
    # 0,50 × 7 % = 0,035 → 0,04
    summen = belegsummen([Position(quantity=1, unit_price=0.50)], vat_rate=7)
    assert (summen.tax, summen.gross) == (D("0.04"), D("0.54"))


def test_net_per_position_is_rounded_to_cents():
    summen = belegsummen(
        [Position(quantity=1.5, unit_price=33.33), Position(quantity=2, unit_price=10)], vat_rate=19
    )
    assert summen.positions_net == (D("50.00"), D("20.00"))


def test_ordinary_document_has_no_deductions_and_pays_gross():
    summen = belegsummen([Position(quantity=1, unit_price=100)], vat_rate=19)
    assert summen.is_final_invoice is False
    assert summen.deductions == ()
    assert summen.payable == summen.gross == D("119.00")


def test_final_invoice_without_down_payments_pays_full_gross():
    summen = belegsummen([Position(quantity=1, unit_price=2000)], vat_rate=19, deductions=[])
    assert summen.is_final_invoice is True
    assert summen.deductions == ()
    assert (summen.sum_net, summen.sum_tax, summen.sum_gross) == (D("0"), D("0"), D("0"))
    assert (summen.rest_net, summen.rest_tax, summen.rest_gross) == (D("2000.00"), D("380.00"), D("2380.00"))
    assert summen.payable == D("2380.00")


def test_final_invoice_with_one_down_payment():
    summen = belegsummen(
        [Position(quantity=1, unit_price=2000)], vat_rate=19,
        deductions=[Abschlag(id=7, nr="10001", date="2026-03-01", net=1000, tax=190)],
    )
    assert (summen.net, summen.tax, summen.gross) == (D("2000.00"), D("380.00"), D("2380.00"))
    (abzug,) = summen.deductions
    assert (abzug.id, abzug.nr, abzug.date) == (7, "10001", "2026-03-01")
    assert (abzug.net, abzug.tax, abzug.gross) == (D("1000.00"), D("190.00"), D("1190.00"))
    assert (summen.sum_net, summen.sum_tax, summen.sum_gross) == (D("1000.00"), D("190.00"), D("1190.00"))
    assert (summen.rest_net, summen.rest_tax, summen.rest_gross) == (D("1000.00"), D("190.00"), D("1190.00"))
    assert summen.payable == D("1190.00")


def test_final_invoice_with_several_down_payments():
    summen = belegsummen(
        [Position(quantity=1, unit_price=3333.33)], vat_rate=19,
        deductions=[
            Abschlag(id=1, nr="A", net=1000, tax=190),
            Abschlag(id=2, nr="B", net=1111.11, tax=211.11),
            Abschlag(id=3, nr="C", net=333.33, tax=63.33),
        ],
    )
    # Gesamtleistung: 3333,33 netto, 633,33 USt (633,3327), 3966,66 brutto
    assert (summen.net, summen.tax, summen.gross) == (D("3333.33"), D("633.33"), D("3966.66"))
    assert [a.nr for a in summen.deductions] == ["A", "B", "C"]
    assert (summen.sum_net, summen.sum_tax, summen.sum_gross) == (D("2444.44"), D("464.44"), D("2908.88"))
    assert (summen.rest_net, summen.rest_tax, summen.rest_gross) == (D("888.89"), D("168.89"), D("1057.78"))
    assert summen.payable == D("1057.78")


def test_final_invoice_for_small_business_has_no_tax_anywhere():
    summen = belegsummen(
        [Position(quantity=1, unit_price=2000)], vat_rate=19, charges_vat=False,
        deductions=[Abschlag(id=1, nr="A", net=500, tax=0), Abschlag(id=2, nr="B", net=500, tax=0)],
    )
    assert (summen.tax, summen.gross) == (D("0.00"), D("2000.00"))
    assert (summen.sum_net, summen.sum_tax, summen.sum_gross) == (D("1000.00"), D("0.00"), D("1000.00"))
    assert (summen.rest_net, summen.rest_tax, summen.rest_gross) == (D("1000.00"), D("0.00"), D("1000.00"))
    assert summen.payable == D("1000.00")


def test_legacy_document_rate_is_derived_from_stored_gross():
    positions = [Position(quantity=1, unit_price=33.33)]
    rate = legacy_vat_rate(positions, stored_gross=39.66)
    # 6,33 / 33,33 = 18,99 % → auf 0,1 % gerundet 19,0 %
    assert rate == D("19.0")
    assert belegsummen(positions, vat_rate=rate).gross == D("39.66")


def test_legacy_rate_keeps_reduced_and_odd_rates():
    assert legacy_vat_rate([Position(quantity=2, unit_price=50)], stored_gross=107) == D("7.0")
    assert legacy_vat_rate([Position(quantity=1, unit_price=100)], stored_gross=107.5) == D("7.5")


def test_legacy_rate_is_zero_without_surplus_or_without_net():
    assert legacy_vat_rate([Position(quantity=1, unit_price=100)], stored_gross=100) == D("0")
    assert legacy_vat_rate([Position(quantity=1, unit_price=100)], stored_gross=100.004) == D("0")
    assert legacy_vat_rate([], stored_gross=50) == D("0")
    assert legacy_vat_rate([Position(quantity=1, unit_price=100)], stored_gross=None) == D("0")
