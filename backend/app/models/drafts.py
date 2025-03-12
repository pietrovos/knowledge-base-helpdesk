import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin
from app.models.identity import User


class DraftStatus(enum.StrEnum):
    pending = "pending"
    ready = "ready"  # grounded answer with at least one valid citation
    insufficient_evidence = "insufficient_evidence"
    failed = "failed"  # provider error / timeout / circuit open; ticket stays usable
    published = "published"
    discarded = "discarded"


class Draft(TimestampMixin, Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[DraftStatus] = mapped_column(
        Enum(DraftStatus, name="draft_status"), default=DraftStatus.pending, nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    custom_question: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reply: Mapped[str] = mapped_column(
        Text, default="", nullable=False
    )  # validated, with [id] markers
    raw_reply: Mapped[str] = mapped_column(
        Text, default="", nullable=False
    )  # as the model wrote it
    missing_information: Mapped[str] = mapped_column(Text, default="", nullable=False)
    invalid_citation_ids: Mapped[list[int]] = mapped_column(
        ARRAY(BigInteger), default=list, nullable=False
    )
    error: Mapped[str | None] = mapped_column(Text)
    error_kind: Mapped[str | None] = mapped_column(String(40))
    decided_by: Mapped[str | None] = mapped_column(
        String(40)
    )  # "model" | "evidence_gate" | "validator"
    provider: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(80))
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    retrieval_ms: Mapped[int | None] = mapped_column(Integer)
    generation_ms: Mapped[int | None] = mapped_column(Integer)
    best_similarity: Mapped[float | None] = mapped_column(Float)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_message_id: Mapped[int | None] = mapped_column(BigInteger)
    published_text: Mapped[str | None] = mapped_column(Text)
    was_edited: Mapped[bool | None] = mapped_column(Boolean)

    requested_by: Mapped[User | None] = relationship()
    sources: Mapped[list["DraftSource"]] = relationship(
        order_by="DraftSource.rank", cascade="all, delete-orphan"
    )


class DraftSource(Base):
    """A chunk retrieved for a draft, snapshotted exactly as the model saw it.

    This is both the validation set for citations (a citation is valid only if its chunk is
    here) and the audit trail for the evidence viewer.
    """

    __tablename__ = "draft_sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    draft_id: Mapped[int] = mapped_column(
        ForeignKey("drafts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("chunks.id", ondelete="SET NULL"))
    chunk_ref: Mapped[int] = mapped_column(BigInteger, nullable=False)  # survives chunk deletion
    collection_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    document_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    document_title: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    similarity: Mapped[float | None] = mapped_column(Float)
    keyword_rank: Mapped[int | None] = mapped_column(Integer)
    cited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (Index("ix_draft_sources_chunk", "chunk_ref"),)


class GapStatus(enum.StrEnum):
    open = "open"
    resolved = "resolved"
    dismissed = "dismissed"


class KnowledgeGap(TimestampMixin, Base):
    """A question the knowledge base couldn't answer: work for whoever owns the docs."""

    __tablename__ = "knowledge_gaps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id", ondelete="SET NULL"))
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("drafts.id", ondelete="SET NULL"))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    custom_question: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    missing_information: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[GapStatus] = mapped_column(
        Enum(GapStatus, name="gap_status"), default=GapStatus.open, nullable=False
    )
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])
    resolved_by: Mapped[User | None] = relationship(foreign_keys=[resolved_by_id])

    __table_args__ = (Index("ix_gaps_status", "status", "created_at"),)


class LLMCall(TimestampMixin, Base):
    """One row per model or embedding call: the basis for latency/token/cost dashboards."""

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    purpose: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # draft | embed_query | eval_judge
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # ok | error | timeout | refused | circuit_open
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(120))
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("drafts.id", ondelete="SET NULL"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (Index("ix_llm_calls_created", "created_at"),)
