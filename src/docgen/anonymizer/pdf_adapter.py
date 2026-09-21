from __future__ import annotations

import hashlib
import io
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from functools import lru_cache
from importlib.resources import files as resource_files

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont, ImageStat
from pypdf import PdfReader
from rapidocr import RapidOCR
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from docgen.anonymizer.models import CoverageIssue, DocumentLocation, Finding, TextBlock
from docgen.feature_flags import image_ocr_enabled

RENDER_SCALE = 2.0
VARIABLE_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")
PAGE_PATTERN = re.compile(r"page\[(\d+)]/(text|ocr)")

PixelBox = tuple[int, int, int, int]
OcrLine = tuple[str, PixelBox]


def _coverage_id(page_index: int) -> str:
    return hashlib.sha256(f"pdf:unreadable:{page_index}".encode()).hexdigest()[:18]


@lru_cache(maxsize=1)
def _ocr_engine() -> RapidOCR:
    model_dir = resource_files("rapidocr").joinpath("models")
    required = (
        "PP-OCRv6_det_small.onnx",
        "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
        "PP-OCRv6_rec_small.onnx",
    )
    if any(not model_dir.joinpath(name).is_file() for name in required):
        raise RuntimeError(
            "Los modelos OCR locales no están instalados; no se descargan en runtime."
        )
    return RapidOCR()


def _render_page(page: pdfium.PdfPage) -> Image.Image:
    return page.render(scale=RENDER_SCALE, may_draw_forms=True).to_pil().convert("RGB")


def _is_blank(image: Image.Image) -> bool:
    grayscale = image.convert("L")
    stats = ImageStat.Stat(grayscale)
    return stats.mean[0] > 248 and stats.stddev[0] < 2.5


def _ocr_lines(image: Image.Image) -> list[OcrLine]:
    result = _ocr_engine()(np.asarray(image))
    if result.boxes is None or result.txts is None:
        return []
    lines: list[OcrLine] = []
    for points, text in zip(result.boxes, result.txts, strict=False):
        if not str(text).strip():
            continue
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        box = (
            max(0, int(min(xs)) - 3),
            max(0, int(min(ys)) - 3),
            min(image.width, int(max(xs)) + 3),
            min(image.height, int(max(ys)) + 3),
        )
        lines.append((str(text), box))
    return lines


def _digital_location(page_index: int) -> DocumentLocation:
    return DocumentLocation(
        kind="pdf",
        part=f"page[{page_index + 1}]/text",
        block_index=0,
        label=f"Página {page_index + 1}",
    )


def _ocr_location(page_index: int, line_index: int) -> DocumentLocation:
    return DocumentLocation(
        kind="pdf",
        part=f"page[{page_index + 1}]/ocr",
        block_index=line_index,
        label=f"Página {page_index + 1} · OCR",
    )


def _page_text(page: pdfium.PdfPage) -> tuple[pdfium.PdfTextPage, str]:
    text_page = page.get_textpage()
    return text_page, text_page.get_text_range()


def _pixel_char_boxes(
    text_page: pdfium.PdfTextPage,
    *,
    start: int,
    end: int,
    page_height: float,
) -> list[PixelBox]:
    boxes: list[PixelBox] = []
    for index in range(start, end):
        try:
            left, bottom, right, top = text_page.get_charbox(index, loose=True)
        except Exception:
            continue
        if right <= left or top <= bottom:
            continue
        boxes.append(
            (
                int(left * RENDER_SCALE) - 3,
                int((page_height - top) * RENDER_SCALE) - 3,
                int(right * RENDER_SCALE) + 3,
                int((page_height - bottom) * RENDER_SCALE) + 3,
            )
        )
    if not boxes:
        raise ValueError("No se han podido localizar las coordenadas del texto en el PDF.")

    lines: list[list[PixelBox]] = []
    for box in boxes:
        center = (box[1] + box[3]) / 2
        target = next(
            (
                line
                for line in lines
                if abs(center - sum((item[1] + item[3]) / 2 for item in line) / len(line))
                <= max(box[3] - box[1], 8)
            ),
            None,
        )
        if target is None:
            lines.append([box])
        else:
            target.append(box)
    return [
        (
            min(item[0] for item in line),
            min(item[1] for item in line),
            max(item[2] for item in line),
            max(item[3] for item in line),
        )
        for line in lines
    ]


def _font_for(box: PixelBox) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = max(10, min(28, int((box[3] - box[1]) * 0.62)))
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def _paint_boxes(
    image: Image.Image,
    boxes: Sequence[PixelBox],
    replacement: str,
    *,
    secure: bool,
) -> None:
    if not boxes:
        return
    draw = ImageDraw.Draw(image)
    background = "black" if secure else "white"
    foreground = "white" if secure else "black"
    for box in boxes:
        draw.rectangle(box, fill=background)
    first = boxes[0]
    draw.text(
        (first[0] + 3, first[1] + 1),
        replacement,
        fill=foreground,
        font=_font_for(first),
    )


def _images_to_pdf(pages: Sequence[tuple[Image.Image, float, float]]) -> bytes:
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pageCompression=1)
    pdf.setTitle("SmartDocs")
    pdf.setAuthor("")
    pdf.setSubject("")
    for image, width, height in pages:
        pdf.setPageSize((width, height))
        encoded = io.BytesIO()
        image.save(encoded, format="JPEG", quality=94, optimize=True)
        encoded.seek(0)
        pdf.drawImage(ImageReader(encoded), 0, 0, width=width, height=height)
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def _open_pdf(document_bytes: bytes) -> pdfium.PdfDocument:
    try:
        document = pdfium.PdfDocument(document_bytes)
    except Exception as exc:
        raise ValueError("El archivo no contiene un PDF válido o está protegido.") from exc
    if len(document) == 0:
        document.close()
        raise ValueError("El PDF no contiene páginas.")
    return document


class PdfDocumentAdapter:
    format_name = "pdf"

    def extract(
        self,
        document_bytes: bytes,
    ) -> tuple[tuple[TextBlock, ...], tuple[CoverageIssue, ...]]:
        document = _open_pdf(document_bytes)
        blocks: list[TextBlock] = []
        issues: list[CoverageIssue] = []
        try:
            for page_index in range(len(document)):
                page = document[page_index]
                text_page, text = _page_text(page)
                try:
                    if text.strip():
                        location = _digital_location(page_index)
                        blocks.append(TextBlock(id=location.id, text=text, location=location))
                        continue
                    image = _render_page(page)
                    if not image_ocr_enabled():
                        if not _is_blank(image):
                            issues.append(
                                CoverageIssue(
                                    id=_coverage_id(page_index),
                                    kind="image_ocr_disabled",
                                    label=f"Página {page_index + 1} requiere OCR",
                                    detail=(
                                        "La lectura de imágenes está deshabilitada en este despliegue "
                                        "y se habilitará en una fase posterior."
                                    ),
                                    blocking=True,
                                    removable=False,
                                )
                            )
                        continue
                    lines = _ocr_lines(image)
                    for line_index, (line_text, _) in enumerate(lines):
                        location = _ocr_location(page_index, line_index)
                        blocks.append(
                            TextBlock(id=location.id, text=line_text, location=location)
                        )
                    if not lines and not _is_blank(image):
                        issues.append(
                            CoverageIssue(
                                id=_coverage_id(page_index),
                                kind="unreadable_pdf_page",
                                label=f"Página {page_index + 1} no legible",
                                detail=(
                                    "La página no tiene texto digital y el OCR local no ha "
                                    "podido leerla con suficiente seguridad."
                                ),
                                blocking=True,
                                removable=False,
                            )
                        )
                finally:
                    text_page.close()
                    page.close()
        finally:
            document.close()
        return tuple(blocks), tuple(issues)

    def apply(
        self,
        document_bytes: bytes,
        findings: Sequence[Finding],
        replacements: Mapping[str, str],
        *,
        remove_unsupported_content: bool,
    ) -> bytes:
        del remove_unsupported_content
        _, issues = self.extract(document_bytes)
        if issues:
            raise ValueError("El PDF contiene páginas que no pueden inspeccionarse.")
        grouped: dict[str, list[Finding]] = defaultdict(list)
        for finding in findings:
            grouped[finding.location_id].append(finding)

        document = _open_pdf(document_bytes)
        rendered: list[tuple[Image.Image, float, float]] = []
        try:
            for page_index in range(len(document)):
                page = document[page_index]
                width, height = page.get_width(), page.get_height()
                image = _render_page(page)
                text_page, text = _page_text(page)
                try:
                    if text.strip():
                        location = _digital_location(page_index)
                        for finding in grouped.get(location.id, ()):
                            boxes = _pixel_char_boxes(
                                text_page,
                                start=finding.start,
                                end=finding.end,
                                page_height=height,
                            )
                            _paint_boxes(
                                image,
                                boxes,
                                replacements.get(finding.group_id, finding.replacement),
                                secure=True,
                            )
                    else:
                        lines = _ocr_lines(image)
                        for line_index, (_, box) in enumerate(lines):
                            location = _ocr_location(page_index, line_index)
                            selected = grouped.get(location.id, ())
                            if not selected:
                                continue
                            tokens = list(
                                dict.fromkeys(
                                    replacements.get(item.group_id, item.replacement)
                                    for item in selected
                                )
                            )
                            _paint_boxes(
                                image,
                                [box],
                                " ".join(tokens),
                                secure=True,
                            )
                finally:
                    text_page.close()
                    page.close()
                rendered.append((image, width, height))
        finally:
            document.close()
        return _images_to_pdf(rendered)

    def verify(
        self,
        document_bytes: bytes,
        applied_findings: Iterable[Finding],
    ) -> tuple[TextBlock, ...]:
        applied = tuple(applied_findings)
        blocks, issues = self.extract(document_bytes)
        if issues:
            raise ValueError("La copia PDF contiene páginas no inspeccionables.")
        searchable = "\n".join(block.text for block in blocks).casefold()
        if any(finding.value.casefold() in searchable for finding in applied):
            raise ValueError(
                "La verificación posterior ha encontrado valores seleccionados sin sustituir."
            )
        reader = PdfReader(io.BytesIO(document_bytes))
        root = reader.trailer["/Root"]
        if root.get("/AcroForm") or root.get("/EmbeddedFiles"):
            raise ValueError("La copia PDF conserva formularios o adjuntos.")
        raw = document_bytes.lower()
        if any(finding.value.encode("utf-8", errors="ignore").lower() in raw for finding in applied):
            raise ValueError("La copia PDF conserva un valor sensible en su estructura.")
        return blocks


def render_pdf_template(
    template_bytes: bytes,
    context: Mapping[str, object],
) -> bytes:
    document = _open_pdf(template_bytes)
    rendered: list[tuple[Image.Image, float, float]] = []
    try:
        for page_index in range(len(document)):
            page = document[page_index]
            width, height = page.get_width(), page.get_height()
            image = _render_page(page)
            text_page, text = _page_text(page)
            try:
                if text.strip():
                    for match in reversed(list(VARIABLE_PATTERN.finditer(text))):
                        boxes = _pixel_char_boxes(
                            text_page,
                            start=match.start(),
                            end=match.end(),
                            page_height=height,
                        )
                        _paint_boxes(
                            image,
                            boxes,
                            str(context.get(match.group(1), "")),
                            secure=False,
                        )
                else:
                    for line_text, box in _ocr_lines(image):
                        matches = list(VARIABLE_PATTERN.finditer(line_text))
                        if matches:
                            values = [
                                str(context.get(match.group(1), ""))
                                for match in matches
                            ]
                            _paint_boxes(image, [box], " ".join(values), secure=False)
            finally:
                text_page.close()
                page.close()
            rendered.append((image, width, height))
    finally:
        document.close()
    return _images_to_pdf(rendered)
