"""Core invoice domain models."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Literal

LineStatus = Literal["proposed", "accepted", "pending"]


@dataclass(frozen=True, slots=True)
class InvoiceLine:
    id: str
    user: str
    service: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    confidence: float
    project_reference: str = ""
    status: LineStatus = "proposed"
    comment: str = ""

    def updated(self, **changes: object) -> "InvoiceLine":
        return replace(self, **changes)


@dataclass(frozen=True, slots=True)
class InvoiceAnalysis:
    provider: str
    invoice_number: str
    invoice_date: str
    customer_code: str
    customer_name: str
    taxable_base: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    invoice_total: Decimal
    lines: tuple[InvoiceLine, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)

