from __future__ import annotations

import pytest

from conftest import FIXTURE_ROOT, load_corpus_manifest
from docgen.anonymizer.adapter_registry import DocumentAdapterRegistry
from docgen.anonymizer.resolution import canonical_value
from docgen.anonymizer.verified_engine import build_verified_rules_engine
from docgen.document_formats import detect_document_format
from docgen.renderer import render_document
from docgen.template_service import analyze_template


MANIFEST = load_corpus_manifest()


def corpus_params(section: str) -> list[object]:
    params: list[object] = []
    for case in MANIFEST[section]:
        marks = [pytest.mark.slow] if case.get("slow") else []
        params.append(pytest.param(case, id=case["id"], marks=marks))
    return params


def expected_pairs(case: dict[str, object]) -> set[tuple[str, str]]:
    return {
        (entity_type, canonical_value(entity_type, value))
        for entity_type, values in case["expected_values"].items()
        for value in values
    }


def document_text(document_bytes: bytes) -> str:
    adapter = DocumentAdapterRegistry().for_document(document_bytes)
    blocks, issues = adapter.extract(document_bytes)
    assert not issues
    return "\n".join(block.text for block in blocks)


@pytest.mark.integration
@pytest.mark.parametrize("case", corpus_params("anonymizer_cases"))
def test_anonymizer_corpus_exercises_real_adapters(case: dict[str, object]) -> None:
    path = FIXTURE_ROOT / case["path"]
    source = path.read_bytes()

    assert path.stat().st_size > 10_000
    assert detect_document_format(source) == case["format"]

    analysis = build_verified_rules_engine().analyze(source)
    actual = {
        (finding.entity_type, canonical_value(finding.entity_type, finding.value))
        for finding in analysis.findings
    }
    assert len(analysis.findings) >= case["minimum_findings"]
    assert expected_pairs(case) <= actual
    assert not analysis.coverage_issues
    if case.get("requires_ocr"):
        assert any(block.location.part.endswith("/ocr") for block in analysis.blocks)


@pytest.mark.integration
@pytest.mark.parametrize("case", corpus_params("anonymizer_cases"))
def test_anonymizer_corpus_roundtrip_removes_selected_values(
    case: dict[str, object],
) -> None:
    source = (FIXTURE_ROOT / case["path"]).read_bytes()
    engine = build_verified_rules_engine()
    analysis = engine.analyze(source)
    output, applied = engine.apply(
        source,
        analysis,
        selected_group_ids={group.id for group in analysis.groups},
        replacements={},
        remove_unsupported_content=False,
    )

    assert output != source
    assert detect_document_format(output) == case["format"]
    assert len(applied) == len(analysis.findings)
    residual = engine.analyze(output)
    residual_pairs = {
        (finding.entity_type, canonical_value(finding.entity_type, finding.value))
        for finding in residual.findings
    }
    assert expected_pairs(case).isdisjoint(residual_pairs)


@pytest.mark.integration
@pytest.mark.parametrize("case", corpus_params("generator_cases"))
def test_generator_corpus_discovers_and_renders_variables(
    case: dict[str, object],
) -> None:
    source = (FIXTURE_ROOT / case["path"]).read_bytes()
    analysis = analyze_template(source)

    assert detect_document_format(source) == case["format"]
    assert set(analysis.variables) == set(case["variables"])
    assert analysis.is_ready

    output = render_document(source, case["context"])
    assert detect_document_format(output) == case["format"]
    assert not analyze_template(output).variables
    rendered_text = document_text(output).casefold()
    for expected in case["expected_text"]:
        assert expected.casefold() in rendered_text
