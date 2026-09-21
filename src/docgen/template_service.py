from dataclasses import dataclass
import re
from typing import Literal

from docgen.anonymizer.adapter_registry import DocumentAdapterRegistry
from docgen.document_formats import DocumentFormat, detect_document_format
from docgen.extractor import (
    extract_vars_docxtpl,
    extract_vars_fallback_regex,
)
from docgen.validator import (
    SplitPlaceholderIssue,
    validate_template_placeholders,
)

ExtractionMethod = Literal["docxtpl", "regex", "pdf_text", "pptx_xml", "none"]
VARIABLE_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")


@dataclass(frozen=True)
class TemplateAnalysis:
    """Result of inspecting a Word template before showing its form."""

    variables: tuple[str, ...]
    issues: tuple[SplitPlaceholderIssue, ...]
    extraction_method: ExtractionMethod
    document_format: DocumentFormat = "docx"

    @property
    def is_ready(self) -> bool:
        return not self.issues and bool(self.variables)


def _analyze_docx(docx_bytes: bytes) -> TemplateAnalysis:
    issues = tuple(validate_template_placeholders(docx_bytes))
    if issues:
        return TemplateAnalysis(
            variables=(),
            issues=issues,
            extraction_method="none",
            document_format="docx",
        )

    try:
        variables = extract_vars_docxtpl(docx_bytes)
        extraction_method: ExtractionMethod = "docxtpl"
    except Exception:
        variables = []
        extraction_method = "none"

    if not variables:
        variables = extract_vars_fallback_regex(docx_bytes)
        extraction_method = "regex" if variables else "none"

    return TemplateAnalysis(
        variables=tuple(variables),
        issues=(),
        extraction_method=extraction_method,
        document_format="docx",
    )


def analyze_template(document_bytes: bytes) -> TemplateAnalysis:
    """Validate a DOCX, PDF or PPTX template and discover simple variables."""
    document_format = detect_document_format(document_bytes)
    if document_format == "docx":
        return _analyze_docx(document_bytes)

    adapter = DocumentAdapterRegistry().for_document(document_bytes)
    blocks, _ = adapter.extract(document_bytes)
    variables: list[str] = []
    for block in blocks:
        for match in VARIABLE_PATTERN.finditer(block.text):
            if match.group(1) not in variables:
                variables.append(match.group(1))
    method: ExtractionMethod = "pdf_text" if document_format == "pdf" else "pptx_xml"
    return TemplateAnalysis(
        variables=tuple(variables),
        issues=(),
        extraction_method=method if variables else "none",
        document_format=document_format,
    )
