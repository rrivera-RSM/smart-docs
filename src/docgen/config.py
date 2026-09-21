from pathlib import Path

from docgen.document_formats import (
    FORMAT_SPECS,
    detect_document_format,
    output_filename,
)

APP_NAME = "Smart Docs"
APP_DESCRIPTION = "Generación de documentos a partir de plantillas Word"
DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
PDF_MIME = FORMAT_SPECS["pdf"].mime_type
PPTX_MIME = FORMAT_SPECS["pptx"].mime_type

PACKAGE_DIR = Path(__file__).resolve().parent
LOGO_PATH = PACKAGE_DIR / "assets" / "rsm_logo.png"


def format_variable_label(variable: str) -> str:
    """Convert a snake_case template variable into a readable form label."""
    return variable.replace("_", " ").strip().capitalize()


def generated_filename(source_name: str) -> str:
    return output_filename(source_name, "generado")


def fixed_filename(source_name: str) -> str:
    return output_filename(source_name, "reparada")
