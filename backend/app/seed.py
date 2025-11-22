"""Idempotent demo data. Run with: python -m app.cli seed"""

from pathlib import Path

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
    {
        "subject": "Refund for order #48213 still not received",
        "customer": ("Morgan Blake", "morgan.blake@example.com"),
        "priority": "high",
        "age_hours": 5,
        "body": "Hi, I returned my headphones 12 days ago and the tracking shows you received them on the 3rd. "
        "When will I see the refund on my card?",
    },
    {
        "subject": "Can I return a gift card?",
        "customer": ("Priya Natarajan", "priya.n@example.com"),
        "age_hours": 7,
        "body": "I bought a $100 gift card by mistake last week. Can I return it for a refund?",
    },
    {
        "subject": "Charged twice for my subscription",
        "customer": ("Luis Ortega", "luis.ortega@example.com"),
        "priority": "urgent",
        "age_hours": 2,
        "body": "My bank statement shows two charges of $9.99 for Kestrel Cloud Pro this month. Please fix this ASAP.",
    },
    {
        "subject": "Earbuds keep disconnecting from my Pixel",
        "customer": ("Hannah Kim", "hannah.kim@example.com"),
        "age_hours": 3,
        "body": "Since last week my Kestrel Buds drop the connection to my Android phone every few "
        "minutes. They used to work fine. What can I do?",
    },
    {
        "subject": "Wrong shipping address on order #50122",
        "customer": ("Tom Becker", "tom.becker@example.com"),
        "priority": "high",
        "age_hours": 0.3,
        "body": "I just placed an order and noticed it's going to my old apartment. Can you change the address?",
    },
    {
        "subject": "Battery only lasts 3 hours now",
        "customer": ("Aisha Rahman", "aisha.r@example.com"),
        "age_hours": 26,
        "body": "My Over-Ear headphones are 14 months old and the battery now dies after about 3 hours. "
        "They used to last all week. Is this covered by the warranty?",
    },
    {
        "subject": "Do you ship to Brazil?",
        "customer": ("Rafael Souza", "rafael.souza@example.com"),
        "priority": "low",
        "age_hours": 30,
        "body": "Olá! I'd love to order the Buds Pro. Do you ship to São Paulo?",
    },
    {
        "subject": "Refund for annual Pro plan",
        "customer": ("Grace Liu", "grace.liu@example.com"),
        "age_hours": 9,
        "body": "I upgraded to the annual Pro plan 4 days ago but I don't really use the extra features. "
        "Can I get my $99 back?",
    },
    {
        "subject": "Package says delivered but it isn't here",
        "customer": ("Daniel Okafor", "d.okafor@example.com"),
        "priority": "high",
        "age_hours": 4,
        "body": "Tracking for order #49877 says delivered yesterday at 2pm but there is nothing at my door or with my "
        "neighbours. The order was $129.",
    },
    {
        "subject": "Gift wrapping for a birthday order?",
        "customer": ("Elena Petrova", "elena.p@example.com"),
        "priority": "low",
        "age_hours": 12,
        "body": "I'm ordering the Over-Ear headphones as a birthday present. Can you gift wrap them and add a note?",
    },
    {
        "subject": "Someone logged into my account",
        "customer": ("Marcus Webb", "marcus.webb@example.com"),
        "priority": "urgent",
        "age_hours": 1,
        "status": "escalated",
        "escalation_reason": "Possible account takeover: needs the security procedure.",
        "body": "I got an email that my account email was changed, but I didn't do that. I can't log in anymore.",
    },
    {
        "subject": "Headband cracked after a drop",
        "customer": ("Sofia Marino", "sofia.marino@example.com"),
        "age_hours": 50,
        "status": "pending",
        "assignee": "alex@supportlens.dev",
        "body": "I dropped my headphones from my desk and the headband cracked. Can you repair them under warranty?",
        "reply": "Hi Sofia, I'm sorry to hear that. Could you send a photo of the crack and your order number? "
        "I'll check what options we have.",
    },
    {
        "subject": "Lost my right earbud",
        "customer": ("Kevin Tran", "kevin.tran@example.com"),
        "priority": "low",
        "age_hours": 72,
        "status": "resolved",
        "assignee": "jordan@supportlens.dev",
        "body": "I lost my right earbud on the train. Do I need to buy a whole new pair?",
        "reply": "Hi Kevin, no need for a new pair: you can buy a single replacement earbud for $39 from "
        "Account > Support > Replacement parts.",
    },
    {
        "subject": "Student discount?",
        "customer": ("Olivia Brooks", "olivia.brooks@example.edu"),
        "priority": "low",
        "age_hours": 20,
        "body": "Hi! Do you have a student discount on the Buds Pro?",
    },
    {
        "subject": "Factory reset isn't working",
        "customer": ("Ben Carter", "ben.carter@example.com"),
        "age_hours": 6,
        "assignee": "jordan@supportlens.dev",
        "body": "I tried to reset my earbuds by holding the button but the light never flashes amber. How long do I hold it?",
    },
    {
        "subject": "Customs fees on my order to Germany",
        "customer": ("Lena Fischer", "lena.fischer@example.de"),
        "age_hours": 15,
        "body": "The courier is asking me for 23 euros in import fees. I thought shipping was "
        "included. Do I have to pay this?",
    },
]


def seed_tickets(db: Session) -> None:
    from datetime import UTC, datetime, timedelta

    from app.models import (
        AuthorType,
        Ticket,
        TicketEvent,
        TicketMessage,
        TicketPriority,
        TicketStatus,
    )

    users = {u.email: u for u in db.scalars(select(User))}
    now = datetime.now(UTC)
    for spec in TICKETS:
        if db.scalar(select(Ticket.id).where(Ticket.subject == spec["subject"])):
            continue
        created = now - timedelta(hours=spec["age_hours"])
        assignee = users.get(spec.get("assignee", ""))
        name, email = spec["customer"]
        t = Ticket(
            subject=spec["subject"],
            customer_name=name,
            customer_email=email,
            priority=TicketPriority(spec.get("priority", "normal")),
            status=TicketStatus(spec.get("status", "open")),
            escalation_reason=spec.get("escalation_reason"),
            assignee_id=assignee.id if assignee else None,
            created_at=created,
            updated_at=created,
        )
        db.add(t)
        db.flush()
        db.add(
            TicketMessage(
                ticket_id=t.id,
                author_type=AuthorType.customer,
                body=spec["body"],
                created_at=created,
            )
        )
        db.add(
            TicketEvent(
                ticket_id=t.id, kind="created", data={"channel": "email"}, created_at=created
            )
        )
        if assignee:
            db.add(
                TicketEvent(
                    ticket_id=t.id,
                    actor_id=assignee.id,
                    kind="assigned",
                    created_at=created,
                    data={"assignee_id": assignee.id, "assignee_name": assignee.name},
                )
            )
        if spec.get("reply") and assignee:
            replied = created + timedelta(minutes=40)
            db.add(
                TicketMessage(
                    ticket_id=t.id,
                    author_type=AuthorType.agent,
                    author_id=assignee.id,
                    body=spec["reply"],
                    created_at=replied,
                )
            )
            t.updated_at = replied
        if t.status != TicketStatus.open:
            data = {"from": "open", "to": t.status.value}
            if spec.get("escalation_reason"):
                data["reason"] = spec["escalation_reason"]
            db.add(
                TicketEvent(
                    ticket_id=t.id,
                    actor_id=assignee.id if assignee else None,
                    kind="status_changed",
                    data=data,
                    created_at=created + timedelta(minutes=45),
                )
            )
    db.commit()


SEED_DIR = Path(__file__).parent / "seed_data"
FOLDERS = {
    "customer-policies": "Customer Policies",
    "product-handbook": "Product Handbook",
    "billing-operations": "Billing Operations",
    "security-compliance": "Security & Compliance",
}


def seed_documents(db: Session, *, log=print) -> None:
    """Upload every seed document and ingest it synchronously (no worker needed)."""
    from app.models import DocumentVersion, VersionStatus
    from app.services import ingestion, storage

    storage.ensure_bucket()
    admin = db.scalar(select(User).where(User.email == USERS[0][0]))
    for folder, cname in FOLDERS.items():
        collection = db.scalar(select(Collection).where(Collection.name == cname))
        for path in sorted((SEED_DIR / folder).glob("*.md")):
            _, version, created = ingestion.create_version(
                db, collection=collection, filename=path.name, data=path.read_bytes(), user=admin
            )
            if created or db.get(DocumentVersion, version.id).status != VersionStatus.ready:
                ingestion.process_version(version.id)
                log(f"  ingested {cname} / {path.name}")


def run(db: Session) -> None:
    seed_identity(db)
    seed_documents(db)
    seed_tickets(db)
