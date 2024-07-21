import enum

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class Role(enum.StrEnum):
    agent = "agent"
    admin = "admin"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    groups: Mapped[list["Group"]] = relationship(
        secondary="group_members", back_populates="members", order_by="Group.name"
    )


class Group(TimestampMixin, Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    members: Mapped[list[User]] = relationship(
        secondary="group_members", back_populates="groups", order_by=User.name
    )


class GroupMember(Base):
    __tablename__ = "group_members"

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (Index("ix_group_members_user", "user_id"),)


class Collection(TimestampMixin, Base):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    grants: Mapped[list["CollectionGrant"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )


class CollectionGrant(TimestampMixin, Base):
    """Read access to a collection for exactly one principal: a user or a group."""

    __tablename__ = "collection_grants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))

    collection: Mapped[Collection] = relationship(back_populates="grants")
    user: Mapped[User | None] = relationship()
    group: Mapped[Group | None] = relationship()

    __table_args__ = (
        CheckConstraint("(user_id IS NULL) <> (group_id IS NULL)", name="grant_one_principal"),
        Index(
            "uq_grant_user",
            "collection_id",
            "user_id",
            unique=True,
            postgresql_where="user_id IS NOT NULL",
        ),
        Index(
            "uq_grant_group",
            "collection_id",
            "group_id",
            unique=True,
            postgresql_where="group_id IS NOT NULL",
        ),
        Index("ix_grants_user", "user_id"),
        Index("ix_grants_group", "group_id"),
    )
