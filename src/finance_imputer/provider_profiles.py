"""Validated declarative provider profiles and their local catalog."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

MAX_PATTERN_LENGTH = 800
PROVIDER_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class RegexCapture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern: str = Field(min_length=1, max_length=MAX_PATTERN_LENGTH)
    group: str = Field(default="value", min_length=1, max_length=40)
    required: bool = True
    join_following_line: bool = False

    @field_validator("pattern")
    @classmethod
    def valid_regex(cls, value: str) -> str:
        try:
            re.compile(value, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"Expresión regular no válida: {exc}") from exc
        return value

    @model_validator(mode="after")
    def valid_group(self) -> "RegexCapture":
        compiled = re.compile(self.pattern, re.IGNORECASE)
        if self.group.isdigit():
            if int(self.group) > compiled.groups:
                raise ValueError(f"El grupo {self.group} no existe en el patrón.")
        elif self.group not in compiled.groupindex:
            raise ValueError(f"El grupo '{self.group}' no existe en el patrón.")
        return self


class DetectionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    all_terms: list[str] = Field(min_length=1, max_length=12)
    page_limit: int = Field(default=2, ge=1, le=10)

    @field_validator("all_terms")
    @classmethod
    def valid_terms(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 100 for value in cleaned):
            raise ValueError("Cada término de detección debe tener entre 1 y 100 caracteres.")
        return cleaned


class HeaderProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=0, ge=0, le=50)
    invoice_number: RegexCapture
    invoice_date: RegexCapture
    customer_code: RegexCapture | None = None
    customer_name: RegexCapture | None = None
    taxable_base: RegexCapture
    tax_rate: RegexCapture | None = None
    tax_amount: RegexCapture | None = None
    invoice_total: RegexCapture


class LineExtractionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["grouped_detail", "flat"]
    page: int = Field(default=1, ge=0, le=50)
    user_pattern: str | None = Field(default=None, max_length=MAX_PATTERN_LENGTH)
    summary_pattern: str | None = Field(default=None, max_length=MAX_PATTERN_LENGTH)
    detail_pattern: str | None = Field(default=None, max_length=MAX_PATTERN_LENGTH)
    row_pattern: str | None = Field(default=None, max_length=MAX_PATTERN_LENGTH)
    project_reference_pattern: str | None = Field(
        default=None,
        max_length=MAX_PATTERN_LENGTH,
    )
    service_names: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def valid_line_patterns(self) -> "LineExtractionProfile":
        if self.mode == "grouped_detail":
            self._check(self.user_pattern, {"user"}, "usuario")
            self._check(
                self.summary_pattern,
                {"service", "quantity", "amount"},
                "resumen",
            )
            self._check(
                self.detail_pattern,
                {"quantity", "unit_price", "amount"},
                "detalle",
            )
        else:
            self._check(
                self.row_pattern,
                {"service", "quantity", "unit_price", "amount"},
                "fila",
            )
        if self.project_reference_pattern:
            self._check(
                self.project_reference_pattern,
                {"project_reference"},
                "referencia de proyecto",
            )
        return self

    @staticmethod
    def _check(pattern: str | None, groups: set[str], label: str) -> None:
        if not pattern:
            raise ValueError(f"Falta el patrón de {label}.")
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"El patrón de {label} no es válido: {exc}") from exc
        missing = groups.difference(compiled.groupindex)
        if missing:
            raise ValueError(
                f"El patrón de {label} no contiene los grupos: {', '.join(sorted(missing))}."
            )


class ProviderProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    id: str = Field(min_length=2, max_length=60)
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=300)
    detection: DetectionProfile
    header: HeaderProfile
    lines: LineExtractionProfile

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        if not PROVIDER_ID_RE.fullmatch(value):
            raise ValueError(
                "El identificador sólo puede contener minúsculas, números y guiones."
            )
        return value


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
    profile: ProviderProfile
    built_in: bool


class ProviderCatalog:
    def __init__(self, built_in_dir: Path, user_dir: Path) -> None:
        self.built_in_dir = built_in_dir
        self.user_dir = user_dir

    @classmethod
    def default(cls) -> "ProviderCatalog":
        project_dir = Path(__file__).resolve().parents[2]
        user_dir = Path(
            os.getenv(
                "FINANCE_IMPUTER_PROVIDER_DIR",
                str(project_dir / "data" / "finance" / "providers"),
            )
        )
        return cls(project_dir / "provider_profiles", user_dir)

    def list(self) -> tuple[ProviderDefinition, ...]:
        records: dict[str, ProviderDefinition] = {}
        for path in sorted(self.built_in_dir.glob("*.json")):
            profile = self._read(path)
            records[profile.id] = ProviderDefinition(profile=profile, built_in=True)
        if self.user_dir.exists():
            for path in sorted(self.user_dir.glob("*.json")):
                try:
                    profile = self._read(path)
                except (ValueError, OSError, ValidationError):
                    continue
                records[profile.id] = ProviderDefinition(profile=profile, built_in=False)
        return tuple(sorted(records.values(), key=lambda item: item.profile.name.casefold()))

    def get(self, provider_id: str) -> ProviderDefinition:
        for definition in self.list():
            if definition.profile.id == provider_id:
                return definition
        raise KeyError("El perfil de proveedor no existe.")

    def save(self, profile: ProviderProfile) -> ProviderDefinition:
        self.user_dir.mkdir(parents=True, exist_ok=True)
        destination = self.user_dir / f"{profile.id}.json"
        temporary = self.user_dir / f".{profile.id}.tmp"
        temporary.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(destination)
        return ProviderDefinition(profile=profile, built_in=False)

    @staticmethod
    def _read(path: Path) -> ProviderProfile:
        return ProviderProfile.model_validate_json(path.read_text(encoding="utf-8"))
