"""Finance workflows mounted on the shared SmartDocs API."""

from importlib import import_module
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from reportlab.pdfgen.canvas import Canvas

from apps.api.auth import require_azure_user
from apps.api.finance.access_registry import ObservedUserStore
from apps.api.finance.store import InMemoryInvoiceStore
from apps.api.main import app
from finance_imputer.provider_profiles import ProviderCatalog

finance = import_module("apps.api.finance.router")


@pytest.fixture
def client(tmp_path, monkeypatch):
    catalog = ProviderCatalog(Path(__file__).resolve().parents[2] / "provider_profiles", tmp_path / "providers")
    monkeypatch.setattr(finance, "provider_catalog", catalog)
    monkeypatch.setattr(finance, "store", InMemoryInvoiceStore())
    monkeypatch.setattr(finance, "observed_user_store", ObservedUserStore(tmp_path / "users.json"))
    with TestClient(app) as value:
        yield value


def test_finance_provider_routes_are_namespaced(client):
    response = client.get("/api/finance/providers")
    assert response.status_code == 200
    assert response.json()["providers"][0]["id"] == "lleidanet"
    assert client.get("/api/providers").status_code == 404
    assert client.get("/api/health").json()["service"] == "smartdocs-api"


def test_finance_rejects_non_pdf(client):
    response = client.post("/api/finance/invoices/analyze", files={"file": ("invoice.txt", b"invalid", "text/plain")})
    assert response.status_code == 415


@pytest.mark.parametrize("path", ["/providers", "/me", "/admin/access-overview", "/invoices/missing"])
def test_finance_uses_shared_auth_dependency(client, path):
    async def denied():
        raise HTTPException(status_code=401, detail="Authentication required")

    app.dependency_overrides[require_azure_user] = denied
    try:
        assert client.get("/api/finance" + path).status_code == 401
    finally:
        app.dependency_overrides.pop(require_azure_user, None)


def test_finance_observes_shared_identity(client):
    async def identity(request: Request):
        request.state.user = {"oid": "test-user", "name": "Persona", "preferred_username": "PERSONA@example.test"}

    app.dependency_overrides[require_azure_user] = identity
    try:
        response = client.get("/api/finance/me")
        assert response.json()["authenticated"] is True
        overview = client.get("/api/finance/admin/access-overview").json()
        assert overview["policy"]["additional_filtering"] is False
        assert overview["users"][0]["email"] == "persona@example.test"
    finally:
        app.dependency_overrides.pop(require_azure_user, None)


def test_digital_pdf_profile_moderation_and_excel(client):
    profile = {
        "id": "migration-demo", "name": "Migration Demo",
        "detection": {"all_terms": ["Migration Demo"]},
        "header": {
            "invoice_number": {"pattern": r"Invoice: (?P<value>\S+)"},
            "invoice_date": {"pattern": r"Date: (?P<value>\S+)"},
            "taxable_base": {"pattern": r"Base: (?P<value>[\d.,]+)"},
            "invoice_total": {"pattern": r"Total: (?P<value>[\d.,]+)"},
        },
        "lines": {
            "mode": "flat", "page": 0,
            "row_pattern": r"^(?P<project_reference>\d+)\|(?P<service>[^|]+)\|(?P<quantity>[\d.,]+)\|(?P<unit_price>[\d.,]+)\|(?P<amount>[\d.,]+)$",
        },
    }
    assert client.post("/api/finance/providers", json=profile).status_code == 200
    saved = client.get("/api/finance/providers/migration-demo").json()
    assert saved["built_in"] is False
    buffer = BytesIO()
    pdf = Canvas(buffer)
    for row, text in enumerate([
        "Migration Demo", "Invoice: DEMO-1", "Date: 16/11/2026", "Base: 30,00", "Total: 30,00",
        "00010533182|Travel|1|10,00|10,00", "18491|Courier|1|20,00|20,00",
    ]):
        pdf.drawString(60, 780 - row * 22, text)
    pdf.save()
    response = client.post("/api/finance/invoices/analyze", files={"file": ("demo.pdf", buffer.getvalue(), "application/pdf")})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["reconciliation"]["matches"] is True
    assert payload["lines"][0]["project_reference"] == "00010533182"
    job_path = "/api/finance/invoices/" + payload["job_id"]
    assert client.get(job_path).status_code == 200
    update = client.patch(job_path + "/lines/" + payload["lines"][0]["id"], json={"status": "accepted", "comment": "Reviewed"})
    assert update.status_code == 200
    assert client.post(job_path + "/export", json={}).status_code == 409
    exported = client.post(job_path + "/export", json={"confirm_discard_pending": True})
    assert exported.status_code == 200
    assert "demo_validado.xlsx" in exported.headers["content-disposition"]
    sheet = load_workbook(BytesIO(exported.content))["Detalle"]
    assert sheet["C9"].value == "00010533182"
    assert len(client.get(job_path).json()["lines"]) == 1
    assert client.post(job_path + "/accept-all").status_code == 200
