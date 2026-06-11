import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.core.enums import Classification


class DocumentResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    uploaded_by_id: uuid.UUID | None
    filename: str
    original_filename: str
    content_type: str
    checksum: str
    status: str
    error_message: str | None
    classification: str
    created_at: datetime
    indexed_at: datetime | None
    # Populated only for tenant_admin and compliance_officer roles
    pii_findings_count: int | None = None

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    id: uuid.UUID
    status: str
    message: str


class DocumentClassificationUpdate(BaseModel):
    classification: str

    @field_validator("classification")
    @classmethod
    def validate_classification(cls, v: str) -> str:
        valid = [c.value for c in Classification]
        if v not in valid:
            raise ValueError(f"Invalid classification. Must be one of: {valid}")
        return v
