import io
from typing import Any, Dict

from docxtpl import DocxTemplate


def render_docx(template_bytes: bytes, context: Dict[str, Any]) -> bytes:
    """Renderiza la plantilla DOCX con el contexto y devuelve el docx generado como bytes."""
    tpl = DocxTemplate(io.BytesIO(template_bytes))
    tpl.render(context)
    out = io.BytesIO()
    tpl.save(out)
    return out.getvalue()
