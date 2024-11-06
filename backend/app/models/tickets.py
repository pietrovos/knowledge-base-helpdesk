import enum
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin
from app.models.identity import User


class TicketStatus(enum.StrEnum):
    open = "open"
    pending = "pending"  # waiting on the customer
    escalated = "escalated"
    resolved = "resolved"
    closed = "closed"


class TicketPriority(enum.StrEnum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class AuthorType(enum.StrEnum):
    customer = "customer"
    agent = "agent"


class Ticket(TimestampMixin, Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(254), nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status"), default=TicketStatus.open, nullable=False
    )
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority, name="ticket_priority"), default=TicketPriority.normal, nullable=False
    )
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    escalation_reason: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    assignee: Mapped[User | None] = relationship()
    messages: Mapped[list["TicketMessage"]] = relationship(
        back_populates="ticket", order_by="TicketMessage.id", cascade="all, delete-orphan"
    )
    events: Mapped[list["TicketEvent"]] = relationship(
        order_by="TicketEvent.id", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_tickets_status_updated", "status", "updated_at"),
        Index("ix_tickets_assignee", "assignee_id"),
    )


class TicketMessage(TimestampMixin, Base):
    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_type: Mapped[AuthorType] = mapped_column(
        Enum(AuthorType, name="author_type"), nullable=False
    )
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    draft_id: Mapped[int | None] = mapped_column(BigInteger)  # set when published from an AI draft

    ticket: Mapped[Ticket] = relationship(back_populates="messages")
    author: Mapped[User | None] = relationship()


class TicketEvent(TimestampMixin, Base):
    """Append-only activity log: status changes, assignment, escalation, publishing."""

    __tablename__ = "ticket_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    actor: Mapped[User | None] = relationship()
