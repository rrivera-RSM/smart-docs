"""Provider detection and extractor entry points."""

from __future__ import annotations

from finance_imputer.models import InvoiceAnalysis
from finance_imputer.provider_profiles import ProviderCatalog, ProviderProfile

from .generic import extract_pages, extract_with_profile, profile_matches


class UnsupportedInvoiceError(ValueError):
    pass


def extract_invoice(
    content: bytes, catalog: ProviderCatalog | None = None
) -> InvoiceAnalysis:
    pages = extract_pages(content)
    active_catalog = catalog or ProviderCatalog.default()
    for definition in active_catalog.list():
        if profile_matches(pages, definition.profile):
            return extract_with_profile(pages, definition.profile)
    raise UnsupportedInvoiceError(
        "No se ha reconocido el proveedor. Puedes añadir un perfil desde Proveedores."
    )


def test_profile(content: bytes, profile: ProviderProfile) -> tuple[InvoiceAnalysis, bool]:
    pages = extract_pages(content)
    return extract_with_profile(pages, profile), profile_matches(pages, profile)
