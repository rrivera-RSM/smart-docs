from __future__ import annotations

from docgen.anonymizer.pdf_adapter import PdfDocumentAdapter
from docgen.anonymizer.pptx_adapter import PptxDocumentAdapter
from docgen.anonymizer.ports import DocumentAdapter
from docgen.anonymizer.secure_docx_adapter import SecureDocxDocumentAdapter
from docgen.document_formats import FORMAT_SPECS, detect_document_format
from docgen.feature_flags import document_format_enabled


class DocumentAdapterRegistry:
    """Select the document implementation from the file signature."""

    def __init__(self) -> None:
        self._adapters: dict[str, DocumentAdapter] = {
            "docx": SecureDocxDocumentAdapter(),
            "pdf": PdfDocumentAdapter(),
            "pptx": PptxDocumentAdapter(),
        }

    def for_document(self, document_bytes: bytes) -> DocumentAdapter:
        document_format = detect_document_format(document_bytes)
        return self._adapters[document_format]

    def capabilities(self) -> list[dict[str, object]]:
        details = {
            "docx": "Texto, tablas, cabeceras, pies y notas.",
            "pdf": "Texto digital y páginas escaneadas mediante OCR local.",
            "pptx": "Diapositivas, notas, patrones, diseños y SmartArt.",
        }
        return [
            {
                "id": identifier,
                "label": spec.label,
                "enabled": document_format_enabled(identifier),
                "reason": (
                    details[identifier]
                    if document_format_enabled(identifier)
                    else "Disponible en una fase posterior."
                ),
            }
            for identifier, spec in FORMAT_SPECS.items()
        ]
