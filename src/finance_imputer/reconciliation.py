"""Compare extracted lines with the invoice taxable base."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import InvoiceLine


@dataclass(frozen=True, slots=True)
class Reconciliation:
    line_total: Decimal
    taxable_base: Decimal
    absolute_difference: Decimal
    percentage_difference: Decimal
    tolerance_percentage: Decimal
    matches: bool


def reconcile(
    lines: tuple[InvoiceLine, ...] | list[InvoiceLine],
    taxable_base: Decimal,
    tolerance_percentage: Decimal = Decimal("0.10"),
) -> Reconciliation:
    line_total = sum((line.amount for line in lines), start=Decimal("0"))
    absolute_difference = abs(line_total - taxable_base)
    if taxable_base == 0:
        percentage_difference = Decimal("0") if absolute_difference == 0 else Decimal("100")
    else:
        percentage_difference = absolute_difference / abs(taxable_base) * Decimal("100")
    return Reconciliation(
        line_total=line_total,
        taxable_base=taxable_base,
        absolute_difference=absolute_difference,
        percentage_difference=percentage_difference,
        tolerance_percentage=tolerance_percentage,
        matches=percentage_difference <= tolerance_percentage,
    )

