from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from docgen.anonymizer.models import ConfidenceBand, JobStatus
from docgen.document_formats import DocumentFormat


class FormatCapability(BaseModel):
    id: str
    label: str
    enabled: bool
    reason: str | None = None


class CategoryCapability(BaseModel):
    id: str
    label: str
    enabled_by_default: bool


class ModelCapability(BaseModel):
    ready: bool
    provider: str
    version: str
    detail: str
    local_only: bool


class LimitsCapability(BaseModel):
    compressed_mb: int
    expanded_mb: int
    retention_minutes: int


class CapabilitiesResponse(BaseModel):
    formats: list[FormatCapability]
    features: dict[str, bool]
    categories: list[CategoryCapability]
    default_profile: Literal["maximum"]
    model: ModelCapability
    limits: LimitsCapability


class LocationResponse(BaseModel):
    kind: DocumentFormat
    part: str
    block_index: int
    label: str


class FindingResponse(BaseModel):
    id: str
    group_id: str
    entity_type: str
    label: str
    value: str
    replacement: str
    location: LocationResponse
    start: int
    end: int
    context: str
    confidence: float
    confidence_band: ConfidenceBand
    sources: list[str]
    reason: str
    selected_by_default: bool
    is_manual: bool


class FindingGroupResponse(BaseModel):
    id: str
    entity_type: str
    label: str
    value: str
    replacement: str
    confidence: float
    confidence_band: ConfidenceBand
    finding_ids: list[str]
    occurrence_count: int
    sources: list[str]
    reason: str
    selected_by_default: bool


class TextBlockResponse(BaseModel):
    id: str
    text: str
    location: LocationResponse


class CoverageIssueResponse(BaseModel):
    id: str
    kind: str
    label: str
    detail: str
    blocking: bool
    removable: bool


class AnonymizerJobResponse(BaseModel):
    job_id: str
    filename: str
    document_format: DocumentFormat
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    error: str | None
    expires_in_minutes: int
    limitations: list[str]
    findings: list[FindingResponse]
    groups: list[FindingGroupResponse]
    blocks: list[TextBlockResponse]
    coverage_issues: list[CoverageIssueResponse]
    summary: dict[str, int]
    applied_count: int | None = None
    remaining_count: int | None = None
    download_url: str | None = None
    output_filename: str | None = None
