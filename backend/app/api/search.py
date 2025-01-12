from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import DB, CurrentUser
from app.services.retrieval import retrieve

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchHit(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    collection_name: str
    version: int
    heading: str
    text: str
    similarity: float | None
    keyword_rank: int | None
    score: float


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]
    has_evidence: bool
    embedding_model: str
    latency_ms: int


@router.get("", response_model=SearchResponse)
def search(
    db: DB,
    user: CurrentUser,
    q: Annotated[str, Query(min_length=1, max_length=500)],
    k: Annotated[int, Query(ge=1, le=20)] = 6,
    collection_id: Annotated[list[int] | None, Query()] = None,
) -> SearchResponse:
    r = retrieve(db, user, q, k=k, collection_ids=collection_id)
    return SearchResponse(
        query=q,
        hits=[SearchHit(**vars(c)) for c in r.chunks],
        has_evidence=r.has_evidence,
        embedding_model=r.embedding_model,
        latency_ms=r.latency_ms,
    )
