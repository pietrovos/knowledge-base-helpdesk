"""Single source of truth for "which collections can this user read".

Both the collection API and the retrieval query embed `readable_collection_ids` as a SQL
subquery, so access checks always run inside the database against current grants.
"""

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.models import Collection, CollectionGrant, GroupMember, Role, User


def readable_collection_ids(user: User) -> Select[tuple[int]]:
    if user.role == Role.admin:
        return select(Collection.id)
    user_groups = select(GroupMember.group_id).where(GroupMember.user_id == user.id)
    return select(CollectionGrant.collection_id).where(
        or_(CollectionGrant.user_id == user.id, CollectionGrant.group_id.in_(user_groups))
    )


def can_read_collection(db: Session, user: User, collection_id: int) -> bool:
    q = select(Collection.id).where(
        Collection.id == collection_id, Collection.id.in_(readable_collection_ids(user))
    )
    return db.execute(q).first() is not None
