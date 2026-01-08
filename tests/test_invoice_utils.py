from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

module_path = Path(__file__).resolve().parents[1] / "app" / "pages" / "invoice_utils.py"
spec = spec_from_file_location("invoice_utils", module_path)
invoice_utils = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(invoice_utils)

build_invoice_preview_html = invoice_utils.build_invoice_preview_html
compute_invoice_totals = invoice_utils.compute_invoice_totals


def test_compute_invoice_totals_vat_off() -> None:
    items = [{"quantity": 2, "unit_price": 10.0}]
    net, vat, gross = compute_invoice_totals(items, vat_enabled=False, vat_rate=19)
    assert net == 20.0
    assert vat == 0.0
    assert gross == 20.0


def test_compute_invoice_totals_vat_on_rounding() -> None:
    items = [{"quantity": 1, "unit_price": 100.0}]
    net, vat, gross = compute_invoice_totals(items, vat_enabled=True, vat_rate=19)
    assert net == 100.0
    assert vat == 19.0
    assert gross == 119.0


def test_compute_invoice_totals_multiple_items() -> None:
    items = [
        {"quantity": 2, "unit_price": 10.0},
        {"quantity": 3, "unit_price": 5.5},
    ]
    net, vat, gross = compute_invoice_totals(items, vat_enabled=True, vat_rate=7)
    assert net == 36.5
    assert vat == 2.56
    assert gross == 39.06


def test_compute_invoice_totals_edge_cases() -> None:
    items = [
        {"quantity": 0, "unit_price": 100.0},
        {"quantity": -1, "unit_price": 50.0},
    ]
    net, vat, gross = compute_invoice_totals(items, vat_enabled=True, vat_rate=19)
    assert net == -50.0
    assert vat == -9.5
    assert gross == -59.5


def test_compute_invoice_totals_empty() -> None:
    net, vat, gross = compute_invoice_totals([], vat_enabled=True, vat_rate=19)
    assert net == 0.0
    assert vat == 0.0
    assert gross == 0.0


def test_build_invoice_preview_html_contains_fields() -> None:
    html = build_invoice_preview_html(
        {
            "invoice_number": "INV-2024-001",
            "invoice_date": "2024-01-01",
            "totals": {"net": 10.0, "vat": 1.9, "gross": 11.9},
        }
    )
    assert "INV-2024-001" in html
    assert "2024-01-01" in html
    assert "10.0" in html
    assert "1.9" in html
    assert "11.9" in html
