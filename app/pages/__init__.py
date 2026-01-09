from __future__ import annotations
from ._shared import *

from .customer_detail import render_customer_detail
from .customer_new import render_customer_new
from .customers import render_customers
from .dashboard import render_dashboard
from .documents import render_documents
from .expenses import render_expenses
from .exports import render_exports
from .invoice_create import render_invoice_create
from .invoice_detail import render_invoice_detail
from .invoices import render_invoices
from .ledger import render_ledger
from .settings import render_settings

# Import routes for side effects. Registers @ui.page decorators
from . import auth
