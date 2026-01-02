from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class Address(BaseModel):
    name: str
    street: str
    zip: str
    city: str
    country: str = "DE"


class LineItem(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal = Decimal("19.0")

    @property
    def net_total(self) -> Decimal:
        return self.quantity * self.unit_price

    @property
    def vat_amount(self) -> Decimal:
        return self.net_total * self.tax_rate / Decimal("100")


class Invoice(BaseModel):
    id: str
    invoice_number: Optional[str] = None
    date: date
    delivery_date: date
    sender: Address
    recipient: Address
    items: List[LineItem]
