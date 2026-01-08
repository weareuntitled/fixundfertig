import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.invoice_calculations import (  # noqa: E402
    build_invoice_preview_html,
    calculate_invoice_totals,
)


class InvoiceCalculationsTests(unittest.TestCase):
    def test_vat_off_gross_equals_net(self) -> None:
        items = [
            {"description": "Service", "quantity": 2, "unit_price": 50, "tax_rate": 19},
        ]
        totals = calculate_invoice_totals(items, ust_enabled=False)
        self.assertEqual(totals["vat"], 0.0)
        self.assertEqual(totals["gross"], totals["net"])

    def test_vat_on_rounding(self) -> None:
        items = [
            {"description": "Service", "quantity": 1, "unit_price": 9.99, "tax_rate": 19},
        ]
        totals = calculate_invoice_totals(items, ust_enabled=True)
        self.assertAlmostEqual(totals["net"], 9.99, places=2)
        self.assertAlmostEqual(totals["vat"], 1.90, places=2)
        self.assertAlmostEqual(totals["gross"], 11.89, places=2)

    def test_multiple_items_sum(self) -> None:
        items = [
            {"description": "Item A", "quantity": 2, "unit_price": 10, "tax_rate": 19},
            {"description": "Item B", "quantity": 1, "unit_price": 5, "tax_rate": 7},
        ]
        totals = calculate_invoice_totals(items, ust_enabled=True)
        self.assertAlmostEqual(totals["net"], 25.00, places=2)
        self.assertAlmostEqual(totals["vat"], 4.15, places=2)
        self.assertAlmostEqual(totals["gross"], 29.15, places=2)

    def test_empty_items_and_zero_quantity(self) -> None:
        totals = calculate_invoice_totals([], ust_enabled=True)
        self.assertEqual(totals["net"], 0.0)
        self.assertEqual(totals["vat"], 0.0)
        self.assertEqual(totals["gross"], 0.0)

        items = [
            {"description": "Unused", "quantity": 0, "unit_price": 100, "tax_rate": 19},
        ]
        totals = calculate_invoice_totals(items, ust_enabled=True)
        self.assertEqual(totals["net"], 0.0)
        self.assertEqual(totals["vat"], 0.0)
        self.assertEqual(totals["gross"], 0.0)

    def test_negative_values_allowed(self) -> None:
        items = [
            {"description": "Refund", "quantity": -1, "unit_price": 10, "tax_rate": 19},
        ]
        totals = calculate_invoice_totals(items, ust_enabled=True, allow_negative=True)
        self.assertAlmostEqual(totals["net"], -10.00, places=2)
        self.assertAlmostEqual(totals["vat"], -1.90, places=2)
        self.assertAlmostEqual(totals["gross"], -11.90, places=2)

    def test_build_invoice_preview_html_contains_meta(self) -> None:
        totals = calculate_invoice_totals(
            [{"description": "Service", "quantity": 1, "unit_price": 100, "tax_rate": 19}],
            ust_enabled=True,
        )
        html = build_invoice_preview_html("INV-42", "2024-01-10", totals)
        self.assertTrue(html)
        self.assertIn("INV-42", html)
        self.assertIn("2024-01-10", html)
        self.assertIn("119.00", html)


if __name__ == "__main__":
    unittest.main()
