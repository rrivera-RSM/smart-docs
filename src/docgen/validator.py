import io
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from docx import Document

JINJA_SIMPLE_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


@dataclass
class SplitPlaceholderIssue:
    location: str
    variable: str
    paragraph_preview: str
    run_texts: List[str]


def _run_spans(paragraph) -> List[Tuple[int, int, str]]:
    """Devuelve spans (start, end, text)
    por run en el texto concatenado. end es exclusivo."""
    spans: List[Tuple[int, int, str]] = []
    pos = 0
    for run in paragraph.runs:
        txt = run.text or ""
        start = pos
        end = pos + len(txt)
        spans.append((start, end, txt))
        pos = end
    return spans


def _find_run_index(
    spans: List[Tuple[int, int, str]], char_pos: int
) -> Optional[int]:
    for i, (s, e, _) in enumerate(spans):
        if s <= char_pos < e:
            return i
    return None


def _preview(text: str, max_len: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def validate_template_placeholders(
    docx_bytes: bytes,
) -> List[SplitPlaceholderIssue]:
    """Valida que cada placeholder {{ var }}
    simple cae dentro de un único run."""
    doc = Document(io.BytesIO(docx_bytes))
    issues: List[SplitPlaceholderIssue] = []

    for pi, p in enumerate(doc.paragraphs):
        full = p.text or ""
        if "{{" not in full:
            continue

        spans = _run_spans(p)
        if not spans:
            continue

        for m in JINJA_SIMPLE_RE.finditer(full):
            var = m.group(1)
            start_char = m.start()
            end_char_inclusive = m.end() - 1

            run_start = _find_run_index(spans, start_char)
            run_end = _find_run_index(spans, end_char_inclusive)

            if run_start is None or run_end is None:
                continue

            if run_start != run_end:
                run_texts = [t for _, _, t in spans[run_start: run_end + 1]]
                issues.append(
                    SplitPlaceholderIssue(
                        location=f"body.paragraph[{pi}]",
                        variable=var,
                        paragraph_preview=_preview(full),
                        run_texts=run_texts,
                    )
                )

    return issues
