import io
from typing import Any, Dict

from docxtpl import DocxTemplate

from docgen.anonymizer.pdf_adapter import render_pdf_template
from docgen.anonymizer.pptx_adapter import render_pptx_template
from docgen.document_formats import detect_document_format


def render_docx(template_bytes: bytes, context: Dict[str, Any]) -> bytes:
    """Renderiza la plantilla DOCX con el contexto y devuelve el docx generado como bytes."""
    tpl = DocxTemplate(io.BytesIO(template_bytes))
    tpl.render(context)
    out = io.BytesIO()
    tpl.save(out)
    return out.getvalue()


def render_document(template_bytes: bytes, context: Dict[str, Any]) -> bytes:
    document_format = detect_document_format(template_bytes)
    if document_format == "docx":
        return render_docx(template_bytes, context)
    if document_format == "pdf":
        return render_pdf_template(template_bytes, context)
    return render_pptx_template(template_bytes, context)
