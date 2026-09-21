from __future__ import annotations

import os


TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


class FeatureDisabledError(ValueError):
    """Raised when a valid document targets a disabled deployment feature."""


def _enabled(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in TRUE_VALUES


def pdf_enabled() -> bool:
    return _enabled("SMARTDOCS_FEATURE_PDF")


def image_ocr_enabled() -> bool:
    return _enabled("SMARTDOCS_FEATURE_IMAGE_OCR")


def webadmin_enabled() -> bool:
    return _enabled("SMARTDOCS_FEATURE_WEBADMIN")


def document_format_enabled(document_format: str) -> bool:
    return document_format != "pdf" or pdf_enabled()


def require_document_format_enabled(document_format: str) -> None:
    if document_format_enabled(document_format):
        return
    raise FeatureDisabledError(
        "El formato PDF estará disponible en una fase posterior."
    )


def feature_snapshot() -> dict[str, bool]:
    return {
        "pdf": pdf_enabled(),
        "image_ocr": image_ocr_enabled(),
        "webadmin": webadmin_enabled(),
    }
