from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app"
if str(APP_PATH) not in __import__("sys").path:
    __import__("sys").path.append(str(APP_PATH))

data_module = importlib.import_module("data")
engine = data_module.engine


def _sqlite_tables() -> set[str]:
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(row[0]) for row in rows}


def test_legacy_invoice_revision_table_removed_when_modern_table_exists() -> None:
    tables = _sqlite_tables()
    assert "invoicerevision" in tables
    assert "invoice_revision" not in tables
