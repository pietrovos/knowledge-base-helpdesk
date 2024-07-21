from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DB, AdminUser, CurrentUser
from app.models import Role, User
from app.schemas.identity import UserCreate, UserOut, UserRef, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: DB, _: AdminUser) -> list[User]:
    return list(db.scalars(select(User).order_by(User.name)))


@router.get("/directory", response_model=list[UserRef])
def directory(db: DB, _: CurrentUser) -> list[User]:
    """Active users, for assignment pickers. Visible to every signed-in user."""
    return list(db.scalars(select(User).where(User.is_active).order_by(User.name)))


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: DB, _: AdminUser) -> User:
    user = User(
        email=body.email, name=body.name, role=body.role, password_hash=hash_password(body.password)
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A user with that email already exists") from None
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: DB, admin: AdminUser) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == admin.id and (body.role == Role.agent or body.is_active is False):
        raise HTTPException(400, "You cannot demote or deactivate yourself")
    if body.name is not None:
        user.name = body.name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    db.commit()
    return user
