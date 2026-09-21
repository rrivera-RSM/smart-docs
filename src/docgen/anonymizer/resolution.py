from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from dataclasses import replace
from decimal import Decimal, InvalidOperation

from docgen.anonymizer.detector_registry import TOKEN_PREFIXES
from docgen.anonymizer.models import Finding, FindingGroup


def confidence_band(score: float) -> str:
    if score >= .95:
        return "validated"
    if score >= .75:
        return "probable"
    return "review"


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def _accentless(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )


def _money_words(value: str) -> int | None:
    words = re.findall(r"[a-z]+", _accentless(value.casefold()))
    units = {
        "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
        "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
        "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14,
        "quince": 15, "veinte": 20, "treinta": 30, "cuarenta": 40,
        "cincuenta": 50, "cien": 100, "ciento": 100,
    }
    total, current, matched = 0, 0, False
    for word in words:
        if word in units:
            current += units[word]
            matched = True
        elif word == "mil":
            total += max(current, 1) * 1_000
            current = 0
            matched = True
        elif word in {"millon", "millones"}:
            total += max(current, 1) * 1_000_000
            current = 0
            matched = True
    return total + current if matched else None


def _money_number(value: str) -> Decimal | None:
    match = re.search(r"\d[\d.,\s]*", value)
    if not match:
        words = _money_words(value)
        return Decimal(words) if words is not None else None
    raw = re.sub(r"\s", "", match.group(0))
    if "," in raw and "." in raw:
        decimal_mark = "," if raw.rfind(",") > raw.rfind(".") else "."
        thousands_mark = "." if decimal_mark == "," else ","
        raw = raw.replace(thousands_mark, "").replace(decimal_mark, ".")
    elif "," in raw:
        raw = raw.replace(",", ".") if len(raw.rsplit(",", 1)[1]) <= 2 else raw.replace(",", "")
    elif "." in raw and len(raw.rsplit(".", 1)[1]) > 2:
        raw = raw.replace(".", "")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def canonical_value(entity_type: str, value: str) -> str:
    folded = _fold(value)
    if entity_type in {
        "ES_DNI", "ES_NIE", "ES_TAX_ID", "ES_SOCIAL_SECURITY", "ES_IBAN",
        "CREDIT_CARD", "SWIFT", "ES_PHONE", "VEHICLE_PLATE", "PASSPORT",
    }:
        return re.sub(r"[^a-z0-9]", "", folded)
    if entity_type == "ORGANIZATION":
        normalized = _accentless(folded)
        normalized = re.sub(
            r"\b(?:s[\s.]*l[\s.]*u|s[\s.]*l|s[\s.]*a[\s.]*u|s[\s.]*a|ltd|limited|gmbh|llp|inc)\b\.?$",
            "",
            normalized,
        )
        return re.sub(r"[^a-z0-9&]", "", normalized)
    if entity_type == "MONEY":
        plain = _accentless(folded)
        currency = (
            "eur" if "\u20ac" in folded or "eur" in plain or "euro" in plain
            else "usd" if "$" in folded or "usd" in plain or "dolar" in plain
            else "gbp" if "\u00a3" in folded or "gbp" in plain or "libra" in plain
            else ""
        )
        number = _money_number(folded)
        return f"{number.normalize()}:{currency}" if number is not None else folded
    return folded


def group_id(entity_type: str, canonical: str) -> str:
    return hashlib.sha256(f"{entity_type}:{canonical}".encode()).hexdigest()[:18]


def _overlap(left: Finding, right: Finding) -> bool:
    return left.location_id == right.location_id and left.start < right.end and left.end > right.start


def _merge_evidence(primary: Finding, secondary: Finding) -> Finding:
    reasons = tuple(dict.fromkeys(filter(None, (primary.reason, secondary.reason))))
    return replace(
        primary,
        confidence=max(primary.confidence, secondary.confidence),
        sources=tuple(dict.fromkeys((*primary.sources, *secondary.sources))),
        reason=" ".join(reasons),
        priority=max(primary.priority, secondary.priority),
    )


class DefaultFindingResolver:
    """Resolve overlaps by authority and assign deterministic document aliases."""

    def resolve(
        self,
        findings: list[Finding] | tuple[Finding, ...],
    ) -> tuple[tuple[Finding, ...], tuple[FindingGroup, ...]]:
        accepted: list[Finding] = []
        for candidate in sorted(
            findings,
            key=lambda item: (
                -item.priority,
                -item.confidence,
                -(item.end - item.start),
                item.location_id,
                item.start,
            ),
        ):
            conflict_index = next(
                (index for index, item in enumerate(accepted) if _overlap(candidate, item)),
                None,
            )
            if conflict_index is None:
                accepted.append(candidate)
                continue
            accepted[conflict_index] = _merge_evidence(accepted[conflict_index], candidate)

        accepted.sort(key=lambda item: (item.location_id, item.start, item.end))
        grouped: dict[str, list[Finding]] = defaultdict(list)
        group_order: list[str] = []
        for finding in accepted:
            key = group_id(finding.entity_type, canonical_value(finding.entity_type, finding.value))
            if key not in grouped:
                group_order.append(key)
            grouped[key].append(finding)

        counters: dict[str, int] = defaultdict(int)
        resolved: list[Finding] = []
        groups: list[FindingGroup] = []
        for key in group_order:
            occurrences = grouped[key]
            entity_type = occurrences[0].entity_type
            prefix = TOKEN_PREFIXES.get(entity_type, entity_type[:5])
            counters[prefix] += 1
            token = f"[{prefix}_{counters[prefix]:02d}]"
            occurrence_ids: list[str] = []
            sources: list[str] = []
            reasons: list[str] = []
            max_confidence = max(item.confidence for item in occurrences)
            for finding in occurrences:
                enriched = replace(
                    finding,
                    group_id=key,
                    replacement=token,
                    confidence_band=confidence_band(finding.confidence),
                )
                resolved.append(enriched)
                occurrence_ids.append(enriched.id)
                sources.extend(enriched.sources)
                if enriched.reason:
                    reasons.append(enriched.reason)
            groups.append(FindingGroup(
                id=key,
                entity_type=entity_type,
                label=occurrences[0].label,
                value=occurrences[0].value,
                replacement=token,
                confidence=max_confidence,
                confidence_band=confidence_band(max_confidence),
                finding_ids=tuple(occurrence_ids),
                sources=tuple(dict.fromkeys(sources)),
                reason=" ".join(dict.fromkeys(reasons)),
            ))
        resolved.sort(key=lambda item: (item.location_id, item.start, item.end))
        return tuple(resolved), tuple(groups)


class CompactTokenPolicy:
    def token_for(self, entity_type: str, ordinal: int) -> str:
        prefix = TOKEN_PREFIXES.get(entity_type, entity_type[:5])
        return f"[{prefix}_{ordinal:02d}]"


class BlockingCoverageValidator:
    def ensure_applicable(
        self,
        issues: tuple[object, ...] | list[object],
        *,
        remove_unsupported_content: bool,
    ) -> None:
        blocking = [issue for issue in issues if getattr(issue, "blocking", False)]
        non_removable = [
            issue for issue in blocking if not getattr(issue, "removable", True)
        ]
        if non_removable:
            labels = ", ".join(
                getattr(issue, "label", "contenido no inspeccionable")
                for issue in non_removable
            )
            raise ValueError(
                "El documento contiene contenido que no puede inspeccionarse ni "
                f"eliminarse automáticamente: {labels}."
            )
        if blocking and not remove_unsupported_content:
            raise ValueError(
                "El documento contiene elementos no inspeccionables. "
                "Eliminalos antes de generar la copia segura."
            )
