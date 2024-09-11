from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import VersionStatus


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VersionOut(ORM):
    id: int
    version: int
    status: VersionStatus
    progress: int
    stage: str
    error: str | None
    attempts: int
    chunk_count: int
    size_bytes: int
    sha256: str
    embedding_model: str | None
    created_at: datetime
    processed_at: datetime | None


class DocumentOut(ORM):
    id: int
    collection_id: int
    title: str
    filename: str
    created_at: datetime
    current_version: VersionOut | None
    latest_version: VersionOut | None


class DocumentDetail(DocumentOut):
    collection_name: str
    versions: list[VersionOut]


class UploadResult(BaseModel):
    document: DocumentOut
    version: VersionOut
    created: bool
    queued: bool


class ChunkOut(ORM):
    id: int
    ordinal: int
    heading: str
    text: str
    char_start: int
    char_end: int
    is_active: bool
