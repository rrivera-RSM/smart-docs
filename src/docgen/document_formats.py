from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from docgen.feature_flags import require_document_format_enabled

DocumentFormat = Literal["docx", "pdf", "pptx"]


@dataclass(frozen=True)
class DocumentFormatSpec:
    id: DocumentFormat
    label: str
    extension: str
    mime_type: str


FORMAT_SPECS: dict[DocumentFormat, DocumentFormatSpec] = {
    "docx": DocumentFormatSpec(
        id="docx",
        label="Microsoft Word",
        extension=".docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    "pdf": DocumentFormatSpec(
        id="pdf",
        label="PDF",
        extension=".pdf",
        mime_type="application/pdf",
    ),
    "pptx": DocumentFormatSpec(
        id="pptx",
        label="Microsoft PowerPoint",
        extension=".pptx",
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
}

SUPPORTED_EXTENSIONS = tuple(spec.extension for spec in FORMAT_SPECS.values())


def detect_document_format(content: bytes) -> DocumentFormat:
    if content.startswith(b"%PDF-"):
        return "pdf"
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise ValueError("El archivo no contiene un documento compatible válido.") from exc
    if "word/document.xml" in names:
        return "docx"
    if "ppt/presentation.xml" in names:
        return "pptx"
    raise ValueError("El archivo no contiene un documento DOCX, PDF o PPTX válido.")


def validate_document(
    filename: str | None,
    content: bytes,
    *,
    max_expanded_bytes: int,
) -> tuple[str, DocumentFormat]:
    safe_name = Path((filename or "documento").replace("\\", "/")).name
    suffix = Path(safe_name).suffix.casefold()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError("El formato no es compatible. Utiliza DOCX, PDF o PPTX.")
    try:
        document_format = detect_document_format(content)
    except ValueError as exc:
        label = {
            ".docx": "un documento Word",
            ".pdf": "un PDF",
            ".pptx": "una presentación PowerPoint",
        }[suffix]
        raise ValueError(f"El archivo no contiene {label} válido.") from exc
    require_document_format_enabled(document_format)
    if suffix != FORMAT_SPECS[document_format].extension:
        raise ValueError("La extensión del archivo no coincide con su contenido.")
    if document_format in {"docx", "pptx"}:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if sum(item.file_size for item in archive.infolist()) > max_expanded_bytes:
                raise OverflowError("El contenido expandido supera el límite de 60 MB.")
    return safe_name, document_format


def mime_type_for(document_format: DocumentFormat) -> str:
    return FORMAT_SPECS[document_format].mime_type


def output_filename(
    source_name: str,
    operation: Literal["generado", "anonimizado", "reparada"],
) -> str:
    source = Path(source_name)
    extension = source.suffix.casefold()
    if extension not in SUPPORTED_EXTENSIONS:
        extension = ".docx"
    return f"{source.stem}_{operation}{extension}"
