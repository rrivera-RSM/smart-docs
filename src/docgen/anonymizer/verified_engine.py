from __future__ import annotations

from docgen.anonymizer.detector_registry import NoOpNerDetector
from docgen.anonymizer.engine import LocalAnonymizerEngine
from docgen.anonymizer.models import DocumentAnalysis, Finding
from docgen.anonymizer.resolution import canonical_value


class VerifiedLocalAnonymizerEngine(LocalAnonymizerEngine):
    """Engine variant that re-runs detectors after applying replacements."""

    def apply(
        self,
        document_bytes: bytes,
        analysis: DocumentAnalysis,
        *,
        selected_group_ids: set[str],
        replacements: dict[str, str],
        remove_unsupported_content: bool,
    ) -> tuple[bytes, tuple[Finding, ...]]:
        output, applied = super().apply(
            document_bytes,
            analysis,
            selected_group_ids=selected_group_ids,
            replacements=replacements,
            remove_unsupported_content=remove_unsupported_content,
            _verify_output=False,
        )
        protected = {
            (finding.entity_type, canonical_value(finding.entity_type, finding.value))
            for finding in applied
        }
        adapter = self.adapters.for_document(output)
        blocks = adapter.verify(output, applied)
        residual: list[Finding] = []
        for block in blocks:
            residual.extend(self.rule_detector.detect(block.text, block.location))
            residual.extend(self._ner_findings(block))
        if any(
            (finding.entity_type, canonical_value(finding.entity_type, finding.value)) in protected
            for finding in residual
        ):
            raise ValueError(
                "La segunda pasada de detectores ha encontrado una entidad aprobada sin anonimizar."
            )
        return output, applied


def build_verified_rules_engine() -> VerifiedLocalAnonymizerEngine:
    return VerifiedLocalAnonymizerEngine(ner_detector=NoOpNerDetector())
