import os
from urllib.parse import quote

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from apps.api.anonymizer_api import router as anonymizer_router

from apps.api.schemas import (
    ApplyAnonymizationRequest,
    GenerateDocumentRequest,
)
from apps.api.store import InMemoryJobStore, JobNotFoundError
from docgen.anonymizer.service import (
    analyze_document,
    anonymize_document,
    summarize_findings,
)
from docgen.autofix import autofix_split_placeholders
from docgen.config import fixed_filename, generated_filename
from docgen.document_formats import (
    detect_document_format,
    mime_type_for,
    validate_document,
)
from docgen.feature_flags import FeatureDisabledError
from docgen.renderer import render_document
from docgen.template_service import TemplateAnalysis, analyze_template

MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_EXPANDED_BYTES = 60 * 1024 * 1024
MVP_LIMITATIONS = (
    "El despliegue de fase 1 admite DOCX y PPTX.",
    "PDF y lectura OCR de imágenes permanecen deshabilitados mediante feature flags.",
    "La descarga avanzada sanea contenido oculto y verifica el resultado.",
)

app = FastAPI(
    title="SmartDocs API",
    version="0.1.0",
    description="Document generation and human-reviewed anonymization.",
)
store = InMemoryJobStore(ttl_minutes=30)

default_origins = "http://localhost:3050,http://127.0.0.1:3050"
allowed_origins = [
    origin.strip()
    for origin in os.getenv("SMARTDOCS_ALLOWED_ORIGINS", default_origins).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(anonymizer_router)


async def _read_upload(upload: UploadFile) -> tuple[str, bytes]:
    content = await upload.read(MAX_FILE_BYTES + 1)
    await upload.close()

    if not content:
        raise HTTPException(status_code=400, detail="El documento está vacío.")
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="El documento supera el límite de 15 MB del MVP.",
        )
    try:
        filename, _ = validate_document(
            upload.filename,
            content,
            max_expanded_bytes=MAX_EXPANDED_BYTES,
        )
    except OverflowError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except FeatureDisabledError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except ValueError as exc:
        status = 415 if "formato no es compatible" in str(exc) else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return filename, content


def _download_response(content: bytes, filename: str) -> Response:
    encoded_name = quote(filename)
    return Response(
        content=content,
        media_type=mime_type_for(detect_document_format(content)),
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{encoded_name}"
            )
        },
    )


def _serialize_template_analysis(
    analysis: TemplateAnalysis,
) -> dict[str, object]:
    return {
        "ready": analysis.is_ready,
        "document_format": analysis.document_format,
        "variables": list(analysis.variables),
        "issues": [
            {
                "location": issue.location,
                "variable": issue.variable,
                "paragraph_preview": issue.paragraph_preview,
                "run_texts": list(issue.run_texts),
            }
            for issue in analysis.issues
        ],
    }


def _generator_job(job_id: str):
    try:
        return store.get(job_id, "generator")
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="La sesión de generación ya no existe o ha caducado.",
        ) from exc


def _anonymizer_job(job_id: str):
    try:
        return store.get(job_id, "anonymizer")
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="La sesión de anonimización ya no existe o ha caducado.",
        ) from exc


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "smartdocs-api"}


@app.post("/api/legacy-anonymizer/analyze", include_in_schema=False)
async def analyze_for_anonymization(
    file: UploadFile = File(...),
) -> dict[str, object]:
    filename, content = await _read_upload(file)
    try:
        findings = analyze_document(content)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="No se ha podido leer el documento Word.",
        ) from exc

    job = store.create(
        kind="anonymizer",
        source_name=filename,
        source_bytes=content,
        findings=findings,
    )
    return {
        "job_id": job.id,
        "filename": filename,
        "expires_in_minutes": store.ttl_minutes,
        "findings": [finding.to_dict() for finding in findings],
        "summary": summarize_findings(findings),
        "limitations": list(MVP_LIMITATIONS),
    }


@app.post("/api/legacy-anonymizer/{job_id}/apply", include_in_schema=False)
def apply_anonymization(
    job_id: str,
    request: ApplyAnonymizationRequest,
) -> dict[str, object]:
    job = _anonymizer_job(job_id)
    findings_by_id = {finding.id: finding for finding in job.findings}
    selected = []
    replacements: dict[str, str] = {}

    for decision in request.decisions:
        finding = findings_by_id.get(decision.finding_id)
        if finding is None:
            raise HTTPException(
                status_code=400,
                detail="La selección contiene un hallazgo desconocido.",
            )
        selected.append(finding)
        if decision.replacement is not None:
            replacements[finding.id] = decision.replacement

    try:
        output = anonymize_document(
            job.source_bytes,
            selected,
            replacements,
        )
        remaining = analyze_document(output)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    source = Path(job.source_name)
    job.output_name = f"{source.stem}_anonimizado.docx"
    job.output_bytes = output
    job.metadata["applied_count"] = len(selected)
    job.metadata["remaining_count"] = len(remaining)

    return {
        "job_id": job.id,
        "applied_count": len(selected),
        "remaining_count": len(remaining),
        "download_url": f"/api/anonymizer/{job.id}/download",
        "filename": job.output_name,
    }


@app.get("/api/legacy-anonymizer/{job_id}/download", include_in_schema=False)
def download_anonymized(job_id: str) -> Response:
    job = _anonymizer_job(job_id)
    if job.output_bytes is None or job.output_name is None:
        raise HTTPException(
            status_code=409,
            detail="Todavía no se ha generado el documento anonimizado.",
        )
    return _download_response(job.output_bytes, job.output_name)


@app.post("/api/generator/analyze")
async def analyze_for_generation(
    file: UploadFile = File(...),
) -> dict[str, object]:
    filename, content = await _read_upload(file)
    try:
        analysis = analyze_template(content)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="No se ha podido leer la plantilla DOCX, PDF o PPTX.",
        ) from exc

    job = store.create(
        kind="generator",
        source_name=filename,
        source_bytes=content,
        template_analysis=analysis,
    )
    return {
        "job_id": job.id,
        "filename": filename,
        "expires_in_minutes": store.ttl_minutes,
        **_serialize_template_analysis(analysis),
    }


@app.post("/api/generator/{job_id}/repair")
def repair_template(job_id: str) -> dict[str, object]:
    job = _generator_job(job_id)
    analysis = job.template_analysis or analyze_template(job.source_bytes)
    if analysis.document_format != "docx":
        raise HTTPException(
            status_code=409,
            detail="La reparación automática de variables partidas solo aplica a DOCX.",
        )
    fixed_bytes, merge_count = autofix_split_placeholders(job.source_bytes)
    analysis = analyze_template(fixed_bytes)
    job.source_bytes = fixed_bytes
    job.template_analysis = analysis
    job.output_bytes = None
    job.output_name = None

    return {
        "job_id": job.id,
        "filename": job.source_name,
        "expires_in_minutes": store.ttl_minutes,
        "merge_count": merge_count,
        "fixed_filename": fixed_filename(job.source_name),
        **_serialize_template_analysis(analysis),
    }


@app.post("/api/generator/{job_id}/generate")
def generate_document(
    job_id: str,
    request: GenerateDocumentRequest,
) -> dict[str, object]:
    job = _generator_job(job_id)
    analysis = job.template_analysis or analyze_template(job.source_bytes)

    if analysis.issues:
        raise HTTPException(
            status_code=409,
            detail="La plantilla debe repararse antes de generar el documento.",
        )
    if not analysis.variables:
        raise HTTPException(
            status_code=409,
            detail="La plantilla no contiene variables compatibles.",
        )

    context = {
        variable: request.context.get(variable, "")
        for variable in analysis.variables
    }
    try:
        job.output_bytes = render_document(job.source_bytes, context)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="No se ha podido generar el documento.",
        ) from exc

    job.output_name = generated_filename(job.source_name)
    return {
        "job_id": job.id,
        "filename": job.output_name,
        "download_url": f"/api/generator/{job.id}/download",
    }


@app.get("/api/generator/{job_id}/download")
def download_generated(job_id: str) -> Response:
    job = _generator_job(job_id)
    if job.output_bytes is None or job.output_name is None:
        raise HTTPException(
            status_code=409,
            detail="Todavía no se ha generado el documento.",
        )
    return _download_response(job.output_bytes, job.output_name)
