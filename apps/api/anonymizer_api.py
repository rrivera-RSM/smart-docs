from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Literal
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError

from docgen.anonymizer.engine import ModelUnavailableError
from docgen.anonymizer.models import AnalysisOptions, DocumentAnalysis, JobStatus
from docgen.anonymizer.verified_engine import VerifiedLocalAnonymizerEngine
from docgen.document_formats import (
    DocumentFormat,
    detect_document_format,
    mime_type_for,
    output_filename,
    validate_document,
)
from docgen.feature_flags import FeatureDisabledError, image_ocr_enabled, pdf_enabled
from apps.api.anonymizer_schemas import AnonymizerJobResponse, CapabilitiesResponse

MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_EXPANDED_BYTES = 60 * 1024 * 1024
TTL_MINUTES = 30


class AnalysisOptionsPayload(BaseModel):
    profile: Literal["maximum"] = "maximum"
    enabled_categories: list[str] = Field(default_factory=list, max_length=50)
    allowlist: list[str] = Field(default_factory=list, max_length=100)


class GroupDecision(BaseModel):
    group_id: str = Field(min_length=1, max_length=64)
    action: Literal["replace", "keep"] = "replace"
    replacement: str | None = Field(default=None, min_length=1, max_length=40)


class ApplyRequest(BaseModel):
    decisions: list[GroupDecision] = Field(min_length=1)
    review_confirmed: bool = False
    remove_unsupported_content: bool = False


class ManualFindingRequest(BaseModel):
    block_id: str = Field(min_length=1, max_length=240)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    entity_type: str = Field(min_length=1, max_length=64)
    all_occurrences: bool = True


@dataclass
class AnonymizerJob:
    id: str
    source_name: str
    source_bytes: bytes
    created_at: datetime
    expires_at: datetime
    options: AnalysisOptions
    document_format: DocumentFormat
    status: JobStatus = "queued"
    progress: int = 0
    analysis: DocumentAnalysis | None = None
    output_bytes: bytes | None = None
    output_name: str | None = None
    error: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class AnonymizerJobStore:
    def __init__(self, ttl_minutes: int = TTL_MINUTES) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._jobs: dict[str, AnonymizerJob] = {}
        self._lock = RLock()

    @staticmethod
    def _scrub(job: AnonymizerJob) -> None:
        job.source_name = ""
        job.source_bytes = b""
        job.analysis = None
        job.output_bytes = None
        job.output_name = None
        job.metadata.clear()

    def _cleanup(self) -> None:
        now = datetime.now(UTC)
        for job_id in [key for key, job in self._jobs.items() if job.expires_at <= now]:
            job = self._jobs.pop(job_id)
            self._scrub(job)

    def create(
        self,
        *,
        source_name: str,
        source_bytes: bytes,
        options: AnalysisOptions,
        document_format: DocumentFormat | None = None,
    ) -> AnonymizerJob:
        with self._lock:
            self._cleanup()
            now = datetime.now(UTC)
            job = AnonymizerJob(
                id=uuid4().hex,
                source_name=source_name,
                source_bytes=source_bytes,
                created_at=now,
                expires_at=now + self._ttl,
                options=options,
                document_format=document_format or (
                    "pdf"
                    if source_name.casefold().endswith(".pdf")
                    else "pptx"
                    if source_name.casefold().endswith(".pptx")
                    else "docx"
                ),
            )
            self._jobs[job.id] = job
            return job

    def get(self, job_id: str) -> AnonymizerJob:
        with self._lock:
            self._cleanup()
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            return job

    def delete(self, job_id: str) -> bool:
        with self._lock:
            self._cleanup()
            job = self._jobs.pop(job_id, None)
            if job is None:
                return False
            self._scrub(job)
            return True

    def state(self, job_id: str, *, status: JobStatus, progress: int, error: str | None = None) -> AnonymizerJob:
        with self._lock:
            job = self.get(job_id)
            job.status = status
            job.progress = max(0, min(100, progress))
            job.error = error
            return job


router = APIRouter(prefix="/api/anonymizer", tags=["anonymizer"])
job_store = AnonymizerJobStore()
anonymizer_engine = VerifiedLocalAnonymizerEngine()
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="smartdocs-anonymizer")

def _limitations() -> tuple[str, ...]:
    limitations = [
        "Procesamiento local y efímero; no se envía texto a servicios externos.",
        "En PPTX, imágenes, gráficos, objetos incrustados y firmas deben eliminarse.",
        "La revisión humana es obligatoria: ningún detector garantiza cobertura absoluta.",
    ]
    if not pdf_enabled():
        limitations.insert(1, "PDF está deshabilitado en este despliegue de fase 1.")
    elif image_ocr_enabled():
        limitations.insert(1, "PDF escaneado se inspecciona mediante OCR local.")
    else:
        limitations.insert(1, "PDF escaneado y lectura de imágenes están deshabilitados.")
    return tuple(limitations)


async def _read_upload(upload: UploadFile) -> tuple[str, bytes, DocumentFormat]:
    content = await upload.read(MAX_FILE_BYTES + 1)
    await upload.close()
    if not content:
        raise HTTPException(status_code=400, detail="El documento está vacío.")
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="El documento supera el límite de 15 MB.")
    try:
        filename, document_format = validate_document(
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
    return filename, content, document_format


def _get_job(job_id: str) -> AnonymizerJob:
    try:
        return job_store.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="La sesión de anonimización ya no existe o ha caducado.") from exc


def _serialize(job: AnonymizerJob) -> dict[str, object]:
    payload: dict[str, object] = {
        "job_id": job.id,
        "filename": job.source_name,
        "document_format": job.document_format,
        "status": job.status,
        "progress": job.progress,
        "error": job.error,
        "expires_in_minutes": TTL_MINUTES,
        "limitations": list(_limitations()),
        "findings": [],
        "groups": [],
        "blocks": [],
        "coverage_issues": [],
        "summary": {},
    }
    if job.analysis is not None:
        payload.update({
            "findings": [item.to_dict() for item in job.analysis.findings],
            "groups": [item.to_dict() for item in job.analysis.groups],
            "blocks": [item.to_dict() for item in job.analysis.blocks],
            "coverage_issues": [item.to_dict() for item in job.analysis.coverage_issues],
            "summary": job.analysis.summary,
        })
    if job.output_bytes is not None and job.output_name is not None:
        payload.update({
            "applied_count": job.metadata.get("applied_count", 0),
            "remaining_count": job.metadata.get("remaining_count", 0),
            "download_url": f"/api/anonymizer/{job.id}/download",
            "output_filename": job.output_name,
        })
    return payload


def _run_analysis(job_id: str) -> None:
    try:
        job = job_store.state(job_id, status="extracting", progress=12)
        job_store.state(job_id, status="detecting", progress=38)
        job.analysis = anonymizer_engine.analyze(job.source_bytes, job.options)
        job_store.state(job_id, status="review_ready", progress=100)
    except Exception as exc:
        try:
            job_store.state(job_id, status="failed", progress=100, error="No se ha podido completar el análisis local del documento.")
        except KeyError:
            return


def _run_apply(job_id: str, request: ApplyRequest) -> None:
    try:
        job = job_store.get(job_id)
        if job.analysis is None:
            raise ValueError("El análisis todavía no está disponible.")
        replacements = {
            decision.group_id: decision.replacement
            for decision in request.decisions
            if decision.action == "replace" and decision.replacement is not None
        }
        selected_group_ids = {decision.group_id for decision in request.decisions if decision.action == "replace"}
        output, applied = anonymizer_engine.apply(
            job.source_bytes,
            job.analysis,
            selected_group_ids=selected_group_ids,
            replacements=replacements,
            remove_unsupported_content=request.remove_unsupported_content,
        )
        job.output_bytes = output
        job.output_name = output_filename(job.source_name, "anonimizado")
        job.metadata["applied_count"] = len(applied)
        job.metadata["remaining_count"] = len(job.analysis.findings) - len(applied)
        job_store.state(job_id, status="ready", progress=100)
    except Exception as exc:
        try:
            job_store.state(job_id, status="failed", progress=100, error=str(exc) or "No se ha podido generar la copia anonimizada.")
        except KeyError:
            return


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities() -> dict[str, object]:
    return anonymizer_engine.capabilities()


@router.post("/analyze", status_code=202, response_model=AnonymizerJobResponse)
async def analyze(file: UploadFile = File(...), options: str = Form("{}")) -> dict[str, object]:
    if not anonymizer_engine.ready:
        raise HTTPException(status_code=503, detail=anonymizer_engine.capabilities()["model"]["detail"])
    filename, content, document_format = await _read_upload(file)
    try:
        parsed = AnalysisOptionsPayload.model_validate(json.loads(options or "{}"))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail="La configuración del análisis no es válida.") from exc
    job = job_store.create(
        source_name=filename,
        source_bytes=content,
        options=AnalysisOptions(profile=parsed.profile, enabled_categories=tuple(parsed.enabled_categories), allowlist=tuple(parsed.allowlist)),
        document_format=document_format,
    )
    executor.submit(_run_analysis, job.id)
    return _serialize(job)


@router.get("/{job_id}", response_model=AnonymizerJobResponse)
def get_job(job_id: str) -> dict[str, object]:
    return _serialize(_get_job(job_id))


@router.post("/{job_id}/findings/manual", response_model=AnonymizerJobResponse)
def add_manual_finding(job_id: str, request: ManualFindingRequest) -> dict[str, object]:
    job = _get_job(job_id)
    if job.status != "review_ready" or job.analysis is None:
        raise HTTPException(status_code=409, detail="El trabajo no está disponible para revisión manual.")
    try:
        job.analysis = anonymizer_engine.add_manual_finding(
            job.analysis,
            block_id=request.block_id,
            start=request.start,
            end=request.end,
            entity_type=request.entity_type,
            all_occurrences=request.all_occurrences,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize(job)


@router.post("/{job_id}/apply", status_code=202, response_model=AnonymizerJobResponse)
def apply(job_id: str, request: ApplyRequest) -> dict[str, object]:
    job = _get_job(job_id)
    if not request.review_confirmed:
        raise HTTPException(status_code=400, detail="Confirma la revisión humana antes de generar la copia.")
    if job.status != "review_ready" or job.analysis is None:
        raise HTTPException(status_code=409, detail="El análisis no está preparado para aplicar decisiones.")
    known_groups = {group.id for group in job.analysis.groups}
    if any(decision.group_id not in known_groups for decision in request.decisions):
        raise HTTPException(status_code=400, detail="La selección contiene un grupo desconocido.")
    job_store.state(job_id, status="applying", progress=10)
    executor.submit(_run_apply, job_id, request)
    return _serialize(job)


@router.get("/{job_id}/download")
def download(job_id: str) -> Response:
    job = _get_job(job_id)
    if job.status != "ready" or job.output_bytes is None or job.output_name is None:
        raise HTTPException(status_code=409, detail="La copia anonimizada todavía no está disponible.")
    return Response(
        content=job.output_bytes,
        media_type=mime_type_for(job.document_format),
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(job.output_name)}"},
    )


@router.delete("/{job_id}", status_code=204)
def delete(job_id: str) -> Response:
    if not job_store.delete(job_id):
        raise HTTPException(status_code=404, detail="La sesión de anonimización ya no existe.")
    return Response(status_code=204)
