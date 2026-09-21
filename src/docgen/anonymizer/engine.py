from __future__ import annotations

import re
from collections import Counter
from dataclasses import replace

from docgen.anonymizer.detector_registry import (
    ALL_CATEGORIES,
    ENTITY_LABELS,
    TOKEN_PREFIXES,
    NoOpNerDetector,
    RuleBasedDetector,
    context_snippet,
    finding_id,
)
from docgen.anonymizer.adapter_registry import DocumentAdapterRegistry
from docgen.anonymizer.model_runtime import create_ner_detector
from docgen.anonymizer.models import (
    AnalysisOptions,
    DocumentAnalysis,
    Finding,
    TextBlock,
)
from docgen.anonymizer.resolution import BlockingCoverageValidator, DefaultFindingResolver
from docgen.feature_flags import feature_snapshot


class ModelUnavailableError(RuntimeError):
    pass


def _chunks(text: str, size: int = 1800, overlap: int = 240):
    if len(text) <= size:
        yield 0, text
        return
    start = 0
    while start < len(text):
        tentative = min(len(text), start + size)
        end = tentative
        if tentative < len(text):
            boundary = max(text.rfind(" ", start + size // 2, tentative), text.rfind("\n", start + size // 2, tentative))
            if boundary > start:
                end = boundary
        yield start, text[start:end]
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)


class LocalAnonymizerEngine:
    """Local, document-aware orchestration for rules, NER and review data."""

    def __init__(self, *, ner_detector: object | None = None) -> None:
        self.adapters = DocumentAdapterRegistry()
        self.rule_detector = RuleBasedDetector()
        self.ner_detector = ner_detector if ner_detector is not None else create_ner_detector()
        self.resolver = DefaultFindingResolver()
        self.coverage_validator = BlockingCoverageValidator()

    @property
    def ready(self) -> bool:
        return bool(getattr(self.ner_detector, "ready", False))

    def capabilities(self) -> dict[str, object]:
        return {
            "formats": self.adapters.capabilities(),
            "features": feature_snapshot(),
            "categories": [{"id": category, "label": ENTITY_LABELS[category], "enabled_by_default": True} for category in ALL_CATEGORIES],
            "default_profile": "maximum",
            "model": {
                "ready": self.ready,
                "provider": getattr(self.ner_detector, "name", "Transformer español"),
                "version": getattr(self.ner_detector, "model_version", "unavailable"),
                "detail": getattr(self.ner_detector, "detail", ""),
                "local_only": True,
            },
            "limits": {"compressed_mb": 15, "expanded_mb": 60, "retention_minutes": 30},
        }

    def _ner_findings(self, block: TextBlock) -> list[Finding]:
        findings: list[Finding] = []
        for offset, text in _chunks(block.text):
            for finding in self.ner_detector.detect(text, block.location):
                start, end = finding.start + offset, finding.end + offset
                findings.append(replace(
                    finding,
                    id=finding_id(block.location, finding.entity_type, start, end, block.text[start:end], finding.sources[0] if finding.sources else "NER"),
                    value=block.text[start:end],
                    start=start,
                    end=end,
                    context=context_snippet(block.text, start, end),
                ))
        return findings

    def analyze(self, document_bytes: bytes, options: AnalysisOptions | None = None) -> DocumentAnalysis:
        if not self.ready:
            raise ModelUnavailableError(getattr(self.ner_detector, "detail", "El modelo local no está disponible."))
        options = options or AnalysisOptions()
        adapter = self.adapters.for_document(document_bytes)
        blocks, coverage = adapter.extract(document_bytes)
        enabled = set(options.enabled_categories or ALL_CATEGORIES)
        allowlist = {value.casefold().strip() for value in options.allowlist if value.strip()}
        candidates: list[Finding] = []
        for block in blocks:
            candidates.extend(self.rule_detector.detect(block.text, block.location))
            candidates.extend(self._ner_findings(block))
        candidates = [
            finding for finding in candidates
            if finding.entity_type in enabled and finding.value.casefold().strip() not in allowlist
        ]
        findings, groups = self.resolver.resolve(candidates)
        summary = dict(Counter(finding.entity_type for finding in findings))
        return DocumentAnalysis(findings=findings, groups=groups, blocks=blocks, coverage_issues=coverage, summary=summary)

    def add_manual_finding(
        self,
        analysis: DocumentAnalysis,
        *,
        block_id: str,
        start: int,
        end: int,
        entity_type: str,
        all_occurrences: bool,
    ) -> DocumentAnalysis:
        block = next((item for item in analysis.blocks if item.id == block_id), None)
        if block is None or start < 0 or end > len(block.text) or start >= end:
            raise ValueError("La selección manual no corresponde al documento analizado.")
        value = block.text[start:end]
        if not value.strip():
            raise ValueError("Selecciona texto visible para crear el hallazgo.")
        if entity_type not in ENTITY_LABELS:
            raise ValueError("La categoría manual no es válida.")
        occurrences: list[tuple[TextBlock, int, int]] = [(block, start, end)]
        if all_occurrences:
            occurrences = []
            for current in analysis.blocks:
                for match in re.finditer(re.escape(value), current.text, re.I):
                    occurrences.append((current, match.start(), match.end()))
        manual = [Finding(
            id=finding_id(current.location, entity_type, left, right, current.text[left:right], "Revisión manual"),
            entity_type=entity_type,
            label=ENTITY_LABELS[entity_type],
            value=current.text[left:right],
            replacement=f"[{TOKEN_PREFIXES[entity_type]}]",
            location=current.location,
            start=left,
            end=right,
            context=context_snippet(current.text, left, right),
            confidence=1.0,
            confidence_band="validated",
            sources=("Revisión manual",),
            reason="Hallazgo añadido manualmente durante la revisión humana.",
            is_manual=True,
            priority=200,
        ) for current, left, right in occurrences]
        findings, groups = self.resolver.resolve([*analysis.findings, *manual])
        return replace(analysis, findings=findings, groups=groups, summary=dict(Counter(item.entity_type for item in findings)))

    def apply(
        self,
        document_bytes: bytes,
        analysis: DocumentAnalysis,
        *,
        selected_group_ids: set[str],
        replacements: dict[str, str],
        remove_unsupported_content: bool,
        _verify_output: bool = True,
    ) -> tuple[bytes, tuple[Finding, ...]]:
        self.coverage_validator.ensure_applicable(analysis.coverage_issues, remove_unsupported_content=remove_unsupported_content)
        selected = tuple(item for item in analysis.findings if item.group_id in selected_group_ids)
        if not selected:
            raise ValueError("Selecciona al menos un grupo para anonimizar.")
        adapter = self.adapters.for_document(document_bytes)
        output = adapter.apply(
            document_bytes,
            selected,
            replacements,
            remove_unsupported_content=remove_unsupported_content,
        )
        if _verify_output:
            adapter.verify(output, selected)
        return output, selected


def build_rules_engine() -> LocalAnonymizerEngine:
    return LocalAnonymizerEngine(ner_detector=NoOpNerDetector())
