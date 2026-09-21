import io
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping

from docx import Document

from docgen.anonymizer.detectors import detect_text
from docgen.anonymizer.models import Finding
from docgen.placeholders import (
    find_run_index,
    get_run_spans,
    iter_document_paragraphs,
)


def analyze_document(docx_bytes: bytes) -> tuple[Finding, ...]:
    """Return reviewable findings from visible Word text."""
    document = Document(io.BytesIO(docx_bytes))
    findings: list[Finding] = []
    seen_elements: set[int] = set()

    for location, paragraph in iter_document_paragraphs(document):
        element_id = id(paragraph._p)
        if element_id in seen_elements:
            continue
        seen_elements.add(element_id)

        text = paragraph.text or ""
        if text:
            findings.extend(detect_text(text, location))

    return tuple(findings)


def summarize_findings(findings: Iterable[Finding]) -> dict[str, int]:
    return dict(Counter(finding.entity_type for finding in findings))


def _replace_range(
    paragraph: object,
    start: int,
    end: int,
    replacement: str,
) -> None:
    spans = get_run_spans(paragraph)
    run_start = find_run_index(spans, start)
    run_end = find_run_index(spans, end - 1)

    if run_start is None or run_end is None:
        raise ValueError("The selected text no longer exists in the document.")

    runs = paragraph.runs
    start_span = spans[run_start]
    end_span = spans[run_end]
    start_offset = start - start_span.start
    end_offset = end - end_span.start

    if run_start == run_end:
        original = runs[run_start].text or ""
        runs[run_start].text = (
            original[:start_offset] + replacement + original[end_offset:]
        )
        return

    start_text = runs[run_start].text or ""
    end_text = runs[run_end].text or ""
    runs[run_start].text = start_text[:start_offset] + replacement
    for run_index in range(run_start + 1, run_end):
        runs[run_index].text = ""
    runs[run_end].text = end_text[end_offset:]


def _clear_core_properties(document: object) -> None:
    properties = document.core_properties
    properties.author = ""
    properties.last_modified_by = ""
    properties.comments = ""
    properties.category = ""
    properties.content_status = ""
    properties.identifier = ""
    properties.keywords = ""
    properties.language = ""
    properties.subject = ""
    properties.title = ""
    properties.version = ""


def anonymize_document(
    docx_bytes: bytes,
    findings: Iterable[Finding],
    replacements: Mapping[str, str] | None = None,
) -> bytes:
    """Apply approved findings to a copy of the document and clear metadata."""
    selected = tuple(findings)
    if not selected:
        raise ValueError("At least one finding must be selected.")

    replacement_map = replacements or {}
    grouped: dict[str, list[Finding]] = defaultdict(list)
    for finding in selected:
        grouped[finding.location].append(finding)

    document = Document(io.BytesIO(docx_bytes))
    paragraphs = dict(iter_document_paragraphs(document))

    for location, location_findings in grouped.items():
        paragraph = paragraphs.get(location)
        if paragraph is None:
            raise ValueError(f"Document location not found: {location}")

        for finding in sorted(
            location_findings,
            key=lambda item: item.start,
            reverse=True,
        ):
            replacement = replacement_map.get(finding.id, finding.replacement)
            _replace_range(
                paragraph,
                finding.start,
                finding.end,
                replacement,
            )

    _clear_core_properties(document)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


# Advanced OOXML implementation. The legacy helpers above remain private
# compatibility code for existing imports while public calls use the modular
# document adapter and resolver.
from docgen.anonymizer.docx_adapter import DocxDocumentAdapter
from docgen.anonymizer.engine import build_rules_engine


def analyze_document(docx_bytes: bytes) -> tuple[Finding, ...]:
    """Analyze a DOCX with the deterministic local engine.

    FastAPI uses ``LocalAnonymizerEngine`` with the required transformer. This
    wrapper intentionally keeps unit-level and library callers deterministic.
    """
    return build_rules_engine().analyze(docx_bytes).findings


def summarize_findings(findings: Iterable[Finding]) -> dict[str, int]:
    return dict(Counter(finding.entity_type for finding in findings))


def anonymize_document(
    docx_bytes: bytes,
    findings: Iterable[Finding],
    replacements: Mapping[str, str] | None = None,
) -> bytes:
    selected = tuple(findings)
    if not selected:
        raise ValueError("At least one finding must be selected.")
    replacement_map = replacements or {}
    by_group = {
        finding.group_id: replacement_map.get(
            finding.id,
            replacement_map.get(finding.group_id, finding.replacement),
        )
        for finding in selected
    }
    adapter = DocxDocumentAdapter()
    output = adapter.apply(
        docx_bytes,
        selected,
        by_group,
        remove_unsupported_content=True,
    )
    adapter.verify(output, selected)
    return output
