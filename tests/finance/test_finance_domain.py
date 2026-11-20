from io import BytesIO
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook

from finance_imputer.excel_export import build_excel
from finance_imputer.extractors.generic import _flat_lines, _grouped_lines
from finance_imputer.models import InvoiceAnalysis
from finance_imputer.provider_profiles import ProviderCatalog, ProviderProfile
from finance_imputer.reconciliation import reconcile


DETAIL = """
Usuario Descripción Cantidad Precio Importe
asesores@rsm 198,87 EUR
FACTURA CERTIFICADA 2,00 0,98 EUR
Certificado 2,00 0,4900 EUR 0,98 EUR
E-MAIL CERTIFICADO 35,00 17,15 EUR
Certificado 35,00 0,4900 EUR 17,15 EUR
mcapel@rsm 62,48 EUR
CLICK&SIGN BASE 71,00 35,50 EUR
Unidad 71,00 0,5000 EUR 35,50 EUR
"""


def _lines():
    project_dir = Path(__file__).resolve().parents[2]
    catalog = ProviderCatalog(
        project_dir / "provider_profiles", project_dir / "data" / "providers"
    )
    profile = catalog.get("lleidanet").profile
    return _grouped_lines(DETAIL, profile)


def test_extracts_one_line_per_user_and_service() -> None:
    lines = _lines()
    assert len(lines) == 3
    assert lines[0].user == "asesores@rsm"
    assert lines[0].service == "FACTURA CERTIFICADA"
    assert lines[2].user == "mcapel@rsm"
    assert lines[2].unit_price == Decimal("0.5000")
    assert all(line.project_reference == "" for line in lines)


def test_flat_profile_extracts_project_reference_from_context_or_row() -> None:
    project_dir = Path(__file__).resolve().parents[2]
    catalog = ProviderCatalog(
        project_dir / "provider_profiles",
        project_dir / "data" / "providers",
    )
    payload = catalog.get("lleidanet").profile.model_dump()
    payload["id"] = "referencias-demo"
    payload["name"] = "Referencias demo"
    payload["lines"] = {
        "mode": "flat",
        "page": 0,
        "project_reference_pattern": (
            r"Ref:\s*(?:proyecto\s+)?(?P<project_reference>\d+)"
        ),
        "row_pattern": (
            r"^(?:(?P<project_reference>\d+)\|)?"
            r"(?P<service>[^|]+)\|(?P<quantity>[\d.,]+)\|"
            r"(?P<unit_price>[\d.,]+)\|(?P<amount>[\d.,]+)$"
        ),
    }
    profile = ProviderProfile.model_validate(payload)

    lines = _flat_lines(
        "Ref: proyecto 18491\nNota simple|1|7,18|7,18\n"
        "00010533182|Viaje|1|32,90|32,90",
        profile,
    )

    assert [line.project_reference for line in lines] == [
        "18491",
        "00010533182",
    ]


def test_excel_exports_project_reference_as_its_own_column() -> None:
    line = _lines()[0].updated(project_reference="18491", status="accepted")
    analysis = InvoiceAnalysis(
        provider="Proveedor demo",
        invoice_number="F-1",
        invoice_date="01/10/2026",
        customer_code="C-1",
        customer_name="Cliente demo",
        taxable_base=line.amount,
        tax_rate=Decimal("21"),
        tax_amount=Decimal("0.21"),
        invoice_total=line.amount + Decimal("0.21"),
        lines=(line,),
    )

    workbook = load_workbook(BytesIO(build_excel(analysis, [line])))
    sheet = workbook["Detalle"]

    assert sheet["C8"].value == "REFERENCIA PROYECTO"
    assert sheet["C9"].value == "18491"


def test_reconciliation_is_dynamic_and_percentage_based() -> None:
    lines = _lines()
    result = reconcile(list(lines), Decimal("53.63"))
    assert result.matches
    assert result.absolute_difference == Decimal("0.00")
    assert result.percentage_difference == Decimal("0")


def test_reconciliation_flags_a_relative_difference() -> None:
    lines = _lines()
    result = reconcile(list(lines), Decimal("54.00"), Decimal("0.10"))
    assert not result.matches
    assert result.absolute_difference == Decimal("0.37")
    assert result.percentage_difference > Decimal("0.10")


def test_provider_can_be_added_as_configuration(tmp_path: Path) -> None:
    project_dir = Path(__file__).resolve().parents[2]
    catalog = ProviderCatalog(project_dir / "provider_profiles", tmp_path)
    base = catalog.get("lleidanet").profile.model_copy(
        update={"id": "proveedor-demo", "name": "Proveedor demo"}
    )

    catalog.save(base)

    saved = catalog.get("proveedor-demo")
    assert not saved.built_in
    assert saved.profile.name == "Proveedor demo"


def test_provider_id_cannot_escape_its_directory() -> None:
    project_dir = Path(__file__).resolve().parents[2]
    catalog = ProviderCatalog(project_dir / "provider_profiles", project_dir / "data")
    payload = catalog.get("lleidanet").profile.model_dump()
    payload["id"] = "../fuera"
    with pytest.raises(ValueError):
        ProviderProfile.model_validate(payload)
