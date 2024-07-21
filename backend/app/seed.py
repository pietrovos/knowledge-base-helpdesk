"""Idempotent demo data. Run with: python -m app.cli seed"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Collection, CollectionGrant, Group, GroupMember, Role, User
from app.security import hash_password

DEMO_PASSWORD = "supportlens-demo"

USERS = [
    ("admin@supportlens.dev", "Dana Whitfield", Role.admin),
    ("alex@supportlens.dev", "Alex Rivera", Role.agent),
    ("sam@supportlens.dev", "Sam Patel", Role.agent),
    ("jordan@supportlens.dev", "Jordan Lee", Role.agent),
]

GROUPS = {
    "Tier 1 Support": ["alex@supportlens.dev", "jordan@supportlens.dev"],
    "Billing Team": ["sam@supportlens.dev"],
}

COLLECTIONS = {
    "Customer Policies": ("Refunds, shipping, warranty and account policies customers ask about.",
                          ["Tier 1 Support", "Billing Team"]),
    "Billing Operations": ("Internal billing procedures: invoices, chargebacks, credits.",
                           ["Billing Team"]),
    "Product Handbook": ("How the product works: features, plans, limits, troubleshooting.",
                         ["Tier 1 Support", "Billing Team"]),
    "Security & Compliance": ("Internal security procedures. Restricted.", []),
}


def _get_or_create(db: Session, model, defaults: dict | None = None, **keys):
    obj = db.scalar(select(model).filter_by(**keys))
    if obj is None:
        obj = model(**keys, **(defaults or {}))
        db.add(obj)
        db.flush()
    return obj


def seed_identity(db: Session) -> None:
    pw = hash_password(DEMO_PASSWORD)
    users = {
        email: _get_or_create(db, User, {"name": name, "role": role, "password_hash": pw}, email=email)
        for email, name, role in USERS
    }
    groups = {name: _get_or_create(db, Group, name=name) for name in GROUPS}
    for gname, emails in GROUPS.items():
        for email in emails:
            _get_or_create(db, GroupMember, group_id=groups[gname].id, user_id=users[email].id)
    for cname, (desc, gnames) in COLLECTIONS.items():
        c = _get_or_create(db, Collection, {"description": desc}, name=cname)
        for gname in gnames:
            _get_or_create(db, CollectionGrant, collection_id=c.id, group_id=groups[gname].id)
    db.commit()


def run(db: Session) -> None:
    seed_identity(db)
