from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any, Literal
from uuid import uuid4

from docgen.anonymizer.models import Finding

JobKind = Literal["generator", "anonymizer"]


@dataclass
class DocumentJob:
    id: str
    kind: JobKind
    source_name: str
    source_bytes: bytes
    created_at: datetime
    expires_at: datetime
    findings: tuple[Finding, ...] = ()
    template_analysis: Any | None = None
    output_bytes: bytes | None = None
    output_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class JobNotFoundError(KeyError):
    pass


class InMemoryJobStore:
    """Small, process-local store suitable for the first internal MVP."""

    def __init__(self, ttl_minutes: int = 30) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._jobs: dict[str, DocumentJob] = {}
        self._lock = RLock()

    def _cleanup(self) -> None:
        now = datetime.now(UTC)
        expired = [
            job_id
            for job_id, job in self._jobs.items()
            if job.expires_at <= now
        ]
        for job_id in expired:
            self._jobs.pop(job_id, None)

    def create(
        self,
        *,
        kind: JobKind,
        source_name: str,
        source_bytes: bytes,
        findings: tuple[Finding, ...] = (),
        template_analysis: Any | None = None,
    ) -> DocumentJob:
        with self._lock:
            self._cleanup()
            now = datetime.now(UTC)
            job = DocumentJob(
                id=uuid4().hex,
                kind=kind,
                source_name=source_name,
                source_bytes=source_bytes,
                created_at=now,
                expires_at=now + self._ttl,
                findings=findings,
                template_analysis=template_analysis,
            )
            self._jobs[job.id] = job
            return job

    def get(self, job_id: str, expected_kind: JobKind) -> DocumentJob:
        with self._lock:
            self._cleanup()
            job = self._jobs.get(job_id)
            if job is None or job.kind != expected_kind:
                raise JobNotFoundError(job_id)
            return job

    @property
    def ttl_minutes(self) -> int:
        return int(self._ttl.total_seconds() // 60)
