from decimal import Decimal

import pytest

from finance_imputer.extractors.docling_poc import (
    DoclingPocExtractionError,
    DoclingPocExtractor,
    ExtractedPagePayload,
    assemble_invoice_draft,
    parse_decimal,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.234,56 €", Decimal("1234.56")),
        ("$1,234.56", Decimal("1234.56")),
        ("0,4900 EUR", Decimal("0.4900")),
        ("(42,50)", Decimal("-42.50")),
        (21, Decimal("21")),
        (None, None),
    ],
)
def test_parse_decimal_handles_invoice_formats(raw, expected):
    assert parse_decimal(raw) == expected


def test_assemble_invoice_draft_combines_pages_and_reconciles_totals():
    pages = [
        ExtractedPagePayload(
            page_no=1,
            extracted_data={
                "supplier_name": "Proveedor Demo, S.L.",
                "supplier_tax_id": "B12345678",
                "invoice_number": "F-2026-0042",
                "invoice_date": "2026-08-31",
                "customer_code": "C-001",
                "customer_name": "Cliente Demo, S.L.",
                "currency": "eur",
                "taxable_base": "53,63",
                "tax_amount": "11,26",
                "invoice_total": "64,89",
                "taxes": [
                    {
                        "tax_type": "IVA",
                        "tax_rate": "21",
                        "taxable_base": "53,63",
                        "tax_amount": "11,26",
                    }
                ],
                "line_items": [
                    {
                        "description": "Servicio A",
                        "project_reference": "18491",
                        "quantity": "2",
                        "unit_price": "0,49",
                        "amount": "0,98",
                    },
                    {
                        "description": "Servicio B",
                        "quantity": "1",
                        "unit_price": "17,15",
                        "amount": "17,15",
                    },
                ],
            },
        ),
        ExtractedPagePayload(
            page_no=2,
            extracted_data={
                "supplier_name": "Proveedor Demo, S.L.",
                "invoice_number": "F-2026-0042",
                "taxes": [
                    {
                        "tax_type": "IVA",
                        "rate": "21",
                        "taxable_base": "53.63",
                        "amount": "11.26",
                    }
                ],
                "line_items": [
                    {
                        "description": "Servicio C",
                        "quantity": "1",
                        "unit_price": "35,50",
                        "amount": "35,50",
                    }
                ],
            },
        ),
    ]

    draft = assemble_invoice_draft(pages, source_name="factura.pdf")

    assert draft.pages_processed == 2
    assert len(draft.lines) == 3
    assert draft.currency == "EUR"
    assert draft.lines[0].project_reference == "18491"
    assert draft.validation.line_total == Decimal("53.63")
    assert draft.validation.line_total_matches_taxable_base is True
    assert draft.validation.taxable_base_plus_tax_matches_total is True
    assert draft.validation.ready_for_mapping is True
    assert len(draft.taxes) == 1


def test_assemble_invoice_draft_reports_conflicts_and_partial_lines():
    pages = [
        ExtractedPagePayload(
            page_no=1,
            extracted_data={
                "supplier_name": "Proveedor Demo",
                "invoice_number": "A-1",
                "invoice_date": "2026-09-01",
                "taxable_base": "10,00",
                "tax_amount": "2,10",
                "invoice_total": "12,10",
                "line_items": [{"description": "Sin importe", "quantity": "1"}],
            },
        ),
        ExtractedPagePayload(
            page_no=2,
            extracted_data={"invoice_number": "A-7"},
            errors=("La página se procesó parcialmente",),
        ),
    ]

    draft = assemble_invoice_draft(pages, source_name="conflictiva.pdf")

    assert draft.validation.ready_for_mapping is False
    assert draft.validation.pending_line_count == 1
    assert any("contradictorios" in warning for warning in draft.warnings)
    assert any("parcial" in warning for warning in draft.warnings)


def test_assemble_invoice_draft_uses_raw_json_fallback_and_aliases():
    page = ExtractedPagePayload(
        page_no=1,
        raw_text='''{
          "provider": "Proveedor alternativo",
          "invoice_number": "X-9",
          "invoice_date": "2026-08-30",
          "customer_code": "C-9",
          "customer_name": "Cliente alternativo",
          "subtotal": "5.00",
          "tax_rate": "21",
          "vat_amount": "1.05",
          "total": "6.05",
          "lines": [
            {"service": "Concepto", "reference": "00010533182", "quantity": "1", "unit_price": "5", "amount": "5"}
          ]
        }''',
    )

    draft = assemble_invoice_draft([page], source_name="raw.pdf")

    assert draft.supplier_name == "Proveedor alternativo"
    assert draft.lines[0].project_reference == "00010533182"
    assert draft.validation.ready_for_mapping is True


def test_tax_summary_can_supply_missing_top_level_tax_values():
    page = ExtractedPagePayload(
        page_no=1,
        extracted_data={
            "supplier_name": "Proveedor",
            "invoice_number": "T-1",
            "invoice_date": "2026-09-01",
            "customer_code": "C-1",
            "customer_name": "Cliente",
            "invoice_total": "121",
            "taxes": [
                {"tax_type": "IVA", "rate": "21", "taxable_base": "100", "amount": "21"}
            ],
            "line_items": [
                {"description": "Servicio", "quantity": "1", "unit_price": "100", "amount": "100"}
            ],
        },
    )

    draft = assemble_invoice_draft([page], source_name="tax.pdf")

    assert draft.taxable_base == Decimal("100")
    assert draft.tax_rate == Decimal("21")
    assert draft.tax_amount == Decimal("21")
    assert draft.validation.ready_for_mapping is True


def test_non_pdf_is_rejected_before_docling_is_imported():
    extractor = DoclingPocExtractor()

    with pytest.raises(DoclingPocExtractionError, match="PDF"):
        extractor.extract_bytes(b"not a pdf", filename="factura.pdf")
