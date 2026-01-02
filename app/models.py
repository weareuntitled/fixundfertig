from dataclasses import dataclass, field
from typing import List


@dataclass
class Address:
    name: str
    street: str
    postal_code: str
    city: str
    country: str = ""
    email: str = ""


@dataclass
class LineItem:
    description: str
    quantity: float
    unit_price: float

    @property
    def total(self) -> float:
        return self.quantity * self.unit_price


@dataclass
class Invoice:
    number: str
    date: str
    due_date: str
    issuer: Address
    recipient: Address
    title: str = "Rechnung"
    line_items: List[LineItem] = field(default_factory=list)
    notes: str = ""
    currency: str = "€"
    tax_rate: float = 0.0

    @property
    def subtotal(self) -> float:
        return sum(item.total for item in self.line_items)

    @property
    def tax_amount(self) -> float:
        return self.subtotal * self.tax_rate

    @property
    def total(self) -> float:
        return self.subtotal + self.tax_amount
