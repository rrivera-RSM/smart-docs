"""Data contracts shared by the isolated Docling proof of concept."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


DOCLING_ENGINE_NAME = "docling-document-extractor/nuextract-2.0-2b"
RawNumber = str | int | float | Decimal | None


def optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.casefold() in {"null", "none", "n/a", "na"}:
        return None
    return text


class RawInvoiceLine(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str | None = None
    user: str | None = None
    project_reference: str | None = None
    quantity: RawNumber = None
    unit_price: RawNumber = None
    amount: RawNumber = None

    @model_validator(mode="before")
    @classmethod
    def accept_common_aliases(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        if "description" not in payload and "service" in payload:
            payload["description"] = payload["service"]
        for alias in ("project", "reference", "project_ref", "project_code"):
            if "project_reference" not in payload and alias in payload:
                payload["project_reference"] = payload[alias]
        return payload

    @field_validator("description", "user", "project_reference", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str | None:
        return optional_text(value)


class RawInvoiceTax(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tax_type: str | None = None
    rate: RawNumber = None
    taxable_base: RawNumber = None
    amount: RawNumber = None

    @model_validator(mode="before")
    @classmethod
    def accept_common_aliases(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        aliases = {
            "tax_rate": "rate",
            "base": "taxable_base",
            "tax_amount": "amount",
        }
        for alias, canonical in aliases.items():
            if canonical not in payload and alias in payload:
                payload[canonical] = payload[alias]
        return payload

    @field_validator("tax_type", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str | None:
        return optional_text(value)


class RawInvoicePage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    supplier_name: str | None = None
    supplier_tax_id: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    customer_code: str | None = None
    customer_name: str | None = None
    currency: str | None = None
    taxable_base: RawNumber = None
    tax_rate: RawNumber = None
    tax_amount: RawNumber = None
    invoice_total: RawNumber = None
    taxes: list[RawInvoiceTax] = Field(default_factory=list)
    line_items: list[RawInvoiceLine] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def accept_common_aliases(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        aliases = {
            "lines": "line_items",
            "provider": "supplier_name",
            "supplier": "supplier_name",
            "provider_name": "supplier_name",
            "subtotal": "taxable_base",
            "total": "invoice_total",
            "vat_amount": "tax_amount",
        }
        for alias, canonical in aliases.items():
            if canonical not in payload and alias in payload:
                payload[canonical] = payload[alias]
        return payload

    @field_validator(
        "supplier_name",
        "supplier_tax_id",
        "invoice_number",
        "invoice_date",
        "customer_code",
        "customer_name",
        "currency",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value: object) -> str | None:
        return optional_text(value)


@dataclass(frozen=True, slots=True)
class ExtractedPagePayload:
    page_no: int
    extracted_data: Mapping[str, object] | None = None
    raw_text: str = ""
    errors: tuple[str, ...] = ()


class InvoiceDraftLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_no: int = Field(ge=1)
    description: str | None = None
    user: str | None = None
    project_reference: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None
    warnings: tuple[str, ...] = ()


class InvoiceDraftTax(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_no: int = Field(ge=1)
    tax_type: str | None = None
    rate: Decimal | None = None
    taxable_base: Decimal | None = None
    amount: Decimal | None = None


class DraftValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    missing_required_fields: tuple[str, ...]
    line_total: Decimal
    line_total_matches_taxable_base: bool | None
    taxable_base_plus_tax_matches_total: bool | None
    complete_line_count: int = Field(ge=0)
    pending_line_count: int = Field(ge=0)
    ready_for_mapping: bool


class InvoiceDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    engine: str = DOCLING_ENGINE_NAME
    extraction_status: str
    pages_processed: int = Field(ge=0)
    supplier_name: str | None = None
    supplier_tax_id: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    customer_code: str | None = None
    customer_name: str | None = None
    currency: str | None = None
    taxable_base: Decimal | None = None
    tax_rate: Decimal | None = None
    tax_amount: Decimal | None = None
    invoice_total: Decimal | None = None
    taxes: tuple[InvoiceDraftTax, ...] = ()
    lines: tuple[InvoiceDraftLine, ...] = ()
    validation: DraftValidation
    warnings: tuple[str, ...] = ()


class DoclingPocError(RuntimeError):
    """Base error raised by the isolated Docling proof of concept."""


class DoclingPocUnavailableError(DoclingPocError):
    """Raised when the optional Docling dependency is not installed."""


class DoclingPocExtractionError(DoclingPocError):
    """Raised when Docling cannot process a supplied document."""
