"""Kaufmännisches Runden auf Cent — eine Regel für Backend und Frontend (#Fix 6).

Dieselben Fälle stehen in frontend/src/lib/payment-plan.test.ts: die Anzeige im
Frontend und das Backend müssen denselben Cent zeigen.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.payment_plan import installment_amounts, round_cents  # noqa: E402


def test_round_cents_rounds_half_up():
    assert round_cents(0.125) == 0.13
    assert round_cents(2.345) == 2.35
    assert round_cents(5.025) == 5.03
    assert round_cents(50.005) == 50.01
    assert round_cents(1.005) == 1.01


def test_round_cents_keeps_amounts_that_are_already_cents():
    assert round_cents(2380) == 2380
    assert round_cents(33.33) == 33.33
    assert round_cents(0) == 0


def test_round_cents_rounds_down_below_the_half():
    assert round_cents(0.124) == 0.12
    assert round_cents(50.004) == 50


def test_round_cents_rounds_negative_amounts_away_from_zero():
    assert round_cents(-0.125) == -0.13


def test_installment_amounts_use_the_same_rule():
    assert installment_amounts(4760, [50, 50]) == [2380, 2380]
    assert installment_amounts(4000, [50, 25, 25]) == [2000, 1000, 1000]
    assert installment_amounts(100.01, [50]) == [50.01]
    assert installment_amounts(10.05, [50]) == [5.03]
    assert installment_amounts(0.125, [100]) == [0.13]


def test_installment_amounts_give_the_rounding_rest_to_the_last_installment():
    amounts = installment_amounts(1190, [50, 33.33, 16.67])

    assert amounts == [595, 396.63, 198.37]
    assert round(sum(amounts), 2) == 1190
