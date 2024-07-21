from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.config import get_settings
from app.models import User
from app.schemas.identity import LoginIn, UserOut
from app.security import SESSION_COOKIE, create_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Verified against when the email is unknown so response time doesn't reveal which emails exist.
_DUMMY_HASH = hash_password("timing-equalizer")


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response, db: DB) -> User:
    user = db.scalar(select(User).where(User.email == body.email))
    ok = verify_password(user.password_hash if user else _DUMMY_HASH, body.password)
    if not user or not ok or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    s = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        create_token(user.id),
        httponly=True,
        samesite="lax",
        secure=s.cookie_secure,
        max_age=s.jwt_ttl_minutes * 60,
        path="/",
    )
    return user


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
