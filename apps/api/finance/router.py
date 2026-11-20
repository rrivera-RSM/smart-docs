"""FastAPI routes and HTTP orchestration for Finance Imputer."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError

from apps.api import auth
from apps.api.finance.access_registry import observed_user_store
from apps.api.finance.config import api_settings
from apps.api.finance.schemas import ExportRequest, LineUpdate
from apps.api.finance.serializers import serialize_analysis, serialize_provider
from apps.api.finance.store import InMemoryInvoiceStore, InvoiceJob
from finance_imputer.excel_export import build_excel
from finance_imputer.extractors.registry import (
    UnsupportedInvoiceError,
    extract_invoice,
    test_profile,
)
from finance_imputer.models import InvoiceAnalysis
from finance_imputer.provider_profiles import (
    ProviderCatalog,
    ProviderProfile,
)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# SmartDocs mounts this router with its shared Entra ID dependency.
router = APIRouter(prefix="/api/finance", tags=["Finance"])
store = InMemoryInvoiceStore(ttl_minutes=60)
provider_catalog = ProviderCatalog.default()


def _analysis_payload(
    job_id: str,
    analysis: InvoiceAnalysis,
) -> dict[str, object]:
    return serialize_analysis(
        job_id,
        analysis,
        tolerance_percentage=api_settings.reconciliation_tolerance,
    )


def _get_job(job_id: str) -> InvoiceJob:
    try:
        return store.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def _read_pdf(upload: UploadFile) -> tuple[str, bytes]:
    filename = Path(upload.filename or "factura.pdf").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Solo se admiten archivos PDF.")
    content = await upload.read(api_settings.max_file_bytes + 1)
    await upload.close()
    if not content:
        raise HTTPException(status_code=400, detail="El PDF está vacío.")
    if len(content) > api_settings.max_file_bytes:
        raise HTTPException(status_code=413, detail="El PDF supera el límite de 15 MB.")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="El archivo no contiene un PDF válido.")
    return filename, content


def serialize_authenticated_user(request: Request) -> dict[str, object]:
    """Expose the identity already verified by SmartDocs' security dependency."""
    user = getattr(request.state, "user", None)
    if user is None:
        return {"authenticated": False}
    claims = user if isinstance(user, dict) else getattr(user, "claims", {})
    return {
        "authenticated": True,
        "name": claims.get("name", ""),
        "email": claims.get("preferred_username") or claims.get("email", ""),
        "oid": claims.get("oid", ""),
        "roles": claims.get("roles", []),
    }


@router.get("/me")
def current_user(request: Request) -> dict[str, object]:
    identity = serialize_authenticated_user(request)
    observed_user_store.observe(identity)
    return {
        **identity,
        "access_policy": "tenant",
        "allowed": True,
    }


@router.get("/admin/access-overview")
def access_overview() -> dict[str, object]:
    return {
        "policy": {
            "mode": "tenant",
            "auth_enabled": auth.AUTH_ENABLED,
            "tenant_configured": bool(auth.TENANT_ID),
            "additional_filtering": False,
            "allowed": "Cualquier cuenta autenticada del tenant corporativo.",
            "denied": "Cuentas no autenticadas o pertenecientes a otro tenant.",
        },
        "users": [
            {
                "email": user.email,
                "name": user.name,
                "first_seen_at": user.first_seen_at,
                "last_seen_at": user.last_seen_at,
                "status": "allowed",
            }
            for user in observed_user_store.list()
        ],
    }


@router.get("/providers")
def list_providers() -> dict[str, object]:
    return {
        "providers": [
            serialize_provider(definition) for definition in provider_catalog.list()
        ]
    }


@router.get("/providers/{provider_id}")
def get_provider(provider_id: str) -> dict[str, object]:
    try:
        definition = provider_catalog.get(provider_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        **serialize_provider(definition),
        "profile": definition.profile.model_dump(mode="json"),
    }


@router.post("/providers")
def save_provider(profile: ProviderProfile) -> dict[str, object]:
    try:
        definition = provider_catalog.save(profile)
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail="No se ha podido guardar el perfil."
        ) from exc
    return serialize_provider(definition)


@router.post("/providers/test")
async def test_provider(
    profile_json: str = Form(...), file: UploadFile = File(...)
) -> dict[str, object]:
    if len(profile_json.encode("utf-8")) > api_settings.max_profile_bytes:
        raise HTTPException(status_code=413, detail="El perfil supera el límite de 100 KB.")
    try:
        profile = ProviderProfile.model_validate_json(profile_json)
    except ValidationError as exc:
        first_error = exc.errors()[0]
        location = ".".join(str(part) for part in first_error.get("loc", []))
        raise HTTPException(
            status_code=422,
            detail=f"Perfil no válido en {location}: {first_error['msg']}",
        ) from exc
    _, content = await _read_pdf(file)
    try:
        analysis, detection_matches = test_profile(content, profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "detection_matches": detection_matches,
        "analysis": _analysis_payload("provider-preview", analysis),
    }


@router.post("/invoices/analyze")
async def analyze_invoice(file: UploadFile = File(...)) -> dict[str, object]:
    filename, content = await _read_pdf(file)
    try:
        analysis = extract_invoice(content, provider_catalog)
    except UnsupportedInvoiceError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail="No se ha podido leer la factura.") from exc
    job = store.create(filename, analysis)
    return _analysis_payload(job.id, analysis)


@router.get("/invoices/{job_id}")
def get_invoice(job_id: str) -> dict[str, object]:
    job = _get_job(job_id)
    return _analysis_payload(job.id, job.analysis)


@router.patch("/invoices/{job_id}/lines/{line_id}")
def update_line(job_id: str, line_id: str, request: LineUpdate) -> dict[str, object]:
    job = _get_job(job_id)
    line_index = next(
        (index for index, line in enumerate(job.analysis.lines) if line.id == line_id),
        None,
    )
    if line_index is None:
        raise HTTPException(status_code=404, detail="La línea no existe.")
    line = job.analysis.lines[line_index]
    payload = request.model_dump(exclude_none=True)
    for field in ("quantity", "unit_price", "amount"):
        if field in payload:
            payload[field] = Decimal(str(payload[field]))
    updated = line.updated(**payload)
    lines = list(job.analysis.lines)
    lines[line_index] = updated
    job.analysis = replace(job.analysis, lines=tuple(lines))
    return _analysis_payload(job.id, job.analysis)


@router.post("/invoices/{job_id}/accept-all")
def accept_all(job_id: str) -> dict[str, object]:
    job = _get_job(job_id)
    lines = tuple(line.updated(status="accepted") for line in job.analysis.lines)
    job.analysis = replace(job.analysis, lines=lines)
    return _analysis_payload(job.id, job.analysis)


@router.post("/invoices/{job_id}/export")
def export_invoice(job_id: str, request: ExportRequest) -> Response:
    job = _get_job(job_id)
    accepted = [line for line in job.analysis.lines if line.status == "accepted"]
    pending = [line for line in job.analysis.lines if line.status != "accepted"]
    if pending and not request.confirm_discard_pending:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "pending_lines",
                "count": len(pending),
                "message": "Hay líneas pendientes que se eliminarán al exportar.",
            },
        )
    if not accepted:
        raise HTTPException(status_code=409, detail="No hay líneas aceptadas para exportar.")

    job.analysis = replace(job.analysis, lines=tuple(accepted))
    content = build_excel(job.analysis, accepted)
    stem = Path(job.source_name).stem
    filename = f"{stem}_validado.xlsx"
    return Response(
        content=content,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


