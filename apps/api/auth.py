from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.security import SecurityScopes
from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer


AUTH_ENABLED = os.getenv("SMARTDOCS_AUTH_ENABLED", "true").lower() not in {
    "0",
    "false",
    "no",
    "off",
}
TENANT_ID = os.getenv("SMARTDOCS_AZURE_TENANT_ID", "").strip()
API_CLIENT_ID = os.getenv("SMARTDOCS_AZURE_API_CLIENT_ID", "").strip()
SCOPE_NAME = "user_impersonation"


def _configuration_error() -> str | None:
    missing = [
        name
        for name, value in (
            ("SMARTDOCS_AZURE_TENANT_ID", TENANT_ID),
            ("SMARTDOCS_AZURE_API_CLIENT_ID", API_CLIENT_ID),
        )
        if not value
    ]
    if not missing:
        return None
    return "Faltan variables de autenticación: " + ", ".join(missing)


azure_scheme = (
    SingleTenantAzureAuthorizationCodeBearer(
        app_client_id=API_CLIENT_ID,
        tenant_id=TENANT_ID,
        scopes={f"api://{API_CLIENT_ID}/{SCOPE_NAME}": SCOPE_NAME},
    )
    if AUTH_ENABLED and not _configuration_error()
    else None
)


@asynccontextmanager
async def auth_lifespan(_: FastAPI) -> AsyncIterator[None]:
    if AUTH_ENABLED:
        error = _configuration_error()
        if error or azure_scheme is None:
            raise RuntimeError(error or "La autenticación Azure no está configurada.")
        await azure_scheme.openid_config.load_config()
    yield


async def require_azure_user(
    request: Request,
    security_scopes: SecurityScopes,
):
    if not AUTH_ENABLED:
        return None
    if azure_scheme is None:
        raise HTTPException(
            status_code=503,
            detail=_configuration_error() or "Azure AD no está configurado.",
        )
    return await azure_scheme(
        request=request,
        security_scopes=security_scopes,
    )
