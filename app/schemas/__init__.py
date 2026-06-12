# =========================
# APP/SCHEMAS/__INIT__.PY
# =========================
"""
Pydantic v2 Schemas (Request/Response Models).

Each domain module in `app/schemas/` defines Pydantic BaseModels
that the API layer (`app/api/`) uses for validation and OpenAPI generation.

Source of Truth: Diese Schemas. Pydantic-Output wird in OpenAPI exportiert;
der React-Client mirrort sie 1:1 mit Zod (siehe docs/react_handoff.md §3.3).

Convention:
- `*Create` — input for POST (no id, no server-generated fields)
- `*Update` — input for PUT/PATCH (all fields optional)
- `*Read` — output (includes id and server fields)
- `*Public` — minimal safe representation for auth responses

Wächst inkrementell pro Domain. Stand 2026-06-10: customer, auth, invoice, expense, invite.
"""

from .auth import (
    LoginRequest,
    LoginResponse,
    UserPublic,
)
from .customer import (
    CustomerCreate,
    CustomerRead,
    CustomerUpdate,
)
from .invoice import (
    InvoiceDraft,
    InvoiceItem,
    InvoiceRead,
    InvoiceStatus,
    InvoiceStatusUpdate,
)
from .expense import (
    ExpenseCreate,
    ExpenseRead,
)
from .invite import (
    InviteCreate,
    InviteRead,
)

__all__ = [
    "LoginRequest",
    "LoginResponse",
    "UserPublic",
    "CustomerCreate",
    "CustomerUpdate",
    "CustomerRead",
    "InvoiceItem",
    "InvoiceDraft",
    "InvoiceRead",
    "InvoiceStatus",
    "InvoiceStatusUpdate",
    "ExpenseCreate",
    "ExpenseRead",
    "InviteCreate",
    "InviteRead",
]

