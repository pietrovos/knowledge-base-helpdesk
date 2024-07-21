from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DB, AdminUser, CurrentUser
from app.models import Collection, CollectionGrant, Group, User
from app.schemas.identity import CollectionIn, CollectionOut, GrantIn, GrantOut
from app.services.permissions import can_read_collection, readable_collection_ids

router = APIRouter(prefix="/api/collections", tags=["collections"])


def get_readable_collection(db, user: User, collection_id: int) -> Collection:
    # Unreadable and missing collections both return 404 so IDs can't be probed.
    if not can_read_collection(db, user, collection_id):
        raise HTTPException(404, "Collection not found")
    return db.get(Collection, collection_id)


@router.get("", response_model=list[CollectionOut])
def list_collections(db: DB, user: CurrentUser) -> list[Collection]:
    q = select(Collection).where(Collection.id.in_(readable_collection_ids(user)))
    return list(db.scalars(q.order_by(Collection.name)))


@router.get("/{collection_id}", response_model=CollectionOut)
def get_collection(collection_id: int, db: DB, user: CurrentUser) -> Collection:
    return get_readable_collection(db, user, collection_id)


@router.post("", response_model=CollectionOut, status_code=201)
def create_collection(body: CollectionIn, db: DB, _: AdminUser) -> Collection:
    c = Collection(name=body.name, description=body.description)
    db.add(c)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A collection with that name already exists") from None
    return c


@router.patch("/{collection_id}", response_model=CollectionOut)
def update_collection(collection_id: int, body: CollectionIn, db: DB, _: AdminUser) -> Collection:
    c = db.get(Collection, collection_id)
    if not c:
        raise HTTPException(404, "Collection not found")
    c.name, c.description = body.name, body.description
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A collection with that name already exists") from None
    return c


@router.get("/{collection_id}/grants", response_model=list[GrantOut])
def list_grants(collection_id: int, db: DB, _: AdminUser) -> list[CollectionGrant]:
    q = select(CollectionGrant).where(CollectionGrant.collection_id == collection_id)
    return list(db.scalars(q.order_by(CollectionGrant.id)))


@router.post("/{collection_id}/grants", response_model=GrantOut, status_code=201)
def add_grant(collection_id: int, body: GrantIn, db: DB, _: AdminUser) -> CollectionGrant:
    if not db.get(Collection, collection_id):
        raise HTTPException(404, "Collection not found")
    if body.user_id is not None and not db.get(User, body.user_id):
        raise HTTPException(404, "User not found")
    if body.group_id is not None and not db.get(Group, body.group_id):
        raise HTTPException(404, "Group not found")
    grant = CollectionGrant(
        collection_id=collection_id, user_id=body.user_id, group_id=body.group_id
    )
    db.add(grant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That principal already has access") from None
    return grant


@router.delete("/{collection_id}/grants/{grant_id}", status_code=204)
def revoke_grant(collection_id: int, grant_id: int, db: DB, _: AdminUser) -> None:
    grant = db.get(CollectionGrant, grant_id)
    if not grant or grant.collection_id != collection_id:
        raise HTTPException(404, "Grant not found")
    db.delete(grant)
    db.commit()
