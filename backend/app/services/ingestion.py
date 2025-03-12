"""Document ingestion: upload → S3 → (Celery) chunk → embed → store → activate.

Invariants
- A document's live chunks always come from exactly one version (its current version).
- Activation is a single transaction under a row lock on the document: new chunks go live and
  the previous version's chunks are retired together, so retrieval never sees a mix.
- Re-processing a version is idempotent: its chunks are rebuilt by (version_id, ordinal).
- If a newer upload fails, the previous version stays live.
"""

import hashlib
import logging
import os
import random
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    Chunk,
    ChunkEmbedding,
    Collection,
    Document,
    DocumentVersion,
    User,
    VersionStatus,
)
from app.services import storage
from app.services.chunking import chunk_document, normalize
from app.services.embeddings import get_embedder

log = logging.getLogger(__name__)

ALLOWED_TYPES = {".md": "text/markdown", ".markdown": "text/markdown", ".txt": "text/plain"}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
EMBED_BATCH = 32
MAX_ATTEMPTS = 5


class UploadRejected(ValueError):
    pass


class TransientIngestError(Exception):
    """Worth retrying: storage or embedding provider hiccup."""


class PermanentIngestError(Exception):
    """Retrying won't help: unreadable or empty content."""


def backoff_seconds(retries: int) -> float:
    """Exponential backoff with jitter: ~2s, 4s, 8s, 16s … capped at 60s."""
    return min(60.0, 2.0 * 2**retries) + random.uniform(0, 1)


def validate_upload(filename: str, data: bytes) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_TYPES:
        raise UploadRejected("Only Markdown (.md) and plain text (.txt) files are supported")
    if not data:
        raise UploadRejected("The file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadRejected("Files must be 2 MB or smaller")
    try:
        data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise UploadRejected("The file must be UTF-8 encoded text") from None
    return ALLOWED_TYPES[ext]


def _title_from(filename: str, text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()[:200]
    base = os.path.splitext(os.path.basename(filename))[0]
    return base.replace("-", " ").replace("_", " ").strip().title()[:200] or "Untitled"


def create_version(
    db: Session,
    *,
    collection: Collection,
    filename: str,
    data: bytes,
    user: User,
    title: str | None = None,
    document: Document | None = None,
) -> tuple[Document, DocumentVersion, bool]:
    """Store an upload as a new version. Returns (document, version, created).

    Uploading a file whose name matches a live document in the collection versions that
    document. Re-uploading identical bytes returns the existing version (created=False).
    """
    content_type = validate_upload(filename, data)
    filename = os.path.basename(filename)[:255]
    sha = hashlib.sha256(data).hexdigest()

    if document is None:
        document = db.scalar(
            select(Document)
            .where(
                Document.collection_id == collection.id,
                Document.filename == filename,
                Document.deleted_at.is_(None),
            )
            .with_for_update()
        )
    else:
        db.execute(select(Document.id).where(Document.id == document.id).with_for_update())

    if document is None:
        text = data.decode("utf-8-sig")
        document = Document(
            collection_id=collection.id,
            filename=filename,
            title=(title or _title_from(filename, text)),
            created_by_id=user.id,
        )
        db.add(document)
        db.flush()
    else:
        latest = db.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version.desc())
            .limit(1)
        )
        if latest and latest.sha256 == sha and latest.status != VersionStatus.failed:
            db.rollback()
            return document, latest, False
        if title:
            document.title = title

    number = (
        db.scalar(
            select(func.max(DocumentVersion.version)).where(
                DocumentVersion.document_id == document.id
            )
        )
        or 0
    ) + 1
    ext = os.path.splitext(filename)[1].lower()
    key = f"collections/{collection.id}/documents/{document.id}/v{number}-{sha[:12]}{ext}"
    version = DocumentVersion(
        document_id=document.id,
        version=number,
        s3_key=key,
        content_type=content_type,
        size_bytes=len(data),
        sha256=sha,
        created_by_id=user.id,
    )
    db.add(version)
    db.flush()
    storage.put_object(key, data, content_type)  # before commit: no row without its object
    db.commit()
    return document, version, True


def enqueue(version_id: int) -> bool:
    from app.worker.tasks import process_version_task

    try:
        process_version_task.delay(version_id)
        return True
    except Exception:  # broker unavailable: the version stays queued and can be retried
        log.exception("could not enqueue ingestion for version %s", version_id)
        return False


def _set_state(version_id: int, **values) -> None:
    with SessionLocal() as db:
        db.execute(update(DocumentVersion).where(DocumentVersion.id == version_id).values(**values))
        db.commit()


def mark_failed(version_id: int, error: str) -> None:
    _set_state(version_id, status=VersionStatus.failed, stage="failed", error=error[:2000])


def mark_retrying(version_id: int, error: str, delay: float) -> None:
    _set_state(
        version_id,
        status=VersionStatus.queued,
        stage="retrying",
        error=f"{error[:1900]} (retrying in {delay:.0f}s)",
    )


def process_version(version_id: int) -> None:
    with SessionLocal() as db:
        version = db.get(DocumentVersion, version_id)
        if version is None:
            return
        key, content_type = version.s3_key, version.content_type
        document_title = version.document.title
    _set_state(
        version_id,
        status=VersionStatus.processing,
        stage="downloading",
        progress=5,
        attempts=DocumentVersion.attempts + 1,
        error=None,
    )

    try:
        raw = storage.get_object(key)
    except Exception as e:
        raise TransientIngestError(f"Could not read the file from storage: {e}") from e
    try:
        text = normalize(raw.decode("utf-8-sig"))
    except UnicodeDecodeError as e:
        raise PermanentIngestError("The file is not valid UTF-8 text") from e

    _set_state(version_id, stage="chunking", progress=15)
    spans = chunk_document(text, markdown=content_type == "text/markdown")
    if not spans:
        raise PermanentIngestError("The document has no text content")

    embedder = get_embedder()
    vectors: list[list[float]] = []
    for i in range(0, len(spans), EMBED_BATCH):
        batch = spans[i : i + EMBED_BATCH]
        # The heading path and title give short chunks the context they need to be found.
        inputs = [f"{document_title}\n{s.heading}\n\n{s.text}" for s in batch]
        try:
            vectors.extend(embedder.embed_documents(inputs))
        except Exception as e:
            raise TransientIngestError(f"Embedding provider error: {e}") from e
        done = min(len(spans), i + EMBED_BATCH)
        _set_state(version_id, stage="embedding", progress=20 + int(70 * done / len(spans)))

    _set_state(version_id, stage="activating", progress=95)
    _store_and_activate(version_id, spans, vectors, embedder.name)


def _store_and_activate(version_id: int, spans, vectors, model: str) -> None:
    with SessionLocal() as db, db.begin():
        version = db.get(DocumentVersion, version_id)
        doc = db.scalar(
            select(Document).where(Document.id == version.document_id).with_for_update()
        )
        db.refresh(version)

        # Upsert by (version_id, ordinal) so re-processing keeps chunk IDs stable: drafts that
        # cited a chunk keep pointing at the same row.
        rows = [
            {
                "document_id": doc.id,
                "version_id": version_id,
                "ordinal": s.ordinal,
                "heading": s.heading,
                "text": s.text,
                "char_start": s.char_start,
                "char_end": s.char_end,
                "token_estimate": s.token_estimate,
                "is_active": False,
            }
            for s in spans
        ]
        stmt = pg_insert(Chunk).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_chunk_ordinal",
            set_={
                c: stmt.excluded[c]
                for c in ("heading", "text", "char_start", "char_end", "token_estimate")
            },
        ).returning(Chunk.id, Chunk.ordinal)
        ids = {ordinal: cid for cid, ordinal in db.execute(stmt).all()}
        # A changed chunker may produce fewer chunks: drop this version's leftovers.
        db.execute(delete(Chunk).where(Chunk.version_id == version_id, Chunk.ordinal >= len(spans)))
        emb = pg_insert(ChunkEmbedding).values(
            [
                {"chunk_id": ids[s.ordinal], "model": model, "embedding": v}
                for s, v in zip(spans, vectors, strict=True)
            ]
        )
        db.execute(
            emb.on_conflict_do_update(
                index_elements=["chunk_id", "model"], set_={"embedding": emb.excluded.embedding}
            )
        )

        current = (
            db.get(DocumentVersion, doc.current_version_id) if doc.current_version_id else None
        )
        is_newest = current is None or version.version >= current.version
        if doc.deleted_at is None and is_newest:
            db.execute(
                update(Chunk)
                .where(Chunk.document_id == doc.id)
                .values(is_active=Chunk.version_id == version_id)
            )
            if current is not None and current.id != version_id:
                current.status = VersionStatus.superseded
            doc.current_version_id = version_id
            version.status = VersionStatus.ready
        else:
            version.status = VersionStatus.superseded
        version.stage = "done"
        version.progress = 100
        version.error = None
        version.chunk_count = len(spans)
        version.embedding_model = model
        version.processed_at = datetime.now(UTC)


def delete_document(db: Session, document: Document) -> None:
    """Soft delete. Chunks are retired in the same transaction, so retrieval stops using the
    document immediately; rows and the S3 object remain for audit of past cited replies."""
    document.deleted_at = datetime.now(UTC)
    db.execute(update(Chunk).where(Chunk.document_id == document.id).values(is_active=False))
    db.commit()
