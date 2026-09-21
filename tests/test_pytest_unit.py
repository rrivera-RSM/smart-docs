from __future__ import annotations

import pytest

from docgen.anonymizer.detector_registry import RuleBasedDetector
from docgen.anonymizer.models import DocumentLocation
from docgen.anonymizer.resolution import DefaultFindingResolver


LOCATION = DocumentLocation(
    kind="docx",
    part="word/document.xml",
    block_index=0,
    label="Documento",
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Pasaporte PA123456", "PA123456"),
        ("N.º de pasaporte X1234567", "X1234567"),
        ("Passport number 123456789", "123456789"),
        ("Documento de viaje AB-123456", "AB-123456"),
    ],
)
def test_passport_variants_are_detected_with_explicit_context(
    text: str,
    expected: str,
) -> None:
    findings = RuleBasedDetector().detect(text, LOCATION)

    assert [(item.entity_type, item.value) for item in findings] == [
        ("PASSPORT", expected)
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    [
        "Referencia interna PA123456",
        "Pasaporte ABCDEF",
        "Pasaporte AAAAAA",
    ],
)
def test_passport_rule_avoids_unlabelled_or_non_numeric_values(text: str) -> None:
    findings = RuleBasedDetector().detect(text, LOCATION)

    assert all(item.entity_type != "PASSPORT" for item in findings)


@pytest.mark.unit
def test_passport_separator_variants_share_one_deterministic_alias() -> None:
    candidates = RuleBasedDetector().detect(
        "Pasaporte PA-123456. Documento de viaje PA123456.",
        LOCATION,
    )
    findings, groups = DefaultFindingResolver().resolve(candidates)

    passport_groups = [group for group in groups if group.entity_type == "PASSPORT"]
    passport_findings = [item for item in findings if item.entity_type == "PASSPORT"]
    assert len(passport_groups) == 1
    assert len(passport_findings) == 2
    assert passport_groups[0].replacement == "[PASS_01]"
    assert {item.group_id for item in passport_findings} == {passport_groups[0].id}


@pytest.mark.unit
def test_passport_is_detected_when_a_docx_table_cell_carries_the_label() -> None:
    table_location = DocumentLocation(
        kind="docx",
        part="word/document.xml",
        block_index=7,
        label="Documento · Pasaporte",
    )

    findings = RuleBasedDetector().detect("PA-123456", table_location)

    assert [(item.entity_type, item.value) for item in findings] == [
        ("PASSPORT", "PA-123456")
    ]
