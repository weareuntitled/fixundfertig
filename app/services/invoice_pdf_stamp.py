"""A stamp in the PDF's metadata naming the data its amount was drawn from.

The stored PDF of an invoice is a snapshot. When positions change behind the
app's back (a direct database edit, a script), the snapshot keeps the old
amount while the mail, built live, shows the new one. The stamp lets the send
path see that the snapshot no longer matches the invoice.

The stamp sits in the PDF's keywords as two ASCII tokens:
``ff-stamp:<hash>`` over number, positions and payable amount, and
``ff-amount:<amount>`` with the payable amount the PDF shows.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable

from .invoice_pdf_layout import get_attr, safe_float, safe_str

_STAMP = re.compile(rb"ff-stamp:([0-9a-f]{32})")
_AMOUNT = re.compile(rb"ff-amount:(-?\d+\.\d{2})")


def stamp(nr, items: Iterable, payable: float) -> str:
    """Keywords for a PDF drawn from these positions with this payable amount."""
    positions = [
        [
            safe_str(get_attr(item, "description", "desc", default="")).strip(),
            f"{safe_float(get_attr(item, 'quantity', 'qty', default=0)):.4f}",
            f"{safe_float(get_attr(item, 'unit_price', 'price', default=0)):.4f}",
        ]
        for item in items
    ]
    amount = f"{round(float(payable or 0), 2):.2f}"
    digest = hashlib.sha256(
        json.dumps([safe_str(nr), positions, amount], ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:32]
    return f"ff-stamp:{digest} ff-amount:{amount}"


def invoice_stamp(invoice) -> str:
    """The stamp a PDF must carry to show what the stored invoice says it costs."""
    return stamp(
        get_attr(invoice, "nr", default=""),
        get_attr(invoice, "items", default=None) or [],
        safe_float(get_attr(invoice, "total_brutto", default=0)),
    )


def pdf_matches_invoice(pdf_bytes: bytes | None, invoice) -> bool:
    """True when the PDF was drawn from the invoice's current positions and total.

    A PDF without a stamp (stored before it existed) cannot vouch for itself.
    """
    if not pdf_bytes:
        return False
    found = _STAMP.search(bytes(pdf_bytes))
    expected = invoice_stamp(invoice).split()[0].removeprefix("ff-stamp:")
    return found is not None and found.group(1).decode("ascii") == expected


def pdf_amount(pdf_bytes: bytes | None) -> float | None:
    """The payable amount a stamped PDF shows, or None without a stamp."""
    found = _AMOUNT.search(bytes(pdf_bytes or b""))
    return float(found.group(1)) if found else None
