import io
import re
import zipfile
from typing import List, Set

from docxtpl import DocxTemplate

_SIMPLE_VAR_RE = re.compile(r"^[^\W\d]\w*$", re.UNICODE)


def extract_vars_docxtpl(docx_bytes: bytes) -> List[str]:
    """Extrae variables usando docxtpl.get_undeclared_template_variables()."""
    tpl = DocxTemplate(io.BytesIO(docx_bytes))
    vars_set = tpl.get_undeclared_template_variables()

    clean: Set[str] = set()
    for v in vars_set:
        v = (v or "").strip()
        if _SIMPLE_VAR_RE.fullmatch(v):
            clean.add(v)

    return sorted(clean)


def extract_vars_fallback_regex(docx_bytes: bytes) -> List[str]:
    """Fallback: busca {{ var }} simples dentro de word/document.xml."""
    found: Set[str] = set()

    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="ignore")

    for var in re.findall(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", xml):
        found.add(var)

    return sorted(found)
