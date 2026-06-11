import uuid
from datetime import datetime

from pydantic import BaseModel


class PiiFindingResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    pii_type: str
    matched_text_preview: str
    page_number: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
