"""Request payloads accepted by the HTTP API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LineUpdate(BaseModel):
    user: str | None = None
    project_reference: str | None = None
    service: str | None = None
    quantity: float | None = Field(default=None, ge=0)
    unit_price: float | None = Field(default=None, ge=0)
    amount: float | None = Field(default=None, ge=0)
    status: Literal["proposed", "accepted", "pending"] | None = None
    comment: str | None = None


class ExportRequest(BaseModel):
    confirm_discard_pending: bool = False

