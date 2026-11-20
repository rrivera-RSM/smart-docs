"""Finance limits and reconciliation settings; CORS and auth belong to SmartDocs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ApiSettings:
    """Validated module runtime limits."""

    max_file_bytes: int = 15 * 1024 * 1024
    max_profile_bytes: int = 100 * 1024
    reconciliation_tolerance: Decimal = Decimal("0.10")

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, str] | None = None,
    ) -> "ApiSettings":
        source = os.environ if values is None else values
        raw_tolerance = source.get(
            "FINANCE_IMPUTER_TOLERANCE_PERCENTAGE",
            "0.10",
        ).strip()
        try:
            tolerance = Decimal(raw_tolerance)
        except InvalidOperation as exc:
            raise RuntimeError(
                "FINANCE_IMPUTER_TOLERANCE_PERCENTAGE debe ser un porcentaje válido."
            ) from exc
        if not tolerance.is_finite():
            raise RuntimeError(
                "FINANCE_IMPUTER_TOLERANCE_PERCENTAGE debe ser un porcentaje finito."
            )
        if tolerance < 0:
            raise RuntimeError(
                "FINANCE_IMPUTER_TOLERANCE_PERCENTAGE no puede ser negativo."
            )

        return cls(reconciliation_tolerance=tolerance)


api_settings = ApiSettings.from_mapping()
