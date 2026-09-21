from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol

from docgen.anonymizer.models import CoverageIssue, Finding, TextBlock


class Detector(Protocol):
    name: str
    ready: bool

    def detect(self, text: str, location: object) -> list[Finding]: ...


class DocumentAdapter(Protocol):
    format_name: str

    def extract(
        self, document_bytes: bytes
    ) -> tuple[tuple[TextBlock, ...], tuple[CoverageIssue, ...]]: ...

    def apply(
        self,
        document_bytes: bytes,
        findings: Sequence[Finding],
        replacements: Mapping[str, str],
        *,
        remove_unsupported_content: bool,
    ) -> bytes: ...

    def verify(
        self, document_bytes: bytes, applied_findings: Iterable[Finding]
    ) -> tuple[TextBlock, ...]: ...


class FindingResolver(Protocol):
    def resolve(
        self, findings: Iterable[Finding]
    ) -> tuple[tuple[Finding, ...], tuple[object, ...]]: ...


class ReplacementPolicy(Protocol):
    def token_for(self, entity_type: str, ordinal: int) -> str: ...


class CoverageValidator(Protocol):
    def ensure_applicable(
        self,
        issues: Iterable[CoverageIssue],
        *,
        remove_unsupported_content: bool,
    ) -> None: ...


class JobStore(Protocol):
    def get(self, job_id: str, expected_kind: str) -> object: ...
