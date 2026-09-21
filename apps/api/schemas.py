from pydantic import BaseModel, Field


class AnonymizationDecision(BaseModel):
    finding_id: str = Field(min_length=1, max_length=64)
    replacement: str | None = Field(default=None, max_length=120)


class ApplyAnonymizationRequest(BaseModel):
    decisions: list[AnonymizationDecision] = Field(min_length=1)


class GenerateDocumentRequest(BaseModel):
    context: dict[str, str] = Field(default_factory=dict)
