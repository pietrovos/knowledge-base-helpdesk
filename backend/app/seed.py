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
    "Customer Policies": (
        "Refunds, shipping, warranty and account policies customers ask about.",
        ["Tier 1 Support", "Billing Team"],
    ),
    "Billing Operations": (
        "Internal billing procedures: invoices, chargebacks, credits.",
        ["Billing Team"],
    ),
    "Product Handbook": (
        "How the product works: features, plans, limits, troubleshooting.",
        ["Tier 1 Support", "Billing Team"],
    ),
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
        email: _get_or_create(
            db, User, {"name": name, "role": role, "password_hash": pw}, email=email
        )
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


TICKETS = [
    (
        "Refund for order #48213 still not received",
        "Morgan Blake",
        "morgan.blake@example.com",
        "high",
        "Hi, I returned my headphones 12 days ago and the tracking shows you received them on the 3rd. "
        "When will I see the refund on my card?",
    ),
    (
        "Can I return a gift card?",
        "Priya Natarajan",
        "priya.n@example.com",
        "normal",
        "I bought a $100 gift card by mistake last week. Can I return it for a refund?",
    ),
    (
        "Charged twice for my subscription",
        "Luis Ortega",
        "luis.ortega@example.com",
        "urgent",
        "My bank statement shows two charges of $29 for the Pro plan this month. Please fix this ASAP.",
    ),
]


def seed_tickets(db: Session) -> None:
    from app.models import AuthorType, Ticket, TicketEvent, TicketMessage, TicketPriority

    for subject, name, email, priority, body in TICKETS:
        if db.scalar(select(Ticket.id).where(Ticket.subject == subject)):
            continue
        t = Ticket(
            subject=subject,
            customer_name=name,
            customer_email=email,
            priority=TicketPriority(priority),
        )
        db.add(t)
        db.flush()
        db.add(TicketMessage(ticket_id=t.id, author_type=AuthorType.customer, body=body))
        db.add(TicketEvent(ticket_id=t.id, kind="created", data={"channel": "email"}))
    db.commit()


def run(db: Session) -> None:
    seed_identity(db)
    seed_tickets(db)
