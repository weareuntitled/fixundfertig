from __future__ import annotations

from typing import Any, Protocol


class InvoiceRenderer(Protocol):
    def render(self, invoice: Any, template_id: str | None) -> bytes:
        ...
