"""Authorized hybrid retrieval.

Every candidate list is produced by a SQL query whose WHERE clause already contains the
authorization predicate (readable collection, live document, active chunk). Ranking and LIMIT
happen after that filter inside Postgres, so content the user can't read is never loaded into
the application, never ranked, and therefore can never reach a prompt.

Two candidate lists are fused with Reciprocal Rank Fusion:
- dense: cosine distance on this deployment's embedding model (partial HNSW index per model)
- lexical: Postgres full-text search, which catches exact terms (plan names, error codes) that
  small embedding models blur
"""

import time
from dataclasses import dataclass, field

from sqlalchemy import ColumnElement, cast, func, select, text
from sqlalchemy.orm import Session

from app.models import Chunk, ChunkEmbedding, Collection, Document, DocumentVersion, User
from app.services.embeddings import Embedder, get_embedder, tokenize
from app.services.permissions import readable_collection_ids

CANDIDATES = 30
RRF_K = 60


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document_title: str
    collection_id: int
    collection_name: str
    version: int
    heading: str
    text: str
    similarity: float | None  # cosine similarity from the dense query, if it found this chunk
    keyword_rank: int | None  # 1-based rank in the lexical list, if it found this chunk
    score: float  # fused RRF score used for ordering


@dataclass
class RetrievalResult:
    query: str
    chunks: list[RetrievedChunk]
    embedding_model: str
    min_similarity: float
    latency_ms: int
    best_similarity: float = 0.0
    collection_ids: list[int] = field(default_factory=list)

    @property
    def has_evidence(self) -> bool:
        """Cheap pre-LLM gate: is anything retrieved plausibly about the question?"""
        return bool(self.chunks) and self.best_similarity >= self.min_similarity


def authorized(user: User, collection_ids: list[int] | None = None) -> list[ColumnElement[bool]]:
    """The authorization predicate shared by every retrieval query."""
    preds = [
        Chunk.is_active.is_(True),
        Document.deleted_at.is_(None),
        Document.collection_id.in_(readable_collection_ids(user)),
    ]
    if collection_ids:
        preds.append(Document.collection_id.in_(collection_ids))
    return preds


def _columns():
    return (
        Chunk.id,
        Chunk.document_id,
        Document.title,
        Document.collection_id,
        Collection.name,
        DocumentVersion.version,
        Chunk.heading,
        Chunk.text,
    )


def _base(stmt):
    return (
        stmt.join(Document, Document.id == Chunk.document_id)
        .join(Collection, Collection.id == Document.collection_id)
        .join(DocumentVersion, DocumentVersion.id == Chunk.version_id)
    )


def _dense(db: Session, user: User, embedder: Embedder, query: str, collection_ids, limit: int):
    qvec = embedder.embed_query(query)
    # Must match the partial index expression: embedding::vector(dim) with a model filter.
    distance = cast(ChunkEmbedding.embedding, _vector_type(embedder.dim)).cosine_distance(qvec)
    stmt = _base(
        select(*_columns(), distance.label("distance"))
        .select_from(ChunkEmbedding)
        .join(Chunk, Chunk.id == ChunkEmbedding.chunk_id)
    )
    stmt = stmt.where(ChunkEmbedding.model == embedder.name, *authorized(user, collection_ids))
    return db.execute(stmt.order_by(distance).limit(limit)).all()


def _lexical(db: Session, user: User, query: str, collection_ids, limit: int):
    terms = sorted(set(tokenize(query)))
    if not terms:
        return []
    tsquery = func.to_tsquery("english", " | ".join(terms))
    rank = func.ts_rank_cd(Chunk.tsv, tsquery)
    stmt = _base(select(*_columns(), rank.label("rank")).select_from(Chunk))
    stmt = stmt.where(Chunk.tsv.op("@@")(tsquery), *authorized(user, collection_ids))
    return db.execute(stmt.order_by(rank.desc(), Chunk.id).limit(limit)).all()


def _vector_type(dim: int):
    from pgvector.sqlalchemy import Vector

    return Vector(dim)


def retrieve(
    db: Session,
    user: User,
    query: str,
    *,
    k: int = 6,
    collection_ids: list[int] | None = None,
    embedder: Embedder | None = None,
) -> RetrievalResult:
    embedder = embedder or get_embedder()
    started = time.perf_counter()
    with db.begin_nested() if db.in_transaction() else db.begin():
        # pgvector ≥0.8: keep scanning the HNSW graph until enough rows pass the WHERE clause,
        # so selective permission filters don't starve the result set.
        db.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
        db.execute(text("SET LOCAL hnsw.ef_search = 100"))
        dense = _dense(db, user, embedder, query, collection_ids, CANDIDATES)
        lexical = _lexical(db, user, query, collection_ids, CANDIDATES)

    fused: dict[int, RetrievedChunk] = {}

    def entry(row) -> RetrievedChunk:
        if row[0] not in fused:
            fused[row[0]] = RetrievedChunk(
                chunk_id=row[0],
                document_id=row[1],
                document_title=row[2],
                collection_id=row[3],
                collection_name=row[4],
                version=row[5],
                heading=row[6],
                text=row[7],
                similarity=None,
                keyword_rank=None,
                score=0.0,
            )
        return fused[row[0]]

    # relaxed_order may return near-sorted rows; sort by the true distance before ranking.
    for rank, row in enumerate(sorted(dense, key=lambda r: r.distance), start=1):
        c = entry(row)
        c.similarity = round(1.0 - float(row.distance), 4)
        c.score += 1.0 / (RRF_K + rank)
    for rank, row in enumerate(lexical, start=1):
        c = entry(row)
        c.keyword_rank = rank
        c.score += 1.0 / (RRF_K + rank)

    chunks = sorted(fused.values(), key=lambda c: (-c.score, c.chunk_id))[:k]
    return RetrievalResult(
        query=query,
        chunks=chunks,
        embedding_model=embedder.name,
        min_similarity=embedder.min_similarity,
        latency_ms=int((time.perf_counter() - started) * 1000),
        best_similarity=max((c.similarity or 0.0 for c in chunks), default=0.0),
        collection_ids=sorted({c.collection_id for c in chunks}),
    )
