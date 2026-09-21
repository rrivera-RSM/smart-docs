import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass

from docgen.anonymizer.models import Finding

Validator = Callable[[str], bool]

DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


@dataclass(frozen=True)
class DetectionRule:
    entity_type: str
    label: str
    replacement: str
    pattern: re.Pattern[str]
    validator: Validator
    confidence: float


def _always_valid(_: str) -> bool:
    return True


def _compact(value: str) -> str:
    return re.sub(r"[\s.-]", "", value).upper()


def validate_dni(value: str) -> bool:
    normalized = _compact(value)
    if not re.fullmatch(r"\d{8}[A-Z]", normalized):
        return False
    number = int(normalized[:8])
    return DNI_LETTERS[number % 23] == normalized[-1]


def validate_nie(value: str) -> bool:
    normalized = _compact(value)
    if not re.fullmatch(r"[XYZ]\d{7}[A-Z]", normalized):
        return False
    prefix = {"X": "0", "Y": "1", "Z": "2"}[normalized[0]]
    number = int(prefix + normalized[1:8])
    return DNI_LETTERS[number % 23] == normalized[-1]


def validate_spanish_iban(value: str) -> bool:
    normalized = re.sub(r"[\s-]", "", value).upper()
    if not re.fullmatch(r"ES\d{22}", normalized):
        return False
    rearranged = normalized[4:] + normalized[:4]
    numeric = "".join(
        character if character.isdigit() else str(ord(character) - 55)
        for character in rearranged
    )
    return int(numeric) % 97 == 1


RULES: tuple[DetectionRule, ...] = (
    DetectionRule(
        entity_type="ES_NIE",
        label="NIE",
        replacement="[NIE]",
        pattern=re.compile(
            r"(?<![A-Z0-9])(?:X|Y|Z)[\s.-]?\d{7}[\s.-]?[A-Z](?![A-Z0-9])",
            re.IGNORECASE,
        ),
        validator=validate_nie,
        confidence=0.99,
    ),
    DetectionRule(
        entity_type="ES_DNI",
        label="DNI",
        replacement="[DNI]",
        pattern=re.compile(
            r"(?<![A-Z0-9])\d{8}[\s.-]?[A-Z](?![A-Z0-9])",
            re.IGNORECASE,
        ),
        validator=validate_dni,
        confidence=0.99,
    ),
    DetectionRule(
        entity_type="ES_IBAN",
        label="IBAN",
        replacement="[IBAN]",
        pattern=re.compile(
            r"(?<![A-Z0-9])ES(?:[\s-]?\d){22}(?![A-Z0-9])",
            re.IGNORECASE,
        ),
        validator=validate_spanish_iban,
        confidence=0.99,
    ),
    DetectionRule(
        entity_type="EMAIL",
        label="Correo electrónico",
        replacement="[EMAIL]",
        pattern=re.compile(
            r"(?<![\w.+-])[\w.+-]+@(?:[\w-]+\.)+[A-Z]{2,}(?![\w.-])",
            re.IGNORECASE,
        ),
        validator=_always_valid,
        confidence=0.96,
    ),
    DetectionRule(
        entity_type="ES_PHONE",
        label="Teléfono",
        replacement="[TELÉFONO]",
        pattern=re.compile(
            r"(?<!\d)(?:\+34[\s.-]?)?[6789]\d{2}(?:[\s.-]?\d{3}){2}(?!\d)"
        ),
        validator=_always_valid,
        confidence=0.82,
    ),
)


def _overlaps(start: int, end: int, findings: list[Finding]) -> bool:
    return any(start < finding.end and end > finding.start for finding in findings)


def _context(text: str, start: int, end: int, radius: int = 44) -> str:
    context_start = max(0, start - radius)
    context_end = min(len(text), end + radius)
    prefix = "…" if context_start else ""
    suffix = "…" if context_end < len(text) else ""
    snippet = text[context_start:context_end].replace("\n", " ")
    return f"{prefix}{snippet}{suffix}"


def _finding_id(
    location: str,
    entity_type: str,
    start: int,
    end: int,
    value: str,
) -> str:
    payload = f"{location}:{entity_type}:{start}:{end}:{value}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:20]


def detect_text(text: str, location: str) -> list[Finding]:
    """Detect structured PII in one text block, resolving overlapping matches."""
    findings: list[Finding] = []

    for rule in RULES:
        for match in rule.pattern.finditer(text):
            value = match.group(0)
            if not rule.validator(value):
                continue
            if _overlaps(match.start(), match.end(), findings):
                continue

            findings.append(
                Finding(
                    id=_finding_id(
                        location,
                        rule.entity_type,
                        match.start(),
                        match.end(),
                        value,
                    ),
                    entity_type=rule.entity_type,
                    label=rule.label,
                    value=value,
                    replacement=rule.replacement,
                    location=location,
                    start=match.start(),
                    end=match.end(),
                    context=_context(text, match.start(), match.end()),
                    confidence=rule.confidence,
                )
            )

    return sorted(findings, key=lambda finding: finding.start)
