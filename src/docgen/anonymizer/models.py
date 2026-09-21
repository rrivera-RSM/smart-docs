from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from docgen.document_formats import DocumentFormat

ConfidenceBand = Literal["validated", "probable", "review"]
JobStatus = Literal[
    "queued", "extracting", "detecting", "review_ready", "applying",
    "ready", "failed",
]


@dataclass(frozen=True)
class DocumentLocation:
    """Stable pointer to a logical text block inside a document."""

    kind: DocumentFormat
    part: str
    block_index: int
    label: str

    @property
    def id(self) -> str:
        if self.kind == "docx":
            return f"{self.part}:paragraph[{self.block_index}]"
        return f"{self.kind}:{self.part}:block[{self.block_index}]"

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "part": self.part,
            "block_index": self.block_index,
            "label": self.label,
        }


@dataclass(frozen=True)
class TextBlock:
    id: str
    text: str
    location: DocumentLocation

    def to_dict(self) -> dict[str, object]:
        return {"id": self.id, "text": self.text, "location": self.location.to_dict()}


@dataclass(frozen=True)
class CoverageIssue:
    id: str
    kind: str
    label: str
    detail: str
    blocking: bool = True
    removable: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "detail": self.detail,
            "blocking": self.blocking,
            "removable": self.removable,
        }


@dataclass(frozen=True)
class Finding:
    """A reviewable sensitive value mapped back to its source document."""

    id: str
    entity_type: str
    label: str
    value: str
    replacement: str
    location: DocumentLocation | str
    start: int
    end: int
    context: str
    confidence: float
    group_id: str = ""
    confidence_band: ConfidenceBand = "review"
    sources: tuple[str, ...] = ()
    reason: str = ""
    selected_by_default: bool = True
    is_manual: bool = False
    priority: int = 10

    @property
    def location_id(self) -> str:
        if isinstance(self.location, DocumentLocation):
            return self.location.id
        return self.location

    def to_dict(self) -> dict[str, object]:
        if isinstance(self.location, DocumentLocation):
            location: object = self.location.to_dict()
        else:
            location = {
                "kind": "docx",
                "part": self.location,
                "block_index": 0,
                "label": self.location,
            }
        return {
            "id": self.id,
            "group_id": self.group_id,
            "entity_type": self.entity_type,
            "label": self.label,
            "value": self.value,
            "replacement": self.replacement,
            "location": location,
            "start": self.start,
            "end": self.end,
            "context": self.context,
            "confidence": self.confidence,
            "confidence_band": self.confidence_band,
            "sources": list(self.sources),
            "reason": self.reason,
            "selected_by_default": self.selected_by_default,
            "is_manual": self.is_manual,
        }


@dataclass(frozen=True)
class FindingGroup:
    id: str
    entity_type: str
    label: str
    value: str
    replacement: str
    confidence: float
    confidence_band: ConfidenceBand
    finding_ids: tuple[str, ...]
    sources: tuple[str, ...]
    reason: str
    selected_by_default: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "label": self.label,
            "value": self.value,
            "replacement": self.replacement,
            "confidence": self.confidence,
            "confidence_band": self.confidence_band,
            "finding_ids": list(self.finding_ids),
            "occurrence_count": len(self.finding_ids),
            "sources": list(self.sources),
            "reason": self.reason,
            "selected_by_default": self.selected_by_default,
        }


@dataclass(frozen=True)
class AnalysisOptions:
    profile: str = "maximum"
    enabled_categories: tuple[str, ...] = ()
    allowlist: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentAnalysis:
    findings: tuple[Finding, ...]
    groups: tuple[FindingGroup, ...]
    blocks: tuple[TextBlock, ...]
    coverage_issues: tuple[CoverageIssue, ...]
    summary: dict[str, int] = field(default_factory=dict)
