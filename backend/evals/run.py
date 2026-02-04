"""Run the eval suite end to end and write a report.

    python -m evals.run                         # fake LLM, local embeddings, lexical judge (free)
    python -m evals.run --llm anthropic --judge claude   # real model (costs money)
    python -m evals.run --embedder fake --gate  # CI: fully offline, fail on regressions

The run uses its own database (<db>_eval) and bucket, rebuilt from scratch each time: identity,
seed documents (app/seed_data), then one ticket + draft per case, going through the same
retrieval → evidence gate → generation → citation validation pipeline as production.
"""

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import yaml

HERE = Path(__file__).parent


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--llm", choices=["fake", "anthropic"], default=os.environ.get("EVAL_LLM", "fake")
    )
    p.add_argument(
        "--embedder",
        choices=["local", "fake", "voyage"],
        default=os.environ.get("EVAL_EMBEDDER", "local"),
    )
    p.add_argument(
        "--judge", choices=["lexical", "claude"], default=os.environ.get("EVAL_JUDGE", "lexical")
    )
    p.add_argument("--judge-model", default="claude-opus-5-5")
    p.add_argument("--limit", type=int, default=None, help="only the first N cases")
    p.add_argument("--out", default=str(HERE / "reports"))
    p.add_argument(
        "--gate", action="store_true", help="exit non-zero if metrics fall below thresholds"
    )
    return p.parse_args(argv)


def configure_env(args) -> None:
    """Must run before any app import: settings are read once."""
    from sqlalchemy.engine import make_url

    base = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://supportlens:supportlens@localhost:5433/supportlens"
    )
    url = make_url(base)
    os.environ["DATABASE_URL"] = url.set(database=f"{url.database}_eval").render_as_string(
        hide_password=False
    )
    os.environ["S3_BUCKET"] = "supportlens-eval"
    for key, value in {
        "S3_ENDPOINT_URL": "http://localhost:9000",
        "S3_ACCESS_KEY": "supportlens",
        "S3_SECRET_KEY": "supportlens-secret",
    }.items():
        os.environ.setdefault(key, value)  # local MinIO when run outside compose
    os.environ["EMBEDDING_PROVIDER"] = args.embedder
    os.environ["LLM_PROVIDER"] = args.llm
    os.environ["FAKE_LLM_MODE"] = "ok"


def reset_database() -> None:
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from alembic import command
    from app.config import get_settings

    url = make_url(get_settings().database_url)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()
    command.upgrade(Config(str(HERE.parent / "alembic.ini")), "head")


@dataclass
class CaseResult:
    id: str
    as_user: str
    question: str
    answerable: bool
    status: str
    decided_by: str | None
    correct_decision: bool
    best_similarity: float | None
    retrieval_hit: bool | None
    cited_docs: list[str]
    citation_precision: float | None
    raw_markers: int
    invalid_citations: int
    key_facts: bool | None
    faithfulness: float | None
    permission_violations: int = 0  # retrieved passages from collections this user can't read
    unsupported_claims: list[str] = field(default_factory=list)
    retrieval_ms: int | None = None
    generation_ms: int | None = None
    reply: str = ""
    error: str | None = None


def run_case(db, case, users, judge) -> CaseResult:
    from sqlalchemy import select

    from app.models import AuthorType, Document, Draft, Ticket, TicketMessage
    from app.services import citations, drafting
    from app.services.llm import get_llm

    user = users[case.get("as_user", "alex")]
    t = Ticket(
        subject=case["question"][:120],
        customer_name="Casey Morgan",
        customer_email="casey@example.com",
    )
    db.add(t)
    db.flush()
    db.add(TicketMessage(ticket_id=t.id, author_type=AuthorType.customer, body=case["question"]))
    db.commit()
    draft = drafting.create_draft(db, t, user)
    drafting.run_draft(draft.id, llm=get_llm())
    db.expire_all()
    d = db.get(Draft, draft.id)

    filenames = (
        dict(
            db.execute(
                select(Document.id, Document.filename).where(
                    Document.id.in_({s.document_id for s in d.sources})
                )
            ).all()
        )
        if d.sources
        else {}
    )
    expected = set(case.get("expected_docs", []))
    retrieved_docs = {filenames[s.document_id] for s in d.sources}
    cited = [s for s in d.sources if s.cited]
    cited_docs = sorted({filenames[s.document_id] for s in cited})
    answered = d.status.value == "ready"
    from app.services.permissions import readable_collection_ids

    readable = set(db.scalars(readable_collection_ids(user)))
    violations = sum(s.collection_id not in readable for s in d.sources)

    precision = faith = key = None
    unsupported: list[str] = []
    if answered and cited:
        precision = (
            (sum(filenames[s.document_id] in expected for s in cited) / len(cited))
            if expected
            else None
        )
        verdict = judge.judge(d.reply, {s.chunk_ref: s.text for s in cited})
        faith, unsupported = verdict.score, verdict.unsupported_claims
        judge_cost.append(verdict)
    if answered and case.get("must_include"):
        text = d.reply.lower()
        key = all(any(alt.lower() in text for alt in group) for group in case["must_include"])

    return CaseResult(
        id=case["id"],
        as_user=case.get("as_user", "alex"),
        question=case["question"],
        answerable=case["answerable"],
        status=d.status.value,
        decided_by=d.decided_by,
        correct_decision=(
            answered if case["answerable"] else d.status.value == "insufficient_evidence"
        ),
        best_similarity=d.best_similarity,
        retrieval_hit=bool(expected & retrieved_docs) if expected else None,
        cited_docs=cited_docs,
        citation_precision=precision,
        raw_markers=len(citations.markers(d.raw_reply)),
        invalid_citations=len(d.invalid_citation_ids),
        key_facts=key,
        faithfulness=faith,
        unsupported_claims=unsupported,
        permission_violations=violations,
        retrieval_ms=d.retrieval_ms,
        generation_ms=d.generation_ms,
        reply=d.reply,
        error=d.error,
    )


judge_cost: list = []


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.fmean(xs), 3) if xs else None


def _pct(xs, p):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def summarize(results: list[CaseResult], meta: dict) -> dict:
    ans = [r for r in results if r.answerable]
    unans = [r for r in results if not r.answerable]
    answered = [r for r in ans if r.status == "ready"]
    markers = sum(r.raw_markers for r in results)
    return {
        "meta": meta,
        "cases": len(results),
        "decision_accuracy": _mean([r.correct_decision for r in results]),
        "answer_rate_on_answerable": _mean([r.status == "ready" for r in ans]),
        "correct_refusal_rate": _mean([r.status == "insufficient_evidence" for r in unans]),
        "unsupported_answers": sum(r.status == "ready" for r in unans),
        "errors": sum(r.status == "failed" for r in results),
        "permission_violations": sum(r.permission_violations for r in results),
        "retrieval_recall_at_k": _mean(
            [r.retrieval_hit for r in ans if r.retrieval_hit is not None]
        ),
        "citation_precision": _mean([r.citation_precision for r in answered]),
        "citation_validity": round(1 - sum(r.invalid_citations for r in results) / markers, 3)
        if markers
        else None,
        "faithfulness": _mean([r.faithfulness for r in answered]),
        "key_fact_accuracy": _mean([r.key_facts for r in answered if r.key_facts is not None]),
        "key_fact_accuracy_all_answerable": _mean(
            [bool(r.key_facts) for r in ans if "must_include" in meta["case_keys"].get(r.id, ())]
        ),
        "latency_ms": {
            "retrieval_p50": _pct([r.retrieval_ms for r in results], 50),
            "retrieval_p95": _pct([r.retrieval_ms for r in results], 95),
            "generation_p50": _pct([r.generation_ms for r in results], 50),
            "generation_p95": _pct([r.generation_ms for r in results], 95),
        },
        "similarity": {
            "threshold": meta["min_similarity"],
            "answerable": [r.best_similarity for r in ans],
            "unanswerable": [r.best_similarity for r in unans],
        },
    }


THRESHOLDS = {  # --gate: CI regression check. Calibrated on the offline (fake/fake) baseline.
    "decision_accuracy": 0.65,
    "retrieval_recall_at_k": 0.6,
    "citation_validity": 1.0,
    "faithfulness": 0.9,
}


def fmt(x, pct=True):
    if x is None:
        return "n/a"
    return f"{x * 100:.0f}%" if pct else str(x)


def write_report(summary: dict, results: list[CaseResult], out: Path) -> Path:
    m = summary["meta"]
    lat = summary["latency_ms"]
    sim = summary["similarity"]

    def rng(xs):
        xs = sorted(x for x in xs if x is not None)
        return f"{xs[0]:.2f} / {statistics.median(xs):.2f} / {xs[-1]:.2f}" if xs else "n/a"

    lines = [
        "# SupportLens eval report",
        "",
        f"Run {m['started']} · {summary['cases']} cases · LLM `{m['llm']}` · embeddings `{m['embedding_model']}` · judge `{m['judge']}`",
        "",
        "| Metric | Value | What it measures |",
        "| --- | --- | --- |",
        f"| Decision accuracy | {fmt(summary['decision_accuracy'])} | Answered when the user's knowledge supports it, refused otherwise |",
        f"| Answer rate (answerable) | {fmt(summary['answer_rate_on_answerable'])} | Answerable questions that got a cited draft |",
        f'| Correct refusal rate (unanswerable) | {fmt(summary["correct_refusal_rate"])} | Unsupported or out-of-permission questions answered with "insufficient evidence" |',
        f"| Unsupported answers | {summary['unsupported_answers']} | Drafts produced for questions that should have been refused |",
        f"| Retrieval recall@6 | {fmt(summary['retrieval_recall_at_k'])} | An expected document was among the retrieved passages |",
        f"| Citation precision | {fmt(summary['citation_precision'])} | Cited passages that come from an expected document |",
        f"| Citation validity | {fmt(summary['citation_validity'])} | Model citation markers that pointed at a retrieved passage (before the validator) |",
        f"| Faithfulness | {fmt(summary['faithfulness'])} | Claims in answers supported by the passages they cite ({m['judge']} judge) |",
        f'| Key-fact accuracy | {fmt(summary["key_fact_accuracy"])} | Answers containing the expected fact (e.g. "30 days") |',
        f"| Permission violations | {summary['permission_violations']} | Retrieved passages from collections the asking user can't read (must be 0) |",
        f"| Errors | {summary['errors']} | Provider failures |",
        "",
        f"Latency: retrieval p50 {lat['retrieval_p50']} ms / p95 {lat['retrieval_p95']} ms · generation p50 {lat['generation_p50']} ms / p95 {lat['generation_p95']} ms · "
        f"model cost ${m['cost_usd']} ({m['input_tokens']} in / {m['output_tokens']} out tokens) · judge cost ${m['judge_cost_usd']}",
        "",
        f"Evidence gate calibration (best retrieval similarity, min / median / max): answerable {rng(sim['answerable'])} · "
        f"unanswerable {rng(sim['unanswerable'])} · threshold {sim['threshold']}",
        "",
        "## Cases",
        "",
        "| Case | User | Expected | Outcome | Decided by | Cited | Key fact | Faithful |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        mark = "✅" if r.correct_decision else "❌"
        lines.append(
            f"| `{r.id}` | {r.as_user} | {'answer' if r.answerable else 'refuse'} | {mark} {r.status} | {r.decided_by or ''} | "
            f"{', '.join(r.cited_docs) or '—'} | {'' if r.key_facts is None else ('yes' if r.key_facts else 'no')} | "
            f"{'' if r.faithfulness is None else fmt(r.faithfulness)} |"
        )
    misses = [
        r
        for r in results
        if not r.correct_decision or r.key_facts is False or (r.faithfulness or 1) < 1
    ]
    if misses:
        lines += ["", "## Misses", ""]
        for r in misses:
            lines.append(f"### `{r.id}`: {r.question}")
            lines.append(
                f"Outcome `{r.status}` (decided by {r.decided_by}), best similarity {r.best_similarity}."
            )
            if r.reply:
                lines.append("")
                lines += ["> " + line for line in r.reply.splitlines()]
            for c in r.unsupported_claims:
                lines.append(f"- Unsupported: {c}")
            if r.error:
                lines.append(f"- Error: {r.error}")
            lines.append("")
    out.mkdir(parents=True, exist_ok=True)
    path = out / "latest.md"
    path.write_text("\n".join(lines) + "\n")
    (out / "latest.json").write_text(
        json.dumps(
            {"summary": summary, "results": [asdict(r) for r in results]}, indent=2, default=str
        )
    )
    return path


def main(argv=None) -> int:
    args = parse_args(argv)
    configure_env(args)

    from sqlalchemy import func, select

    from app import seed
    from app.db import SessionLocal
    from app.models import LLMCall, User
    from app.services.embeddings import get_embedder

    started = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    print(f"Resetting eval database and seeding knowledge ({args.embedder} embeddings)…")
    reset_database()
    with SessionLocal() as db:
        seed.seed_identity(db)
        seed.seed_documents(db, log=lambda m: None)

    judge = __import__("evals.judges", fromlist=["x"])
    judge = judge.ClaudeJudge(args.judge_model) if args.judge == "claude" else judge.LexicalJudge()
    cases = yaml.safe_load((HERE / "dataset.yaml").read_text())["cases"][: args.limit]
    results: list[CaseResult] = []
    t0 = time.perf_counter()
    with SessionLocal() as db:
        users = {
            "alex": db.scalar(select(User).where(User.email == "alex@supportlens.dev")),
            "sam": db.scalar(select(User).where(User.email == "sam@supportlens.dev")),
            "admin": db.scalar(select(User).where(User.email == "admin@supportlens.dev")),
        }
        for i, case in enumerate(cases, 1):
            r = run_case(db, case, users, judge)
            results.append(r)
            print(
                f"[{i:>2}/{len(cases)}] {'ok ' if r.correct_decision else 'MISS'} {r.id:<26} {r.status}"
            )
        usage = db.execute(
            select(
                func.coalesce(func.sum(LLMCall.cost_usd), 0),
                func.coalesce(func.sum(LLMCall.input_tokens), 0),
                func.coalesce(func.sum(LLMCall.output_tokens), 0),
            )
        ).one()

    from app.services.llm import cost_usd

    judge_usd = sum(
        (cost_usd(args.judge_model, v.input_tokens, v.output_tokens) for v in judge_cost),
        Decimal(0),
    )
    embedder = get_embedder()
    meta = {
        "started": started,
        "llm": "fake-extractive-1"
        if args.llm == "fake"
        else os.environ.get("LLM_MODEL", "claude-opus-5-5"),
        "embedding_model": embedder.name,
        "min_similarity": embedder.min_similarity,
        "judge": args.judge if args.judge == "lexical" else f"claude ({args.judge_model})",
        "cost_usd": f"{Decimal(usage[0]):.4f}",
        "input_tokens": int(usage[1]),
        "output_tokens": int(usage[2]),
        "judge_cost_usd": f"{judge_usd:.4f}",
        "wall_seconds": round(time.perf_counter() - t0, 1),
        "case_keys": {c["id"]: tuple(c.keys()) for c in cases},
    }
    summary = summarize(results, meta)
    path = write_report(summary, results, Path(args.out))
    print(
        f"\nDecision accuracy {fmt(summary['decision_accuracy'])} · citation precision {fmt(summary['citation_precision'])} · "
        f"faithfulness {fmt(summary['faithfulness'])} · correct refusals {fmt(summary['correct_refusal_rate'])}"
    )
    print(f"Report: {path}")

    if args.gate:
        failed = [
            f"{k} {summary[k]} < {v}"
            for k, v in THRESHOLDS.items()
            if summary[k] is not None and summary[k] < v
        ]
        if failed:
            print("Eval gate FAILED: " + "; ".join(failed), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
