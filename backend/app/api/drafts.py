from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DB, CurrentUser
from app.api.tickets import get_ticket_or_404
from app.models import (
    Chunk,
    Collection,
    Document,
    Draft,
    DraftStatus,
    KnowledgeGap,
    Ticket,
    TicketStatus,
    User,
)
from app.schemas.drafts import DraftCreate, DraftOut, DraftSourceOut, EvidenceOut, PublishIn
from app.schemas.identity import UserRef
from app.services import citations, drafting
from app.services import tickets as ticket_svc
from app.services.permissions import readable_collection_ids

router = APIRouter(prefix="/api", tags=["drafts"])


def _visibility(db: Session, viewer: User, drafts: list[Draft]) -> tuple[set[int], set[int]]:
    """Collections the viewer can read now, and which cited chunks are still live."""
    readable = set(db.scalars(readable_collection_ids(viewer)))
    refs = {s.chunk_ref for d in drafts for s in d.sources}
    live = (
        set(
            db.scalars(
                select(Chunk.id)
                .join(Document, Document.id == Chunk.document_id)
                .where(Chunk.id.in_(refs), Chunk.is_active, Document.deleted_at.is_(None))
            )
        )
        if refs
        else set()
    )
    return readable, live


def _source_out(s, readable: set[int], live: set[int]) -> DraftSourceOut:
    accessible = s.collection_id in readable
    return DraftSourceOut(
        chunk_id=s.chunk_ref,
        document_id=s.document_id,
        document_title=s.document_title,
        version=s.version,
        heading=s.heading,
        text=s.text if accessible else None,
        rank=s.rank,
        similarity=s.similarity,
        keyword_rank=s.keyword_rank,
        cited=s.cited,
        accessible=accessible,
        live=s.chunk_ref in live,
    )


def draft_out(db: Session, viewer: User, draft: Draft, vis=None) -> DraftOut:
    readable, live = vis or _visibility(db, viewer, [draft])
    gap_id = db.scalar(select(KnowledgeGap.id).where(KnowledgeGap.draft_id == draft.id).limit(1))
    return DraftOut(
        **{
            f: getattr(draft, f)
            for f in DraftOut.model_fields
            if f not in ("sources", "requested_by", "knowledge_gap_id")
        },
        requested_by=UserRef.model_validate(draft.requested_by) if draft.requested_by else None,
        sources=[_source_out(s, readable, live) for s in draft.sources],
        knowledge_gap_id=gap_id,
    )


def get_draft_or_404(db: Session, draft_id: int) -> Draft:
    draft = db.get(Draft, draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")
    return draft


@router.post("/tickets/{ticket_id}/drafts", response_model=DraftOut, status_code=202)
def request_draft(ticket_id: int, body: DraftCreate, db: DB, user: CurrentUser) -> DraftOut:
    ticket = get_ticket_or_404(db, ticket_id)
    draft = drafting.create_draft(db, ticket, user, body.question)
    drafting.enqueue(draft.id)
    db.expire_all()
    return draft_out(db, user, db.get(Draft, draft.id))


@router.get("/tickets/{ticket_id}/drafts", response_model=list[DraftOut])
def list_drafts(ticket_id: int, db: DB, user: CurrentUser) -> list[DraftOut]:
    get_ticket_or_404(db, ticket_id)
    drafts = list(
        db.scalars(
            select(Draft).where(Draft.ticket_id == ticket_id).order_by(Draft.id.desc()).limit(10)
        )
    )
    vis = _visibility(db, user, drafts)
    return [draft_out(db, user, d, vis) for d in drafts]


@router.get("/drafts/{draft_id}", response_model=DraftOut)
def get_draft(draft_id: int, db: DB, user: CurrentUser) -> DraftOut:
    return draft_out(db, user, get_draft_or_404(db, draft_id))


@router.post("/drafts/{draft_id}/discard", response_model=DraftOut)
def discard_draft(draft_id: int, db: DB, user: CurrentUser) -> DraftOut:
    draft = get_draft_or_404(db, draft_id)
    if draft.status == DraftStatus.published:
        raise HTTPException(409, "Published drafts can't be discarded")
    draft.status = DraftStatus.discarded
    db.commit()
    return draft_out(db, user, draft)


@router.post("/drafts/{draft_id}/publish", response_model=DraftOut)
def publish_draft(draft_id: int, body: PublishIn, db: DB, user: CurrentUser) -> DraftOut:
    """The agent's (possibly edited) text goes to the customer; citation markers are internal
    and are stripped. The draft keeps its sources and citations as the audit trail."""
    draft = db.scalar(select(Draft).where(Draft.id == draft_id).with_for_update())
    if draft is None:
        raise HTTPException(404, "Draft not found")
    if draft.status != DraftStatus.ready:
        raise HTTPException(409, f"Only ready drafts can be published (this one is {draft.status})")
    text = citations.strip_markers(body.text)
    if not text:
        raise HTTPException(422, "The reply is empty")
    ticket = db.get(Ticket, draft.ticket_id)
    msg = ticket_svc.add_agent_message(db, ticket, user, text, draft_id=draft.id)
    db.flush()
    draft.status = DraftStatus.published
    draft.published_text = text
    draft.published_message_id = msg.id
    draft.was_edited = text != citations.strip_markers(draft.reply)
    ticket_svc.record(
        db,
        ticket,
        user,
        "draft_published",
        draft_id=draft.id,
        edited=draft.was_edited,
        citations=[s.chunk_ref for s in draft.sources if s.cited],
    )
    if body.ticket_status:
        ticket_svc.set_status(db, ticket, user, TicketStatus(body.ticket_status))
    ticket.updated_at = func.now()
    db.commit()
    return draft_out(db, user, draft)


@router.get("/drafts/{draft_id}/evidence/{chunk_id}", response_model=EvidenceOut)
def evidence(draft_id: int, chunk_id: int, db: DB, user: CurrentUser) -> EvidenceOut:
    """The exact passage the model saw for this draft, plus its neighbours for context.
    Access is re-checked on every request: revoked access hides the passage."""
    draft = get_draft_or_404(db, draft_id)
    source = next((s for s in draft.sources if s.chunk_ref == chunk_id), None)
    if source is None:
        raise HTTPException(404, "That passage was not retrieved for this draft")
    readable, live = _visibility(db, user, [draft])
    if source.collection_id not in readable:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You no longer have access to this source")
    before = after = None
    chunk = db.get(Chunk, chunk_id)
    if chunk is not None:
        neighbours = {
            c.ordinal: c.text
            for c in db.scalars(
                select(Chunk).where(
                    Chunk.version_id == chunk.version_id,
                    Chunk.ordinal.in_([chunk.ordinal - 1, chunk.ordinal + 1]),
                )
            )
        }
        before, after = neighbours.get(chunk.ordinal - 1), neighbours.get(chunk.ordinal + 1)
    collection = db.get(Collection, source.collection_id)
    return EvidenceOut(
        source=_source_out(source, readable, live),
        context_before=before,
        context_after=after,
        collection_name=collection.name if collection else "",
    )
