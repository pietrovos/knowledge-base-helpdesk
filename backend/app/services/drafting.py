"""Cited reply drafts.

Pipeline (runs in the worker):
  1. retrieve as the requesting user (permissions applied in SQL)
  2. snapshot the retrieved chunks on the draft (these are the only citable IDs)
  3. evidence gate: if nothing relevant was retrieved, answer "insufficient evidence" without
     calling the model at all
  4. ask the model for a structured, cited reply
  5. validate citations against the snapshot; strip invalid ones; an answer left with no valid
     citation is downgraded to "insufficient evidence"
Every model call is recorded in llm_calls, success or not.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    AuthorType,
    Draft,
    DraftSource,
    DraftStatus,
    LLMCall,
    Ticket,
    TicketMessage,
    User,
)
from app.services import citations
from app.services.llm import DraftRequest, LLMError, LLMProvider, LLMResult, Source
from app.services.retrieval import retrieve

log = logging.getLogger(__name__)
TOP_K = 6


def latest_customer_message(db: Session, ticket: Ticket) -> str:
    msg = db.scalar(
        select(TicketMessage.body)
        .where(
            TicketMessage.ticket_id == ticket.id, TicketMessage.author_type == AuthorType.customer
        )
        .order_by(TicketMessage.id.desc())
        .limit(1)
    )
    return msg or ticket.subject


def create_draft(db: Session, ticket: Ticket, user: User, question: str | None = None) -> Draft:
    custom = bool((question or "").strip())
    draft = Draft(
        ticket_id=ticket.id,
        requested_by_id=user.id,
        question=question.strip() if custom else latest_customer_message(db, ticket),
        custom_question=custom,
    )
    db.add(draft)
    db.commit()
    return draft


def enqueue(draft_id: int) -> bool:
    from app.worker.tasks import generate_draft_task

    try:
        generate_draft_task.delay(draft_id)
        return True
    except Exception:
        log.exception("could not enqueue draft %s", draft_id)
        _finish(
            draft_id,
            status=DraftStatus.failed,
            error_kind="queue_unavailable",
            error="The background worker queue is unavailable. Try again shortly.",
        )
        return False


def _finish(draft_id: int, **values) -> None:
    with SessionLocal() as db:
        draft = db.get(Draft, draft_id)
        for k, v in values.items():
            setattr(draft, k, v)
        draft.completed_at = datetime.now(UTC)
        db.commit()


def record_call(
    db: Session,
    *,
    purpose: str,
    provider: str,
    model: str,
    status: str,
    latency_ms: int,
    result: LLMResult | None = None,
    error: str | None = None,
    draft_id: int | None = None,
    user_id: int | None = None,
) -> None:
    tokens_in = result.input_tokens if result else 0
    tokens_out = result.output_tokens if result else 0
    log.info(
        "llm call",
        extra={
            "event": "llm_call",
            "purpose": purpose,
            "provider": provider,
            "model": model,
            "status": status,
            "latency_ms": latency_ms,
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "cost_usd": float(result.cost) if result else 0.0,
            "draft_id": draft_id,
            "error": error,
        },
    )
    db.add(
        LLMCall(
            purpose=purpose,
            provider=provider,
            model=model,
            status=status,
            latency_ms=latency_ms,
            input_tokens=result.input_tokens if result else 0,
            output_tokens=result.output_tokens if result else 0,
            cost_usd=result.cost if result else 0,
            request_id=result.request_id if result else None,
            error=error,
            draft_id=draft_id,
            user_id=user_id,
        )
    )


def run_draft(draft_id: int, llm: LLMProvider | None = None) -> None:
    from app.services.resilience import get_resilient_llm

    llm = llm or get_resilient_llm()
    with SessionLocal() as db:
        draft = db.get(Draft, draft_id)
        if draft is None or draft.status != DraftStatus.pending:
            return  # already handled (duplicate delivery)
        user = db.get(User, draft.requested_by_id) if draft.requested_by_id else None
        if user is None or not user.is_active:
            draft.status, draft.error_kind = DraftStatus.failed, "forbidden"
            draft.error = "The requesting user no longer has access."
            draft.completed_at = datetime.now(UTC)
            db.commit()
            return
        ticket = db.get(Ticket, draft.ticket_id)
        # The ticket subject helps retrieval for the customer's own message; an agent's custom
        # question stands on its own.
        query = draft.question if draft.custom_question else f"{ticket.subject}\n{draft.question}"

        result = retrieve(db, user, query, k=TOP_K)
        draft.retrieval_ms = result.latency_ms
        draft.embedding_model = result.embedding_model
        draft.best_similarity = result.best_similarity
        for rank, c in enumerate(result.chunks, start=1):
            draft.sources.append(
                DraftSource(
                    chunk_id=c.chunk_id,
                    chunk_ref=c.chunk_id,
                    collection_id=c.collection_id,
                    document_id=c.document_id,
                    document_title=c.document_title,
                    version=c.version,
                    heading=c.heading,
                    text=c.text,
                    rank=rank,
                    similarity=c.similarity,
                    keyword_rank=c.keyword_rank,
                )
            )
        db.commit()

        if not result.has_evidence:
            draft.status = DraftStatus.insufficient_evidence
            draft.decided_by = "evidence_gate"
            draft.missing_information = (
                "None of the knowledge you can access closely matches this question."
                if result.chunks
                else "No knowledge you can access matches this question."
            )
            draft.completed_at = datetime.now(UTC)
            db.commit()
            return

        request = DraftRequest(
            customer_name=ticket.customer_name,
            subject="" if draft.custom_question else ticket.subject,
            question=draft.question,
            sources=[
                Source(s.chunk_ref, s.document_title, s.heading, s.text) for s in draft.sources
            ],
        )
        draft.provider, draft.model = llm.name, llm.model
        try:
            out = llm.draft(request)
        except LLMError as e:
            record_call(
                db,
                purpose="draft",
                provider=llm.name,
                model=llm.model,
                status=_call_status(e.kind),
                latency_ms=e.latency_ms,
                error=str(e),
                draft_id=draft.id,
                user_id=user.id,
            )
            draft.status, draft.error_kind, draft.error = DraftStatus.failed, e.kind, str(e)
            draft.generation_ms = e.latency_ms
            draft.completed_at = datetime.now(UTC)
            db.commit()
            return

        record_call(
            db,
            purpose="draft",
            provider=out.provider,
            model=out.model,
            status="ok",
            latency_ms=out.latency_ms,
            result=out,
            draft_id=draft.id,
            user_id=user.id,
        )
        draft.model = out.model
        draft.generation_ms = out.latency_ms
        draft.raw_reply = out.output.reply
        _apply_output(draft, out)
        draft.completed_at = datetime.now(UTC)
        db.commit()


def _call_status(kind: str) -> str:
    return {"timeout": "timeout", "refused": "refused", "circuit_open": "circuit_open"}.get(
        kind, "error"
    )


def _apply_output(draft: Draft, out: LLMResult) -> None:
    if out.output.status == "insufficient_evidence":
        draft.status = DraftStatus.insufficient_evidence
        draft.decided_by = "model"
        draft.missing_information = (
            out.output.missing_information or "The retrieved passages don't answer this question."
        )
        return
    allowed = {s.chunk_ref for s in draft.sources}
    check = citations.validate(out.output.reply, allowed)
    draft.invalid_citation_ids = check.invalid_ids
    if not check.cited_ids:
        # An answer we can't tie to evidence is treated as no answer.
        draft.status = DraftStatus.insufficient_evidence
        draft.decided_by = "validator"
        draft.missing_information = (
            "The generated answer did not cite any retrieved passage, so it was withheld."
        )
        return
    cited = set(check.cited_ids)
    for s in draft.sources:
        s.cited = s.chunk_ref in cited
    draft.reply = check.text
    draft.status = DraftStatus.ready
    draft.decided_by = "model"
