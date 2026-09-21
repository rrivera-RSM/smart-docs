from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from conftest import FIXTURE_ROOT
from docgen.anonymizer.adapter_registry import DocumentAdapterRegistry
from docgen.anonymizer.pdf_adapter import PdfDocumentAdapter
from docgen.document_formats import validate_document
from docgen.feature_flags import (
    FeatureDisabledError,
    document_format_enabled,
    feature_snapshot,
)


def test_phase_one_disables_pdf_and_image_ocr_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SMARTDOCS_FEATURE_PDF", raising=False)
    monkeypatch.delenv("SMARTDOCS_FEATURE_IMAGE_OCR", raising=False)
    monkeypatch.delenv("SMARTDOCS_FEATURE_WEBADMIN", raising=False)

    assert feature_snapshot() == {
        "pdf": False,
        "image_ocr": False,
        "webadmin": False,
    }
    assert document_format_enabled("docx")
    assert document_format_enabled("pptx")
    assert not document_format_enabled("pdf")


def test_pdf_validation_fails_closed_when_feature_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMARTDOCS_FEATURE_PDF", "false")
    source = (FIXTURE_ROOT / "anonymizer" / "factura_proveedor.pdf").read_bytes()

    with pytest.raises(FeatureDisabledError, match="fase posterior"):
        validate_document(
            "factura_proveedor.pdf",
            source,
            max_expanded_bytes=60 * 1024 * 1024,
        )


def test_capabilities_keep_phase_two_visible_but_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMARTDOCS_FEATURE_PDF", "false")
    formats = {
        item["id"]: item
        for item in DocumentAdapterRegistry().capabilities()
    }

    assert formats["docx"]["enabled"] is True
    assert formats["pptx"]["enabled"] is True
    assert formats["pdf"]["enabled"] is False
    assert formats["pdf"]["reason"] == "Disponible en una fase posterior."


def test_scanned_pdf_does_not_run_ocr_when_image_feature_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMARTDOCS_FEATURE_PDF", "true")
    monkeypatch.setenv("SMARTDOCS_FEATURE_IMAGE_OCR", "false")
    source = (
        FIXTURE_ROOT / "anonymizer" / "formulario_alta_escaneado.pdf"
    ).read_bytes()

    blocks, issues = PdfDocumentAdapter().extract(source)

    assert not blocks
    assert {issue.kind for issue in issues} == {"image_ocr_disabled"}
    assert all(issue.blocking and not issue.removable for issue in issues)


def test_api_rejects_pdf_when_phase_two_is_disabled(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMARTDOCS_FEATURE_PDF", "false")
    path = FIXTURE_ROOT / "anonymizer" / "factura_proveedor.pdf"

    response = api_client.post(
        "/api/anonymizer/analyze",
        files={"file": (path.name, path.read_bytes(), "application/pdf")},
    )

    assert response.status_code == 415
    assert "fase posterior" in response.json()["detail"]
