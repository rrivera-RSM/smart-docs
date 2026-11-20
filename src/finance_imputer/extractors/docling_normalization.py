"""Deterministic normalization of page-level Docling output."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation

from .docling_models import (
    DraftValidation,
    ExtractedPagePayload,
    InvoiceDraft,
    InvoiceDraftLine,
    InvoiceDraftTax,
    RawInvoicePage,
    RawNumber,
    optional_text,
)


DEFAULT_TOLERANCE_PERCENTAGE = Decimal("0.10")
_NUMBER_CLEANUP_RE = re.compile(r"[^0-9,.'()\-]")


def parse_decimal(value: RawNumber) -> Decimal | None:
    """Parse common European and international invoice number formats."""
    text = optional_text(value)
    if text is None:
        return None

    text = text.replace("\u2212", "-").replace("\u00a0", "")
    negative = text.startswith("(") and text.endswith(")")
    normalized = _NUMBER_CLEANUP_RE.sub("", text).replace("'", "")
    normalized = normalized.strip("()")

    if "," in normalized and "." in normalized:
        decimal_separator = (
            "," if normalized.rfind(",") > normalized.rfind(".") else "."
        )
        thousands_separator = "." if decimal_separator == "," else ","
        normalized = normalized.replace(thousands_separator, "")
        normalized = normalized.replace(decimal_separator, ".")
    elif "," in normalized:
        normalized = _normalize_single_separator(normalized, ",")
    elif "." in normalized:
        normalized = _normalize_single_separator(normalized, ".")

    if negative and not normalized.startswith("-"):
        normalized = f"-{normalized}"
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"Valor numérico no válido: {text}") from exc


def _normalize_single_separator(value: str, separator: str) -> str:
    parts = value.split(separator)
    if len(parts) == 2:
        integer, fraction = parts
        if len(fraction) == 3 and integer.lstrip("-") not in {"", "0"}:
            return f"{integer}{fraction}"
        return f"{integer}.{fraction}"

    fraction = parts[-1]
    integer = "".join(parts[:-1])
    if 1 <= len(fraction) <= 4:
        return f"{integer}.{fraction}"
    return "".join(parts)


def _safe_decimal(
    value: RawNumber,
    label: str,
    warnings: list[str],
) -> Decimal | None:
    try:
        return parse_decimal(value)
    except ValueError as exc:
        warnings.append(f"{label}: {exc}")
        return None


def _matches(
    actual: Decimal | None,
    expected: Decimal | None,
    tolerance_percentage: Decimal,
) -> bool | None:
    if actual is None or expected is None:
        return None
    difference = abs(actual - expected)
    if expected == 0:
        return difference == 0
    percentage = difference / abs(expected) * Decimal("100")
    return percentage <= tolerance_percentage


def _payload_from_page(
    page: ExtractedPagePayload,
    warnings: list[str],
) -> RawInvoicePage:
    payload: Mapping[str, object] | None = page.extracted_data
    if payload is None and page.raw_text:
        try:
            decoded = json.loads(page.raw_text)
            if isinstance(decoded, Mapping):
                payload = decoded
        except json.JSONDecodeError:
            warnings.append(
                f"Página {page.page_no}: Docling no devolvió JSON válido."
            )
    if payload is None:
        return RawInvoicePage()

    try:
        return RawInvoicePage.model_validate(payload)
    except Exception as exc:
        warnings.append(
            f"Página {page.page_no}: respuesta incompatible con el esquema ({exc})."
        )
        return RawInvoicePage()


def _choose_text_header(
    pages: list[tuple[int, RawInvoicePage]],
    field_name: str,
    warnings: list[str],
) -> str | None:
    candidates: list[tuple[int, str]] = []
    for page_no, page in pages:
        value = optional_text(getattr(page, field_name))
        if value is not None:
            candidates.append((page_no, value))
    if not candidates:
        return None

    distinct = {value.casefold() for _, value in candidates}
    if len(distinct) > 1:
        locations = ", ".join(
            f"p.{page_no}: {value}" for page_no, value in candidates
        )
        warnings.append(
            f"Valores contradictorios para {field_name}: {locations}."
        )
    return candidates[0][1]


def _choose_decimal_header(
    pages: list[tuple[int, RawInvoicePage]],
    field_name: str,
    warnings: list[str],
) -> Decimal | None:
    candidates: list[tuple[int, Decimal]] = []
    for page_no, page in pages:
        raw = getattr(page, field_name)
        value = _safe_decimal(
            raw,
            f"Página {page_no}, {field_name}",
            warnings,
        )
        if value is not None:
            candidates.append((page_no, value))
    if not candidates:
        return None

    if len({value for _, value in candidates}) > 1:
        locations = ", ".join(
            f"p.{page_no}: {value}" for page_no, value in candidates
        )
        warnings.append(
            f"Valores contradictorios para {field_name}: {locations}."
        )
    return candidates[0][1]


def _normalize_lines(
    pages: list[tuple[int, RawInvoicePage]],
    tolerance_percentage: Decimal,
) -> list[InvoiceDraftLine]:
    lines: list[InvoiceDraftLine] = []
    for page_no, page in pages:
        for index, raw_line in enumerate(page.line_items, start=1):
            warnings: list[str] = []
            quantity = _safe_decimal(
                raw_line.quantity,
                f"Página {page_no}, línea {index}, cantidad",
                warnings,
            )
            unit_price = _safe_decimal(
                raw_line.unit_price,
                f"Página {page_no}, línea {index}, precio unitario",
                warnings,
            )
            amount = _safe_decimal(
                raw_line.amount,
                f"Página {page_no}, línea {index}, importe",
                warnings,
            )
            if (
                quantity is not None
                and unit_price is not None
                and amount is not None
                and not _matches(
                    quantity * unit_price,
                    amount,
                    tolerance_percentage,
                )
            ):
                warnings.append(
                    "Cantidad por precio unitario no coincide con el importe."
                )
            if not raw_line.description:
                warnings.append("Falta la descripción de la línea.")
            if quantity is None:
                warnings.append("Falta la cantidad de la línea.")
            if unit_price is None:
                warnings.append("Falta el precio unitario de la línea.")
            if amount is None:
                warnings.append("Falta el importe de la línea.")

            lines.append(
                InvoiceDraftLine(
                    page_no=page_no,
                    description=raw_line.description,
                    user=raw_line.user,
                    project_reference=raw_line.project_reference,
                    quantity=quantity,
                    unit_price=unit_price,
                    amount=amount,
                    warnings=tuple(warnings),
                )
            )
    return lines


def _normalize_taxes(
    pages: list[tuple[int, RawInvoicePage]],
    warnings: list[str],
) -> list[InvoiceDraftTax]:
    taxes: list[InvoiceDraftTax] = []
    seen: set[
        tuple[str | None, Decimal | None, Decimal | None, Decimal | None]
    ] = set()

    for page_no, page in pages:
        for index, raw_tax in enumerate(page.taxes, start=1):
            rate = _safe_decimal(
                raw_tax.rate,
                f"Página {page_no}, impuesto {index}, tipo",
                warnings,
            )
            base = _safe_decimal(
                raw_tax.taxable_base,
                f"Página {page_no}, impuesto {index}, base",
                warnings,
            )
            amount = _safe_decimal(
                raw_tax.amount,
                f"Página {page_no}, impuesto {index}, importe",
                warnings,
            )
            key = (raw_tax.tax_type, rate, base, amount)
            if key == (None, None, None, None) or key in seen:
                continue

            seen.add(key)
            taxes.append(
                InvoiceDraftTax(
                    page_no=page_no,
                    tax_type=raw_tax.tax_type,
                    rate=rate,
                    taxable_base=base,
                    amount=amount,
                )
            )
    return taxes


def assemble_invoice_draft(
    pages: Iterable[ExtractedPagePayload],
    *,
    source_name: str,
    extraction_status: str = "success",
    global_errors: Iterable[str] = (),
    tolerance_percentage: Decimal = DEFAULT_TOLERANCE_PERCENTAGE,
) -> InvoiceDraft:
    """Merge page payloads and compute deterministic validation results."""
    ordered_pages = sorted(pages, key=lambda item: item.page_no)
    warnings = [f"Docling: {message}" for message in global_errors if message]
    parsed_pages: list[tuple[int, RawInvoicePage]] = []

    for page in ordered_pages:
        warnings.extend(
            f"Página {page.page_no}: {message}"
            for message in page.errors
            if message
        )
        parsed_pages.append(
            (page.page_no, _payload_from_page(page, warnings))
        )

    supplier_name = _choose_text_header(
        parsed_pages,
        "supplier_name",
        warnings,
    )
    supplier_tax_id = _choose_text_header(
        parsed_pages,
        "supplier_tax_id",
        warnings,
    )
    invoice_number = _choose_text_header(
        parsed_pages,
        "invoice_number",
        warnings,
    )
    invoice_date = _choose_text_header(
        parsed_pages,
        "invoice_date",
        warnings,
    )
    customer_code = _choose_text_header(
        parsed_pages,
        "customer_code",
        warnings,
    )
    customer_name = _choose_text_header(
        parsed_pages,
        "customer_name",
        warnings,
    )
    currency = _choose_text_header(parsed_pages, "currency", warnings)
    if currency is not None:
        currency = currency.upper()

    taxable_base = _choose_decimal_header(
        parsed_pages,
        "taxable_base",
        warnings,
    )
    tax_rate = _choose_decimal_header(parsed_pages, "tax_rate", warnings)
    tax_amount = _choose_decimal_header(
        parsed_pages,
        "tax_amount",
        warnings,
    )
    invoice_total = _choose_decimal_header(
        parsed_pages,
        "invoice_total",
        warnings,
    )

    lines = _normalize_lines(parsed_pages, tolerance_percentage)
    taxes = _normalize_taxes(parsed_pages, warnings)

    if tax_amount is None:
        tax_values = [tax.amount for tax in taxes if tax.amount is not None]
        if tax_values:
            tax_amount = sum(tax_values, start=Decimal("0"))
    if taxable_base is None:
        base_values = [
            tax.taxable_base
            for tax in taxes
            if tax.taxable_base is not None
        ]
        if base_values:
            taxable_base = sum(base_values, start=Decimal("0"))
    if tax_rate is None and len(taxes) == 1:
        tax_rate = taxes[0].rate

    line_total = sum(
        (line.amount for line in lines if line.amount is not None),
        start=Decimal("0"),
    )
    complete_line_count = sum(
        line.description is not None
        and line.quantity is not None
        and line.unit_price is not None
        and line.amount is not None
        for line in lines
    )
    pending_line_count = len(lines) - complete_line_count

    required_values = {
        "supplier_name": supplier_name,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "customer_code": customer_code,
        "customer_name": customer_name,
        "taxable_base": taxable_base,
        "tax_rate": tax_rate,
        "tax_amount": tax_amount,
        "invoice_total": invoice_total,
    }
    missing = tuple(
        name for name, value in required_values.items() if value is None
    )
    if not lines:
        missing = (*missing, "lines")

    line_match = (
        _matches(line_total, taxable_base, tolerance_percentage)
        if lines
        else None
    )
    total_match = _matches(
        (
            taxable_base + tax_amount
            if taxable_base is not None and tax_amount is not None
            else None
        ),
        invoice_total,
        tolerance_percentage,
    )
    if line_match is False:
        warnings.append(
            "La suma de líneas no coincide con la base imponible."
        )
    if total_match is False:
        warnings.append(
            "La base imponible más impuestos no coincide con el total."
        )

    has_line_warnings = any(line.warnings for line in lines)
    validation = DraftValidation(
        missing_required_fields=missing,
        line_total=line_total,
        line_total_matches_taxable_base=line_match,
        taxable_base_plus_tax_matches_total=total_match,
        complete_line_count=complete_line_count,
        pending_line_count=pending_line_count,
        ready_for_mapping=(
            not missing
            and pending_line_count == 0
            and line_match is True
            and total_match is True
            and extraction_status.casefold() == "success"
            and not warnings
            and not has_line_warnings
        ),
    )
    return InvoiceDraft(
        source_name=source_name,
        extraction_status=extraction_status,
        pages_processed=len(ordered_pages),
        supplier_name=supplier_name,
        supplier_tax_id=supplier_tax_id,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        customer_code=customer_code,
        customer_name=customer_name,
        currency=currency,
        taxable_base=taxable_base,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        invoice_total=invoice_total,
        taxes=tuple(taxes),
        lines=tuple(lines),
        validation=validation,
        warnings=tuple(warnings),
    )
