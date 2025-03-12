"""ORM models. Importing this package registers every table on Base.metadata."""

from app.models.drafts import Draft, DraftSource, DraftStatus, GapStatus, KnowledgeGap, LLMCall
from app.models.identity import Collection, CollectionGrant, Group, GroupMember, Role, User
from app.models.knowledge import Chunk, ChunkEmbedding, Document, DocumentVersion, VersionStatus
from app.models.tickets import (
    AuthorType,
    Ticket,
    TicketEvent,
    TicketMessage,
    TicketPriority,
    TicketStatus,
)

__all__ = [
    "Draft",
    "DraftSource",
    "DraftStatus",
    "GapStatus",
    "KnowledgeGap",
    "LLMCall",
    "AuthorType",
    "Ticket",
    "TicketEvent",
    "TicketMessage",
    "TicketPriority",
    "TicketStatus",
    "Chunk",
    "ChunkEmbedding",
    "Collection",
    "CollectionGrant",
    "Document",
    "DocumentVersion",
    "Group",
    "GroupMember",
    "Role",
    "User",
    "VersionStatus",
]
