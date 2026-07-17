"""Backfill legacy flag for invoices that had items extracted from PDFs."""
import sys
sys.path.insert(0, '/app')
from db import engine

with engine.begin() as conn:
    # Mark invoices with stored PDFs but whose items were auto-extracted
    # = all invoices where pdf_storage is not empty (imported invoices)
    result = conn.exec_driver_sql(
        "UPDATE invoice SET legacy = 1 WHERE pdf_storage IS NOT NULL AND pdf_storage != ''"
    )
    print(f"Marked {result.rowcount} invoices as legacy")

    # Also mark any invoice with zero original items as legacy
    result2 = conn.exec_driver_sql(
        "UPDATE invoice SET legacy = 1 WHERE id NOT IN (SELECT DISTINCT invoice_id FROM invoiceitem)"
    )
    print(f"Marked {result2.rowcount} itemless invoices as legacy (already counted above if both match)")

    # Verify
    count = conn.exec_driver_sql("SELECT COUNT(*) FROM invoice WHERE legacy = 1").scalar()
    total = conn.exec_driver_sql("SELECT COUNT(*) FROM invoice").scalar()
    print(f"\nDone: {count}/{total} invoices flagged as legacy")
