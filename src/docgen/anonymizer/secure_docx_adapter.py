from __future__ import annotations

import io
import zipfile
from collections.abc import Iterable

from lxml import etree

from docgen.anonymizer.docx_adapter import (
    NS,
    XML_PARSER,
    DocxDocumentAdapter,
    _coverage_id,
    _is_text_part,
    _read_archive,
)
from docgen.anonymizer.models import CoverageIssue, Finding, TextBlock


class SecureDocxDocumentAdapter(DocxDocumentAdapter):
    """DOCX adapter with fail-closed coverage and package-wide verification."""

    def extract(
        self,
        document_bytes: bytes,
    ) -> tuple[tuple[TextBlock, ...], tuple[CoverageIssue, ...]]:
        blocks, issues = super().extract(document_bytes)
        files = _read_archive(document_bytes)
        linked_objects: list[str] = []
        for name, payload in files.items():
            if not _is_text_part(name):
                continue
            try:
                root = etree.fromstring(payload, parser=XML_PARSER)
            except etree.XMLSyntaxError:
                continue
            if root.xpath(".//a:blip[@r:link] | .//w:object | .//w:altChunk", namespaces=NS):
                linked_objects.append(name)
        if linked_objects:
            issues = (*issues, CoverageIssue(
                id=_coverage_id("linked_object", linked_objects),
                kind="linked_object",
                label="Objetos externos o no inspeccionables",
                detail="El documento referencia contenido que no forma parte del texto extraido.",
            ))
        unique = {issue.id: issue for issue in issues}
        return blocks, tuple(unique.values())

    def verify(
        self,
        document_bytes: bytes,
        applied_findings: Iterable[Finding],
    ) -> tuple[TextBlock, ...]:
        applied = tuple(applied_findings)
        blocks = super().verify(document_bytes, applied)
        files = _read_archive(document_bytes)
        xml_text = "\n".join(
            payload.decode("utf-8", errors="ignore").casefold()
            for name, payload in files.items()
            if name.endswith((".xml", ".rels"))
        )
        residuals = sorted({finding.value for finding in applied if finding.value.casefold() in xml_text})
        if residuals:
            raise ValueError(
                "La verificacion de todas las partes XML ha encontrado valores seleccionados sin sustituir."
            )
        with zipfile.ZipFile(io.BytesIO(document_bytes)) as archive:
            unsafe = [
                name for name in archive.namelist()
                if name.startswith(("word/media/", "word/embeddings/", "_xmlsignatures/"))
            ]
        if unsafe:
            raise ValueError("La copia generada conserva contenido binario no inspeccionable.")
        return blocks
