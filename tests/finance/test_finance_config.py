from decimal import Decimal

import pytest

from apps.api.finance.config import ApiSettings


def test_api_settings_have_local_defaults() -> None:
    settings = ApiSettings.from_mapping({})

    assert settings.max_file_bytes == 15 * 1024 * 1024
    assert settings.reconciliation_tolerance == Decimal("0.10")


def test_api_settings_parse_tolerance() -> None:
    settings = ApiSettings.from_mapping(
        {
            "FINANCE_IMPUTER_TOLERANCE_PERCENTAGE": "0.25",
        }
    )

    assert settings.reconciliation_tolerance == Decimal("0.25")


def test_api_settings_reject_negative_tolerance() -> None:
    with pytest.raises(RuntimeError, match="negativo"):
        ApiSettings.from_mapping({"FINANCE_IMPUTER_TOLERANCE_PERCENTAGE": "-1"})


def test_api_settings_reject_non_finite_tolerance() -> None:
    with pytest.raises(RuntimeError, match="finito"):
        ApiSettings.from_mapping({"FINANCE_IMPUTER_TOLERANCE_PERCENTAGE": "NaN"})
