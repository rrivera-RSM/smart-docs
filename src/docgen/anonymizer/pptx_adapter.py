from __future__ import annotations

import hashlib
import io
import re
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence

from lxml import etree

from docgen.anonymizer.docx_adapter import XML_PARSER, _replace_range
from docgen.anonymizer.models import CoverageIssue, DocumentLocation, Finding, TextBlock

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPE_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
NS = {"a": A_NS, "p": P_NS}

TEXT_PART = re.compile(
    r"ppt/(?:slides/slide\d+|notesSlides/notesSlide\d+|"
    r"slideMasters/slideMaster\d+|slideLayouts/slideLayout\d+|"
    r"diagrams/data\d+)\.xml"
)
VARIABLE_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")


def _read_archive(content: bytes) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            files = {
                name: archive.read(name)
                for name in archive.namelist()
                if not name.endswith("/")
            }
    except zipfile.BadZipFile as exc:
        raise ValueError("El archivo no contiene una presentación PowerPoint válida.") from exc
    if "ppt/presentation.xml" not in files:
        raise ValueError("El archivo no contiene una presentación PowerPoint válida.")
    return files


def _parse_xml(content: bytes) -> etree._Element:
    return etree.fromstring(content, parser=XML_PARSER)


def _serialize(root: etree._Element) -> bytes:
    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )


def _is_text_part(name: str) -> bool:
    return bool(TEXT_PART.fullmatch(name))


def _part_label(name: str) -> str:
    if "/slides/" in name:
        return "Diapositiva"
    if "/notesSlides/" in name:
        return "Notas del presentador"
    if "/slideMasters/" in name:
        return "Patrón de diapositivas"
    if "/slideLayouts/" in name:
        return "Diseño de diapositiva"
    if "/diagrams/" in name:
        return "SmartArt"
    return "Presentación"


def _paragraphs(root: etree._Element) -> list[etree._Element]:
    return root.xpath(".//a:p[not(ancestor::a:p)]", namespaces=NS)


def _text_nodes(paragraph: etree._Element) -> list[etree._Element]:
    return paragraph.xpath(".//a:t", namespaces=NS)


def _paragraph_text(paragraph: etree._Element) -> str:
    return "".join(node.text or "" for node in _text_nodes(paragraph))


def _coverage_id(kind: str, names: Sequence[str]) -> str:
    payload = f"{kind}:{':'.join(sorted(names))}".encode()
    return hashlib.sha256(payload).hexdigest()[:18]


def _coverage_issues(files: Mapping[str, bytes]) -> tuple[CoverageIssue, ...]:
    categories = (
        (
            "image",
            [name for name in files if name.startswith("ppt/media/")],
            "Imágenes incrustadas",
            "Las imágenes de la presentación no se inspeccionan y deben eliminarse.",
        ),
        (
            "embedded_object",
            [
                name
                for name in files
                if name.startswith(("ppt/embeddings/", "ppt/activeX/"))
                or name.endswith("vbaProject.bin")
            ],
            "Objetos incrustados o macros",
            "Los objetos OLE, controles y macros pueden contener información oculta.",
        ),
        (
            "chart",
            [name for name in files if name.startswith("ppt/charts/")],
            "Gráficos",
            "Los datos internos de los gráficos no se inspeccionan en esta versión.",
        ),
        (
            "signature",
            [name for name in files if "_xmlsignatures" in name.casefold()],
            "Firma digital",
            "La firma no puede conservarse al generar una copia saneada.",
        ),
    )
    return tuple(
        CoverageIssue(
            id=_coverage_id(kind, names),
            kind=kind,
            label=label,
            detail=detail,
            blocking=True,
            removable=True,
        )
        for kind, names, label, detail in categories
        if names
    )


def _remove_element(element: etree._Element) -> None:
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def _remove_containing_shape(element: etree._Element) -> None:
    current: etree._Element | None = element
    while current is not None:
        if etree.QName(current).localname in {
            "pic",
            "graphicFrame",
            "oleObj",
            "control",
            "bg",
        }:
            _remove_element(current)
            return
        current = current.getparent()
    _remove_element(element)


def _sanitize_part(root: etree._Element, *, remove_unsupported_content: bool) -> None:
    for link in root.xpath(".//a:hlinkClick | .//a:hlinkMouseOver", namespaces=NS):
        _remove_element(link)
    if not remove_unsupported_content:
        return
    unsupported = root.xpath(
        ".//a:blip | .//p:oleObj | .//p:control | "
        ".//a:graphicData[contains(@uri, 'chart')]",
        namespaces=NS,
    )
    for element in list(unsupported):
        _remove_containing_shape(element)


UNSAFE_MARKERS = (
    "media/",
    "embeddings/",
    "activex",
    "oleobject",
    "/image",
    "/chart",
    "charts/",
    "vbaproject",
    "signature",
)
PRIVATE_MARKERS = (
    "comments",
    "commentauthors",
    "persons/",
    "customxml",
    "core-properties",
    "extended-properties",
)


def _sanitize_relationships(
    root: etree._Element,
    *,
    remove_unsupported_content: bool,
) -> None:
    for relationship in list(root):
        target = relationship.get("Target", "").casefold()
        rel_type = relationship.get("Type", "").casefold()
        is_external = relationship.get("TargetMode", "").casefold() == "external"
        private = any(marker in target or marker in rel_type for marker in PRIVATE_MARKERS)
        unsupported = any(marker in target or marker in rel_type for marker in UNSAFE_MARKERS)
        if is_external or private or (remove_unsupported_content and unsupported):
            root.remove(relationship)


def _write_archive(files: Mapping[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


class PptxDocumentAdapter:
    format_name = "pptx"

    def extract(
        self,
        document_bytes: bytes,
    ) -> tuple[tuple[TextBlock, ...], tuple[CoverageIssue, ...]]:
        files = _read_archive(document_bytes)
        blocks: list[TextBlock] = []
        for part_name in sorted(name for name in files if _is_text_part(name)):
            root = _parse_xml(files[part_name])
            for index, paragraph in enumerate(_paragraphs(root)):
                text = _paragraph_text(paragraph)
                if not text.strip():
                    continue
                location = DocumentLocation(
                    kind="pptx",
                    part=part_name,
                    block_index=index,
                    label=_part_label(part_name),
                )
                blocks.append(TextBlock(id=location.id, text=text, location=location))
        return tuple(blocks), _coverage_issues(files)

    def apply(
        self,
        document_bytes: bytes,
        findings: Sequence[Finding],
        replacements: Mapping[str, str],
        *,
        remove_unsupported_content: bool,
    ) -> bytes:
        files = _read_archive(document_bytes)
        issues = _coverage_issues(files)
        if issues and not remove_unsupported_content:
            raise ValueError(
                "La presentación contiene elementos no inspeccionables que deben eliminarse."
            )
        grouped: dict[str, list[Finding]] = defaultdict(list)
        for finding in findings:
            grouped[finding.location_id].append(finding)

        for part_name in sorted(name for name in files if _is_text_part(name)):
            root = _parse_xml(files[part_name])
            for index, paragraph in enumerate(_paragraphs(root)):
                location = DocumentLocation(
                    kind="pptx",
                    part=part_name,
                    block_index=index,
                    label=_part_label(part_name),
                )
                for finding in sorted(
                    grouped.get(location.id, ()),
                    key=lambda item: item.start,
                    reverse=True,
                ):
                    _replace_range(
                        _text_nodes(paragraph),
                        finding.start,
                        finding.end,
                        replacements.get(finding.group_id, finding.replacement),
                    )
            _sanitize_part(
                root,
                remove_unsupported_content=remove_unsupported_content,
            )
            files[part_name] = _serialize(root)

        for name in tuple(files):
            lower = name.casefold()
            private = lower.startswith(
                ("docprops/", "customxml/", "ppt/comments/", "ppt/commentauthors")
            ) or "/persons/" in lower
            unsupported = (
                lower.startswith(
                    ("ppt/media/", "ppt/embeddings/", "ppt/activex/", "ppt/charts/")
                )
                or lower.endswith("vbaproject.bin")
                or "_xmlsignatures" in lower
            )
            if private or (remove_unsupported_content and unsupported):
                files.pop(name, None)
                continue
            if name.endswith(".rels"):
                try:
                    root = _parse_xml(files[name])
                except etree.XMLSyntaxError:
                    continue
                _sanitize_relationships(
                    root,
                    remove_unsupported_content=remove_unsupported_content,
                )
                files[name] = _serialize(root)
        return _write_archive(files)

    def verify(
        self,
        document_bytes: bytes,
        applied_findings: Iterable[Finding],
    ) -> tuple[TextBlock, ...]:
        applied = tuple(applied_findings)
        blocks, issues = self.extract(document_bytes)
        if issues:
            raise ValueError(
                "La presentación generada conserva contenido no inspeccionable."
            )
        searchable = "\n".join(block.text for block in blocks).casefold()
        if any(finding.value.casefold() in searchable for finding in applied):
            raise ValueError(
                "La verificación posterior ha encontrado valores seleccionados sin sustituir."
            )
        files = _read_archive(document_bytes)
        xml_text = "\n".join(
            payload.decode("utf-8", errors="ignore").casefold()
            for name, payload in files.items()
            if name.endswith((".xml", ".rels"))
        )
        if any(finding.value.casefold() in xml_text for finding in applied):
            raise ValueError(
                "La verificación de la presentación ha encontrado valores residuales."
            )
        return blocks


def render_pptx_template(
    template_bytes: bytes,
    context: Mapping[str, object],
) -> bytes:
    files = _read_archive(template_bytes)
    for part_name in sorted(name for name in files if _is_text_part(name)):
        root = _parse_xml(files[part_name])
        for paragraph in _paragraphs(root):
            text = _paragraph_text(paragraph)
            matches = list(VARIABLE_PATTERN.finditer(text))
            for match in reversed(matches):
                value = str(context.get(match.group(1), ""))
                _replace_range(_text_nodes(paragraph), match.start(), match.end(), value)
        files[part_name] = _serialize(root)
    return _write_archive(files)
