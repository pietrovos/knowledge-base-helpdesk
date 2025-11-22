from sqlalchemy import func, select

from app import seed
from app.db import SessionLocal
from app.models import Chunk, Document, Ticket, TicketStatus, User
from app.services import storage


def test_seed_is_idempotent_and_complete():
    storage.ensure_bucket()
    for _ in range(2):
        with SessionLocal() as db:
            seed.run(db)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(User)) == len(seed.USERS)
        assert db.scalar(select(func.count()).select_from(Ticket)) == len(seed.TICKETS)
        docs = db.scalar(select(func.count()).select_from(Document))
        assert docs == sum(len(list((seed.SEED_DIR / f).glob("*.md"))) for f in seed.FOLDERS)
        assert db.scalar(select(func.count()).select_from(Chunk).where(Chunk.is_active)) > docs
        statuses = set(db.scalars(select(Ticket.status)))
        assert {
            TicketStatus.open,
            TicketStatus.pending,
            TicketStatus.escalated,
            TicketStatus.resolved,
        } <= statuses
