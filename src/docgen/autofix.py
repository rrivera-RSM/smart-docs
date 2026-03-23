import io
import re
from typing import Tuple

from docx import Document

# Solo variables simples: {{ var }}
JINJA_SIMPLE_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def _run_spans(paragraph):
    """Devuelve spans (start, end, idx)
    para cada run dentro del texto concatenado del párrafo."""
    spans = []
    pos = 0
    for i, run in enumerate(paragraph.runs):
        t = run.text or ""
        spans.append((pos, pos + len(t), i))
        pos += len(t)
    return spans


def _find_run_index_for_char(spans, char_pos):
    for start, end, idx in spans:
        if start <= char_pos < end:
            return idx
    return None


def _iter_all_paragraphs(doc: Document):
    """
    Itera párrafos del body + tablas.
    (Headers/footers lo podemos añadir luego si lo necesitas.)
    """
    # Body paragraphs
    for p in doc.paragraphs:
        yield p

    # Tables (por si acaso)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    yield p


def autofix_split_placeholders(docx_bytes: bytes) -> Tuple[bytes, int]:
    """
    Repara placeholders partidos en runs fusionando los runs implicados.
    Preserva el estilo del primer run
      (el run inicial de la secuencia fusionada).

    Devuelve: (docx_bytes_reparado, numero_de_fusiones_realizadas)
    """
    doc = Document(io.BytesIO(docx_bytes))
    merges = 0

    for p in _iter_all_paragraphs(doc):
        # Repetimos hasta que ya no haya placeholders partidos en este párrafo
        while True:
            full = p.text or ""
            if "{{" not in full or not p.runs:
                break

            spans = _run_spans(p)
            changed = False

            for m in JINJA_SIMPLE_RE.finditer(full):
                start_char = m.start()
                end_char_inclusive = m.end() - 1

                run_start = _find_run_index_for_char(spans, start_char)
                run_end = _find_run_index_for_char(spans, end_char_inclusive)

                if run_start is None or run_end is None:
                    continue

                if run_start != run_end:
                    runs = p.runs
                    merged_text = "".join(
                        runs[i].text or "" for i in range(
                            run_start, run_end + 1
                        )
                    )

                    # Preservar estilo del primer run:
                    # - no tocamos propiedades del run_start
                    runs[run_start].text = merged_text

                    for i in range(run_start + 1, run_end + 1):
                        runs[i].text = ""

                    merges += 1
                    changed = True
                    break  # recompute spans y texto

            if not changed:
                break

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue(), merges
