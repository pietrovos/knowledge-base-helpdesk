import itertools

from app.db import SessionLocal
from app.models import Collection, CollectionGrant, Group, GroupMember, Role, User
from app.security import hash_password

PASSWORD = "correct-horse-battery"
_seq = itertools.count(1)
_HASH = hash_password(PASSWORD)


def make_user(role: Role = Role.agent, *, name: str | None = None, active: bool = True) -> User:
    n = next(_seq)
    with SessionLocal() as db:
        u = User(email=f"user{n}@example.com", name=name or f"User {n}", role=role,
                 password_hash=_HASH, is_active=active)
        db.add(u)
        db.commit()
        return u


def make_group(name: str, *members: User) -> Group:
    with SessionLocal() as db:
        g = Group(name=name)
        db.add(g)
        db.flush()
        for m in members:
            db.add(GroupMember(group_id=g.id, user_id=m.id))
        db.commit()
        return g


def make_collection(name: str, *, users: tuple[User, ...] = (), groups: tuple[Group, ...] = ()) -> Collection:
    with SessionLocal() as db:
        c = Collection(name=name)
        db.add(c)
        db.flush()
        for u in users:
            db.add(CollectionGrant(collection_id=c.id, user_id=u.id))
        for g in groups:
            db.add(CollectionGrant(collection_id=c.id, group_id=g.id))
        db.commit()
        return c


def login(client, user: User) -> None:
    r = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 200, r.text
