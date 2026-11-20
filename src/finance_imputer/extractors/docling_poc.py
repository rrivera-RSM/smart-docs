"""Optional Docling adapter used only by the local extraction PoC."""

from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import Any

from .docling_models import (
    DoclingPocError,
    DoclingPocExtractionError,
    DoclingPocUnavailableError,
    ExtractedPagePayload,
    InvoiceDraft,
)
from .docling_normalization import (
    DEFAULT_TOLERANCE_PERCENTAGE,
    assemble_invoice_draft,
    parse_decimal,
)


DEFAULT_MAX_FILE_BYTES = 15 * 1024 * 1024
DEFAULT_MAX_PAGES = 10
DEFAULT_TIMEOUT_SECONDS = 120.0

# NuExtract handles an explicit type template reliably, including nested arrays.
INVOICE_EXTRACTION_TEMPLATE: dict[str, object] = {
    "supplier_name": "verbatim-string",
    "supplier_tax_id": "verbatim-string",
    "invoice_number": "verbatim-string",
    "invoice_date": "verbatim-string",
    "customer_code": "verbatim-string",
    "customer_name": "verbatim-string",
    "currency": "verbatim-string",
    "taxable_base": "verbatim-string",
    "tax_rate": "verbatim-string",
    "tax_amount": "verbatim-string",
    "invoice_total": "verbatim-string",
    "taxes": [
        {
            "tax_type": "verbatim-string",
            "rate": "verbatim-string",
            "taxable_base": "verbatim-string",
            "amount": "verbatim-string",
        }
    ],
    "line_items": [
        {
            "description": "verbatim-string",
            "user": "verbatim-string",
            "project_reference": "verbatim-string",
            "quantity": "verbatim-string",
            "unit_price": "verbatim-string",
            "amount": "verbatim-string",
        }
    ],
}

__all__ = [
    "DEFAULT_MAX_FILE_BYTES",
    "DEFAULT_MAX_PAGES",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_TOLERANCE_PERCENTAGE",
    "DoclingPocError",
    "DoclingPocExtractionError",
    "DoclingPocExtractor",
    "DoclingPocUnavailableError",
    "ExtractedPagePayload",
    "InvoiceDraft",
    "assemble_invoice_draft",
    "parse_decimal",
]


def _error_text(error: object) -> str:
    message = getattr(error, "error_message", None)
    return str(message if message is not None else error)


def _mapping_from_extracted_data(
    value: object,
) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, Mapping) else None
    return None


class DoclingPocExtractor:
    """Run Docling locally without registering it in the production API."""

    def __init__(
        self,
        *,
        device: str = "auto",
        max_pages: int = DEFAULT_MAX_PAGES,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if max_pages < 1:
            raise ValueError("max_pages debe ser mayor que cero.")
        if max_file_bytes < 1:
            raise ValueError("max_file_bytes debe ser mayor que cero.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds debe ser mayor que cero.")

        self.device = device
        self.max_pages = max_pages
        self.max_file_bytes = max_file_bytes
        self.timeout_seconds = timeout_seconds
        self._extractor: Any | None = None

    def _build_extractor(self) -> Any:
        try:
            from docling.backend.docling_parse_backend import (
                ThreadedDoclingParseDocumentBackend,
            )
            from docling.datamodel.accelerator_options import (
                AcceleratorOptions,
            )
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import (
                VlmExtractionPipelineOptions,
            )
            from docling.document_extractor import (
                DocumentExtractor,
                ExtractionFormatOption,
            )
            from docling.pipeline.extraction_vlm_pipeline import (
                ExtractionVlmPipeline,
            )
        except ImportError as exc:
            raise DoclingPocUnavailableError(
                "Docling no está instalado. Usa requirements-docling.txt "
                "para preparar la PoC."
            ) from exc

        options = VlmExtractionPipelineOptions(
            document_timeout=self.timeout_seconds,
            accelerator_options=AcceleratorOptions(device=self.device),
            enable_remote_services=False,
        )
        return DocumentExtractor(
            allowed_formats=[InputFormat.PDF],
            extraction_format_options={
                InputFormat.PDF: ExtractionFormatOption(
                    pipeline_cls=ExtractionVlmPipeline,
                    backend=ThreadedDoclingParseDocumentBackend,
                    pipeline_options=options,
                )
            },
        )

    def extract_path(self, path: Path) -> InvoiceDraft:
        return self.extract_bytes(path.read_bytes(), filename=path.name)

    def extract_bytes(
        self,
        content: bytes,
        *,
        filename: str = "factura.pdf",
    ) -> InvoiceDraft:
        if b"%PDF-" not in content[:1024]:
            raise DoclingPocExtractionError(
                "El archivo no contiene un PDF válido."
            )
        if len(content) > self.max_file_bytes:
            raise DoclingPocExtractionError(
                f"El PDF supera el límite de {self.max_file_bytes} bytes."
            )

        try:
            from docling.datamodel.base_models import DocumentStream
        except ImportError as exc:
            raise DoclingPocUnavailableError(
                "Docling no está instalado. Usa requirements-docling.txt "
                "para preparar la PoC."
            ) from exc

        if self._extractor is None:
            self._extractor = self._build_extractor()

        try:
            result = self._extractor.extract(
                source=DocumentStream(
                    name=filename,
                    stream=BytesIO(content),
                ),
                template=INVOICE_EXTRACTION_TEMPLATE,
                raises_on_error=False,
                max_num_pages=self.max_pages,
                max_file_size=self.max_file_bytes,
            )
        except Exception as exc:
            raise DoclingPocExtractionError(
                f"Docling no ha podido procesar el PDF: {exc}"
            ) from exc

        status = str(getattr(result.status, "value", result.status))
        global_errors = tuple(
            _error_text(error)
            for error in (getattr(result, "errors", ()) or ())
        )
        pages = tuple(
            ExtractedPagePayload(
                page_no=page.page_no,
                extracted_data=_mapping_from_extracted_data(
                    page.extracted_data
                ),
                raw_text=page.raw_text or "",
                errors=tuple(
                    str(error) for error in (page.errors or ())
                ),
            )
            for page in (getattr(result, "pages", ()) or ())
        )
        if not pages:
            details = "; ".join(global_errors) or "sin detalle adicional"
            raise DoclingPocExtractionError(
                "Docling no devolvió ninguna página procesada "
                f"({status}: {details})."
            )

        return assemble_invoice_draft(
            pages,
            source_name=filename,
            extraction_status=status,
            global_errors=global_errors,
        )
