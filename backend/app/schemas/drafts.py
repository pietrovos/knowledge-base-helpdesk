from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import DraftStatus, GapStatus
from app.schemas.identity import UserRef


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DraftSourceOut(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    version: int
    heading: str
    text: str | None  # None when the viewer can't read this collection (anymore)
    rank: int
    similarity: float | None
    keyword_rank: int | None
    cited: bool
    accessible: bool
    live: bool  # still the current version of a non-deleted document


class DraftOut(BaseModel):
    id: int
    ticket_id: int
    status: DraftStatus
    question: str
    custom_question: bool
    reply: str
    missing_information: str
    invalid_citation_ids: list[int]
    error: str | None
    error_kind: str | None
    decided_by: str | None
    provider: str | None
    model: str | None
    embedding_model: str | None
    retrieval_ms: int | None
    generation_ms: int | None
    best_similarity: float | None
    requested_by: UserRef | None
    created_at: datetime
    completed_at: datetime | None
    published_text: str | None
    was_edited: bool | None
    sources: list[DraftSourceOut]
    knowledge_gap_id: int | None = None


class DraftCreate(BaseModel):
    question: str | None = Field(default=None, max_length=2000)


class EvidenceOut(BaseModel):
    source: DraftSourceOut
    context_before: str | None
    context_after: str | None
    collection_name: str


class GapCreate(BaseModel):
    draft_id: int | None = None
    ticket_id: int | None = None
    question: str | None = Field(default=None, max_length=2000)
    missing_information: str | None = Field(default=None, max_length=4000)


class GapOut(ORM):
    id: int
    ticket_id: int | None
    draft_id: int | None
    question: str
    missing_information: str
    status: GapStatus
    created_by: UserRef | None
    resolved_by: UserRef | None
    resolution_note: str | None
    resolved_document_id: int | None
    created_at: datetime
    resolved_at: datetime | None


class PublishIn(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    # Optionally move the ticket along in the same action.
    ticket_status: str | None = Field(default=None, pattern="^(open|pending|resolved)$")


class GapUpdate(BaseModel):
    status: GapStatus
    resolution_note: str | None = Field(default=None, max_length=2000)
    resolved_document_id: int | None = None
