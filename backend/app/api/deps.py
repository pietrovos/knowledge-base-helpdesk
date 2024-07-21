from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Role, User
from app.security import SESSION_COOKIE, decode_token

DB = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DB, session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None
) -> User:
    user_id = decode_token(session) if session else None
    user = db.get(User, user_id) if user_id else None
    # Deactivation takes effect on the next request, not when the token expires.
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
