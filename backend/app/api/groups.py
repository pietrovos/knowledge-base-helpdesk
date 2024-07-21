from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.api.deps import DB, AdminUser
from app.models import Group, GroupMember, User
from app.schemas.identity import GroupIn, GroupOut, MemberIn

router = APIRouter(prefix="/api/groups", tags=["groups"])


def _get(db, group_id: int) -> Group:
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    return group


@router.get("", response_model=list[GroupOut])
def list_groups(db: DB, _: AdminUser) -> list[Group]:
    return list(db.scalars(select(Group).order_by(Group.name)))


@router.post("", response_model=GroupOut, status_code=201)
def create_group(body: GroupIn, db: DB, _: AdminUser) -> Group:
    group = Group(name=body.name, description=body.description)
    db.add(group)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A group with that name already exists") from None
    return group


@router.patch("/{group_id}", response_model=GroupOut)
def update_group(group_id: int, body: GroupIn, db: DB, _: AdminUser) -> Group:
    group = _get(db, group_id)
    group.name, group.description = body.name, body.description
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A group with that name already exists") from None
    return group


@router.delete("/{group_id}", status_code=204)
def delete_group(group_id: int, db: DB, _: AdminUser) -> None:
    db.delete(_get(db, group_id))
    db.commit()


@router.post("/{group_id}/members", response_model=GroupOut)
def add_member(group_id: int, body: MemberIn, db: DB, _: AdminUser) -> Group:
    group = _get(db, group_id)
    if not db.get(User, body.user_id):
        raise HTTPException(404, "User not found")
    db.execute(
        insert(GroupMember).values(group_id=group.id, user_id=body.user_id).on_conflict_do_nothing()
    )
    db.commit()
    db.refresh(group)
    return group


@router.delete("/{group_id}/members/{user_id}", response_model=GroupOut)
def remove_member(group_id: int, user_id: int, db: DB, _: AdminUser) -> Group:
    group = _get(db, group_id)
    db.execute(
        delete(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    )
    db.commit()
    db.refresh(group)
    return group
