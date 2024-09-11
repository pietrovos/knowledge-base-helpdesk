import enum
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin
from app.models.identity import Collection, User


class VersionStatus(enum.StrEnum):
    queued = "queued"
    processing = "processing"
    ready = "ready"  # the document's current version; its chunks are live
    superseded = "superseded"  # processed, but a newer version replaced it; chunks retired
    failed = "failed"


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    current_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_versions.id", use_alter=True, name="fk_documents_current_version")
    )
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    collection: Mapped[Collection] = relationship()
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        foreign_keys="DocumentVersion.document_id",
        order_by="DocumentVersion.version.desc()",
    )
    current_version: Mapped["DocumentVersion | None"] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )
    created_by: Mapped[User | None] = relationship()

    __table_args__ = (
        Index(
            "uq_documents_live_filename",
            "collection_id",
            "filename",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
    )


class DocumentVersion(TimestampMixin, Base):
    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    s3_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, name="version_status"), default=VersionStatus.queued, nullable=False
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stage: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    document: Mapped[Document] = relationship(back_populates="versions", foreign_keys=[document_id])

    __table_args__ = (UniqueConstraint("document_id", "version", name="uq_version_number"),)


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[int] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship()
    version: Mapped[DocumentVersion] = relationship()

    __table_args__ = (
        UniqueConstraint("version_id", "ordinal", name="uq_chunk_ordinal"),
        Index("ix_chunks_active_document", "document_id", postgresql_where="is_active"),
    )


class ChunkEmbedding(Base):
    """One row per (chunk, embedding model). The column has no fixed dimension; each model gets
    a partial HNSW index on `embedding::vector(dim)` (see migrations), so vector spaces never mix."""

    __tablename__ = "chunk_embeddings"

    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    model: Mapped[str] = mapped_column(String(120), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)


Collection.document_count = column_property(
    select(func.count(Document.id))
    .where(Document.collection_id == Collection.id, Document.deleted_at.is_(None))
    .correlate_except(Document)
    .scalar_subquery()
)
