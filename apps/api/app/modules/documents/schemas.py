import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.enums import IndexStatus


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    mime_type: str
    size_bytes: int
    index_status: IndexStatus
    chunks: int = 0
    has_embeddings: bool = False
    created_at: datetime
