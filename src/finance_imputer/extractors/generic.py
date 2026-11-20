"""Profile-driven extraction for digital invoice PDFs."""

from __future__ import annotations

import io
import re
from decimal import Decimal, InvalidOperation

import pdfplumber

from finance_imputer.models import InvoiceAnalysis, InvoiceLine
from finance_imputer.provider_profiles import ProviderProfile, RegexCapture


def decimal_value(value: str) -> Decimal:
    normalized = value.strip().replace(" ", "")
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"Importe no válido: {value}") from exc


def extract_pages(content: bytes) -> list[str]:
    try:
        with pdfplumber.open(io.BytesIO(content)) as document:
            return [page.extract_text() or "" for page in document.pages]
    except Exception as exc:
        raise ValueError("No se ha podido extraer el texto del PDF.") from exc


def profile_matches(pages: list[str], profile: ProviderProfile) -> bool:
    text = "\n".join(pages[: profile.detection.page_limit]).casefold()
    return all(term.casefold() in text for term in profile.detection.all_terms)


def _capture(text: str, capture: RegexCapture | None, label: str) -> str:
    if capture is None:
        return ""
    match = re.search(capture.pattern, text, re.IGNORECASE)
    if not match:
        if capture.required:
            raise ValueError(f"No se ha encontrado {label} en la factura.")
        return ""
    group: str | int = int(capture.group) if capture.group.isdigit() else capture.group
    value = match.group(group).strip()
    if capture.join_following_line:
        following = text[match.end() :].lstrip("\r\n").splitlines()
        if following and following[0].strip():
            value = f"{value} {following[0].strip()}"
    return value


def _page(pages: list[str], index: int, label: str) -> str:
    if index >= len(pages):
        raise ValueError(f"El PDF no contiene la página configurada para {label}.")
    return pages[index]


def _optional_group(match: re.Match[str], name: str) -> str:
    value = match.groupdict().get(name)
    return value.strip() if value else ""


def _grouped_lines(text: str, profile: ProviderProfile) -> tuple[InvoiceLine, ...]:
    config = profile.lines
    user_regex = re.compile(config.user_pattern or "", re.IGNORECASE)
    summary_regex = re.compile(config.summary_pattern or "", re.IGNORECASE)
    detail_regex = re.compile(config.detail_pattern or "", re.IGNORECASE)
    project_reference_regex = (
        re.compile(config.project_reference_pattern, re.IGNORECASE)
        if config.project_reference_pattern
        else None
    )
    allowed_services = {name.casefold() for name in config.service_names}

    current_user = ""
    current_project_reference = ""
    pending_service: tuple[str, Decimal, Decimal, str] | None = None
    result: list[InvoiceLine] = []
    for row in (line.strip() for line in text.splitlines() if line.strip()):
        if project_reference_regex:
            project_reference_match = project_reference_regex.search(row)
            if project_reference_match:
                current_project_reference = _optional_group(
                    project_reference_match,
                    "project_reference",
                )

        user_match = user_regex.search(row)
        if user_match:
            current_user = user_match.group("user").strip()
            pending_service = None
            continue

        summary_match = summary_regex.search(row)
        if summary_match:
            service = summary_match.group("service").strip()
            if not allowed_services or service.casefold() in allowed_services:
                pending_service = (
                    service,
                    decimal_value(summary_match.group("quantity")),
                    decimal_value(summary_match.group("amount")),
                    _optional_group(summary_match, "project_reference")
                    or current_project_reference,
                )
                continue

        detail_match = detail_regex.search(row)
        if detail_match and pending_service and current_user:
            service, summary_quantity, summary_amount, project_reference = pending_service
            quantity = decimal_value(detail_match.group("quantity"))
            amount = decimal_value(detail_match.group("amount"))
            confidence = 0.99
            comment = ""
            if quantity != summary_quantity or amount != summary_amount:
                confidence = 0.75
                comment = "El detalle no coincide con el resumen del servicio."
            result.append(
                InvoiceLine(
                    id=f"line-{len(result) + 1}",
                    user=current_user,
                    service=service,
                    quantity=quantity,
                    unit_price=decimal_value(detail_match.group("unit_price")),
                    amount=amount,
                    confidence=confidence,
                    project_reference=(
                        _optional_group(detail_match, "project_reference")
                        or project_reference
                    ),
                    comment=comment,
                )
            )
            pending_service = None
    return tuple(result)


def _flat_lines(text: str, profile: ProviderProfile) -> tuple[InvoiceLine, ...]:
    row_regex = re.compile(profile.lines.row_pattern or "", re.IGNORECASE)
    project_reference_regex = (
        re.compile(profile.lines.project_reference_pattern, re.IGNORECASE)
        if profile.lines.project_reference_pattern
        else None
    )
    current_project_reference = ""
    result: list[InvoiceLine] = []
    for row in (line.strip() for line in text.splitlines() if line.strip()):
        if project_reference_regex:
            project_reference_match = project_reference_regex.search(row)
            if project_reference_match:
                current_project_reference = _optional_group(
                    project_reference_match,
                    "project_reference",
                )
        match = row_regex.search(row)
        if not match:
            continue
        groups = match.groupdict()
        result.append(
            InvoiceLine(
                id=f"line-{len(result) + 1}",
                user=(groups.get("user") or "").strip(),
                service=groups["service"].strip(),
                quantity=decimal_value(groups["quantity"]),
                unit_price=decimal_value(groups["unit_price"]),
                amount=decimal_value(groups["amount"]),
                confidence=0.95,
                project_reference=(groups.get("project_reference") or "").strip()
                or current_project_reference,
            )
        )
    return tuple(result)


def extract_with_profile(pages: list[str], profile: ProviderProfile) -> InvoiceAnalysis:
    header_text = _page(pages, profile.header.page, "la cabecera")
    detail_text = _page(pages, profile.lines.page, "las líneas")
    lines = (
        _grouped_lines(detail_text, profile)
        if profile.lines.mode == "grouped_detail"
        else _flat_lines(detail_text, profile)
    )
    if not lines:
        raise ValueError(
            f"El perfil de {profile.name} no ha encontrado ninguna línea imputable."
        )

    taxable_base = decimal_value(
        _capture(header_text, profile.header.taxable_base, "la base imponible")
    )
    line_total = sum((line.amount for line in lines), start=Decimal("0"))
    warnings: list[str] = []
    if line_total != taxable_base:
        warnings.append("La suma extraída no coincide exactamente con la base imponible.")

    tax_rate = _capture(header_text, profile.header.tax_rate, "el tipo de IVA")
    tax_amount = _capture(header_text, profile.header.tax_amount, "el importe de IVA")
    return InvoiceAnalysis(
        provider=profile.name,
        invoice_number=_capture(
            header_text, profile.header.invoice_number, "el número de factura"
        ),
        invoice_date=_capture(header_text, profile.header.invoice_date, "la fecha"),
        customer_code=_capture(
            header_text, profile.header.customer_code, "el código de cliente"
        ),
        customer_name=_capture(
            header_text, profile.header.customer_name, "el nombre del cliente"
        ),
        taxable_base=taxable_base,
        tax_rate=decimal_value(tax_rate) if tax_rate else Decimal("0"),
        tax_amount=decimal_value(tax_amount) if tax_amount else Decimal("0"),
        invoice_total=decimal_value(
            _capture(header_text, profile.header.invoice_total, "el total de la factura")
        ),
        lines=lines,
        warnings=tuple(warnings),
    )
