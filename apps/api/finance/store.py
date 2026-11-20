"""Short-lived in-memory invoice sessions for the local pilot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from finance_imputer.models import InvoiceAnalysis


@dataclass(slots=True)
class InvoiceJob:
    id: str
    source_name: str
    analysis: InvoiceAnalysis
    created_at: datetime


class InMemoryInvoiceStore:
    def __init__(self, ttl_minutes: int = 60) -> None:
        self.ttl_minutes = ttl_minutes
        self._jobs: dict[str, InvoiceJob] = {}

    def _purge_expired(self) -> None:
        threshold = datetime.now(UTC) - timedelta(minutes=self.ttl_minutes)
        expired = [job_id for job_id, job in self._jobs.items() if job.created_at < threshold]
        for job_id in expired:
            self._jobs.pop(job_id, None)

    def create(self, source_name: str, analysis: InvoiceAnalysis) -> InvoiceJob:
        self._purge_expired()
        job = InvoiceJob(
            id=str(uuid4()),
            source_name=source_name,
            analysis=analysis,
            created_at=datetime.now(UTC),
        )
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> InvoiceJob:
        self._purge_expired()
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise KeyError("La sesión no existe o ha caducado.") from exc


