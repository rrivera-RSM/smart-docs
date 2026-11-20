"""Translate domain objects into stable JSON response payloads."""

from __future__ import annotations

from decimal import Decimal

from finance_imputer.models import InvoiceAnalysis, InvoiceLine
from finance_imputer.provider_profiles import ProviderDefinition
from finance_imputer.reconciliation import reconcile


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


def _serialize_line(line: InvoiceLine) -> dict[str, object]:
    return {
        "id": line.id,
        "user": line.user,
        "project_reference": line.project_reference,
        "service": line.service,
        "quantity": float(line.quantity),
        "unit_price": float(line.unit_price),
        "amount": _money(line.amount),
        "confidence": line.confidence,
        "status": line.status,
        "comment": line.comment,
    }


def serialize_analysis(
    job_id: str,
    analysis: InvoiceAnalysis,
    *,
    tolerance_percentage: Decimal,
) -> dict[str, object]:
    reconciliation = reconcile(
        list(analysis.lines),
        analysis.taxable_base,
        tolerance_percentage=tolerance_percentage,
    )
    return {
        "job_id": job_id,
        "provider": analysis.provider,
        "invoice_number": analysis.invoice_number,
        "invoice_date": analysis.invoice_date,
        "customer_code": analysis.customer_code,
        "customer_name": analysis.customer_name,
        "taxable_base": _money(analysis.taxable_base),
        "tax_rate": float(analysis.tax_rate),
        "tax_amount": _money(analysis.tax_amount),
        "invoice_total": _money(analysis.invoice_total),
        "lines": [_serialize_line(line) for line in analysis.lines],
        "warnings": list(analysis.warnings),
        "reconciliation": {
            "line_total": _money(reconciliation.line_total),
            "taxable_base": _money(reconciliation.taxable_base),
            "absolute_difference": _money(reconciliation.absolute_difference),
            "percentage_difference": float(reconciliation.percentage_difference),
            "tolerance_percentage": float(reconciliation.tolerance_percentage),
            "matches": reconciliation.matches,
        },
    }


def serialize_provider(definition: ProviderDefinition) -> dict[str, object]:
    profile = definition.profile
    return {
        "id": profile.id,
        "name": profile.name,
        "description": profile.description,
        "mode": profile.lines.mode,
        "built_in": definition.built_in,
        "detection_terms": profile.detection.all_terms,
    }
