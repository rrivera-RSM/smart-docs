from __future__ import annotations

import hashlib
import io
import re
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence

from lxml import etree

from docgen.anonymizer.models import CoverageIssue, DocumentLocation, Finding, TextBlock

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
V_NS = "urn:schemas-microsoft-com:vml"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPE_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
NS = {"w": W_NS, "r": R_NS, "a": A_NS, "v": V_NS}
XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, recover=False, huge_tree=False)


def _is_text_part(name: str) -> bool:
    return bool(re.fullmatch(r"word/(?:document|header\d+|footer\d+|footnotes|endnotes)\.xml", name))


def _part_label(name: str) -> str:
    if name == "word/document.xml":
        return "Documento"
    if "header" in name:
        return "Cabecera"
    if "footer" in name:
        return "Pie de página"
    if "footnotes" in name:
        return "Notas al pie"
    if "endnotes" in name:
        return "Notas finales"
    return "Documento"


def _read_archive(content: bytes) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            return {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}
    except zipfile.BadZipFile as exc:
        raise ValueError("El archivo no contiene un documento Word válido.") from exc


def _parse_xml(content: bytes) -> etree._Element:
    return etree.fromstring(content, parser=XML_PARSER)


def _paragraphs(root: etree._Element) -> list[etree._Element]:
    return root.xpath(".//w:p[not(ancestor::w:p)]", namespaces=NS)


def _text_nodes(paragraph: etree._Element) -> list[etree._Element]:
    return paragraph.xpath(".//w:t", namespaces=NS)


def _paragraph_text(paragraph: etree._Element) -> str:
    return "".join(node.text or "" for node in _text_nodes(paragraph))


def _paragraph_label(paragraph: etree._Element, part_name: str) -> str:
    default = _part_label(part_name)
    cells = paragraph.xpath("ancestor::w:tc[1]", namespaces=NS)
    if not cells:
        return default
    cell = cells[0]
    row = cell.getparent()
    if row is None or etree.QName(row).localname != "tr":
        return default
    row_cells = row.xpath("./w:tc", namespaces=NS)
    if cell not in row_cells or row_cells.index(cell) == 0:
        return default
    label = "".join(row_cells[0].xpath(".//w:t/text()", namespaces=NS)).strip()
    return f"{default} · {label[:80]}" if label else default


def _coverage_id(kind: str, names: Sequence[str]) -> str:
    return hashlib.sha256(f"{kind}:{':'.join(sorted(names))}".encode()).hexdigest()[:18]


def _coverage_issues(files: Mapping[str, bytes]) -> tuple[CoverageIssue, ...]:
    categories = (
        ("image", [name for name in files if name.startswith("word/media/")], "Imágenes incrustadas", "Las imágenes no se inspeccionan sin OCR y deben eliminarse de la copia segura."),
        ("embedded_object", [name for name in files if name.startswith("word/embeddings/")], "Objetos incrustados", "Los objetos OLE pueden contener información no visible para el analizador."),
        ("signature", [name for name in files if "_xmlsignatures" in name], "Firma digital", "La firma no puede conservarse después de modificar y sanear el documento."),
    )
    return tuple(
        CoverageIssue(id=_coverage_id(kind, names), kind=kind, label=label, detail=detail)
        for kind, names, label, detail in categories if names
    )


def _replace_range(nodes: Sequence[etree._Element], start: int, end: int, replacement: str) -> None:
    spans: list[tuple[int, int, etree._Element]] = []
    position = 0
    for node in nodes:
        text = node.text or ""
        spans.append((position, position + len(text), node))
        position += len(text)
    first = next((index for index, (left, right, _) in enumerate(spans) if left <= start < right), None)
    last = next((index for index, (left, right, _) in enumerate(spans) if left <= end - 1 < right), None)
    if first is None or last is None:
        raise ValueError("El texto seleccionado ya no existe en el documento.")
    first_left, _, first_node = spans[first]
    last_left, _, last_node = spans[last]
    first_offset, last_offset = start - first_left, end - last_left
    if first == last:
        original = first_node.text or ""
        first_node.text = original[:first_offset] + replacement + original[last_offset:]
        return
    first_node.text = (first_node.text or "")[:first_offset] + replacement
    for index in range(first + 1, last):
        spans[index][2].text = ""
    last_node.text = (last_node.text or "")[last_offset:]


def _remove_element(element: etree._Element) -> None:
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def _unwrap(element: etree._Element) -> None:
    parent = element.getparent()
    if parent is None:
        return
    index = parent.index(element)
    for child in list(element):
        parent.insert(index, child)
        index += 1
    parent.remove(element)


def _sanitize_story(root: etree._Element, *, remove_unsupported_content: bool) -> None:
    for element in root.xpath(".//w:del | .//w:commentRangeStart | .//w:commentRangeEnd | .//w:commentReference", namespaces=NS):
        _remove_element(element)
    for element in list(root.xpath(".//w:ins", namespaces=NS)):
        _unwrap(element)
    sensitive_attributes = {f"{{{W_NS}}}author", f"{{{W_NS}}}date", f"{{{W_NS}}}initials"}
    for element in root.iter():
        for attribute in tuple(element.attrib):
            if attribute in sensitive_attributes:
                element.attrib.pop(attribute, None)
    if remove_unsupported_content:
        xpath = ".//w:drawing[.//a:blip] | .//w:object | .//w:pict[.//v:imagedata] | .//w:altChunk"
        for element in root.xpath(xpath, namespaces=NS):
            _remove_element(element)


def _sanitize_relationships(root: etree._Element) -> None:
    for relationship in list(root):
        target = relationship.get("Target", "").lower()
        rel_type = relationship.get("Type", "").lower()
        if any(marker in target or marker in rel_type for marker in ("media/", "embeddings/", "signature", "afchunk", "oleobject", "/image")):
            root.remove(relationship)


def _serialize(root: etree._Element) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


class DocxDocumentAdapter:
    format_name = "docx"

    def extract(self, document_bytes: bytes) -> tuple[tuple[TextBlock, ...], tuple[CoverageIssue, ...]]:
        files = _read_archive(document_bytes)
        blocks: list[TextBlock] = []
        for part_name in sorted(name for name in files if _is_text_part(name)):
            root = _parse_xml(files[part_name])
            for index, paragraph in enumerate(_paragraphs(root)):
                text = _paragraph_text(paragraph)
                if not text.strip():
                    continue
                location = DocumentLocation(
                    kind="docx",
                    part=part_name,
                    block_index=index,
                    label=_paragraph_label(paragraph, part_name),
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
            raise ValueError("El documento contiene elementos no inspeccionables que deben eliminarse.")
        grouped: dict[str, list[Finding]] = defaultdict(list)
        for finding in findings:
            grouped[finding.location_id].append(finding)

        for part_name in sorted(name for name in files if _is_text_part(name)):
            root = _parse_xml(files[part_name])
            paragraphs = _paragraphs(root)
            for index, paragraph in enumerate(paragraphs):
                location_id = f"{part_name}:paragraph[{index}]"
                for finding in sorted(grouped.get(location_id, ()), key=lambda item: item.start, reverse=True):
                    _replace_range(_text_nodes(paragraph), finding.start, finding.end, replacements.get(finding.group_id, finding.replacement))
            _sanitize_story(root, remove_unsupported_content=remove_unsupported_content)
            files[part_name] = _serialize(root)

        for name in tuple(files):
            if name in {"word/comments.xml", "docProps/core.xml", "docProps/custom.xml", "docProps/app.xml"} or name.startswith("customXml/") and name.endswith(".xml"):
                try:
                    root = _parse_xml(files[name])
                except etree.XMLSyntaxError:
                    continue
                for element in root.iter():
                    if element.text and element.text.strip():
                        element.text = ""
                files[name] = _serialize(root)
            if remove_unsupported_content and (name.startswith("word/media/") or name.startswith("word/embeddings/") or "_xmlsignatures" in name or name.lower().startswith(("word/afchunk", "word/altchunk"))):
                files.pop(name, None)
            elif remove_unsupported_content and name.endswith(".rels"):
                try:
                    root = _parse_xml(files[name])
                except etree.XMLSyntaxError:
                    continue
                _sanitize_relationships(root)
                files[name] = _serialize(root)

        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        return output.getvalue()

    def verify(
        self,
        document_bytes: bytes,
        applied_findings: Iterable[Finding],
    ) -> tuple[TextBlock, ...]:
        blocks, issues = self.extract(document_bytes)
        if issues:
            raise ValueError("La copia generada todavía contiene elementos no inspeccionables.")
        searchable = "\n".join(block.text for block in blocks).casefold()
        remaining = [finding.value for finding in applied_findings if finding.value.casefold() in searchable]
        if remaining:
            raise ValueError("La verificación posterior ha encontrado valores seleccionados sin sustituir.")
        files = _read_archive(document_bytes)
        for name in ("docProps/core.xml", "docProps/custom.xml"):
            if name not in files:
                continue
            root = _parse_xml(files[name])
            if any((element.text or "").strip() for element in root.iter()):
                raise ValueError("La copia generada conserva metadatos personales.")
        return blocks
