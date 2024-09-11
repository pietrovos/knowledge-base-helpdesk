"""ORM models. Importing this package registers every table on Base.metadata."""

from app.models.identity import Collection, CollectionGrant, Group, GroupMember, Role, User
from app.models.knowledge import Chunk, ChunkEmbedding, Document, DocumentVersion, VersionStatus

__all__ = [
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
