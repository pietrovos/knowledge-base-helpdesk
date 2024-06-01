# SupportLens design notes

SupportLens is a helpdesk where agents answer tickets with replies drafted from company
knowledge they are allowed to read, and where every claim in a draft links back to the passage
behind it. The model is one replaceable part of the system; most of the code is the surrounding
work: permissions, ingestion, citations, failure handling and evals.

## Scope

- A local stack (Postgres with pgvector, Redis, MinIO, API, worker, web), an Alembic baseline,
  and CI that runs the test suites with fake providers and no network.
- Users, roles (agent, admin), groups, and collections with read permissions.
- Ingestion for Markdown and text: upload to S3, a Celery job that chunks and embeds, live
  status and progress in the UI, retries with backoff, idempotent re-processing, and document
  versioning.
- A ticket inbox with a detail view, statuses and assignment.
- Retrieval that applies the permission filter inside the vector query, with tests showing
  restricted text never reaches a prompt.
- Cited drafts: grounded generation, validation of every citation against the retrieved set, an
  evidence viewer, and an "insufficient evidence" path that can open a knowledge-gap task.
- Review and publishing, an escalation queue and a knowledge-gap queue.
- Resilience: timeouts, a circuit breaker and a degraded UI, exercised with fake-provider
  failures.
- Observability and evals: per-call latency, tokens and cost, a dashboard, and an eval suite
  run with `make eval`.
- Production Dockerfiles, AWS deployment config and the README.

## Architecture

```
web (React/Vite) ──HTTP /api──▶ api (FastAPI) ──▶ Postgres + pgvector
                                     │  ├──▶ MinIO / S3 (private bucket, presigned GETs)
                                     │  └──▶ Redis (Celery broker, circuit-breaker state)
                                     ▼
                               worker (Celery): ingestion pipeline, draft generation
                                     ├──▶ Embedder  (local fastembed | Voyage | Fake)
                                     └──▶ LLM       (Anthropic Claude | Fake)
```

### Repository layout

- `backend/`: FastAPI app (`app/`), Alembic (`alembic/`), tests (`tests/unit`,
  `tests/integration`), evals (`evals/`). Managed with uv.
- `frontend/`: Vite, React and TypeScript with Tailwind, TanStack Query and React Router;
  Vitest unit tests; Playwright e2e in `frontend/e2e`.
- `infra/`: production Dockerfiles and AWS deployment config.
- `docker-compose.yml`: local dev stack. `Makefile`: common commands.

### Key design decisions

- Providers sit behind interfaces. `Embedder` (local fastembed by default, Voyage, Fake) and
  `LLMProvider` (Anthropic, Fake) are selected by env vars; tests and CI always use Fake, with
  no network.
- The embeddings table is keyed by model. `chunk_embeddings(chunk_id, model, embedding vector)`
  has a per-model partial HNSW index on `embedding::vector(dim)`. Switching embedding models
  means re-embedding into new rows; vector spaces never mix.
- Permissions live in SQL. Retrieval is a single query: chunk joined to active version,
  non-deleted document and readable collection (direct grant or via group), ordered by cosine
  distance. Nothing unauthorized is loaded into Python, so it can't reach a prompt.
- Versioning runs through `documents` → `document_versions` → `chunks`. A new upload creates a
  new version; when processing finishes, its chunks are activated and the older version's chunks
  retired in one transaction. Re-processing a version is idempotent because chunks are keyed by
  `(version_id, ordinal)`.
- Citations come from structured output, with inline markers that name chunk IDs. Every cited ID
  is checked against the set retrieved for that request; unknown IDs are stripped and recorded
  as flagged. "Insufficient evidence" is a first-class response status.
- Draft generation runs in Celery and the UI polls the draft row, so tickets never depend on the
  LLM being up.
- Resilience uses hard timeouts on provider calls, a Redis-backed circuit breaker shared by all
  processes, and an `/api/system/status` endpoint that exposes degraded state to the UI.
- Observability writes an `llm_calls` row (latency, tokens, cost, status) for every LLM and
  embedding call; the dashboard aggregates it.
- Auth uses Argon2 password hashes and a JWT in an httpOnly SameSite cookie. Roles are `agent`
  and `admin`.

### Local ports

Postgres 5433 (host), Redis 6379, MinIO 9000 and console 9001, API 8000, web 5173.

## Notes

- Python 3.12 is pinned in `mise.toml`; backend deps use `uv` (`cd backend && uv sync`).
- Integration tests need Postgres: `docker compose up -d db` then `make test-backend`.
- Official MinIO images are no longer published, so compose uses `cgr.dev/chainguard/minio`. It
  has no shell, so there is no container healthcheck; the API retries bucket creation at
  startup.
- The host Postgres port is 5433 (5432 is often taken). Integration tests use the database
  `supportlens_test` (created automatically) and Redis db 15.
- Run `make check` before every commit (lint, format, typecheck and all tests); it stops on the
  first failure.
- Chunk IDs are stable across re-processing (upsert on `(version_id, ordinal)`), so draft
  citations keep resolving.
- Draft sources are snapshotted in `draft_sources`, and citation validity is checked against
  that snapshot alone. A viewer who lacks access to a source's collection gets it redacted, and
  the evidence endpoint returns 403.
- The LLM is `claude-opus-5-5`, called through `client.beta.messages.parse` with structured
  output, `output_config.effort` (default medium) and server-side `fallbacks="default"` (beta
  `server-side-fallback-2026-07-01`). SDK retries are disabled (`max_retries=0`); the resilience
  layer owns retries.
- Resilience lives in `app/services/resilience.py`. Breaker state is stored in Redis keys
  `cb:llm:*`, and the outage drill switch is `chaos:llm` (Admin → System page, or
  `PUT /api/system/chaos`). Worker liveness is a Redis heartbeat at `worker:heartbeat` with a
  30s TTL.
- Evals run with `make eval` (in the api container, local embeddings and FakeLLM, free). They
  use their own database `<db>_eval` and bucket `supportlens-eval`, rebuilt on every run. For the
  real model, `make eval ARGS="--llm anthropic --judge claude"` costs money, needs
  `ANTHROPIC_API_KEY`, and is worth asking about before running. CI runs the fully offline config
  with `--gate`.
- The local embedder threshold `min_similarity=0.65` was calibrated from the eval report
  (answerable at least 0.66, unanswerable median 0.62).
- Logs are JSON lines (`app/logging_setup.py`): an `http_request` line per request (route,
  status, latency, user, request id) and an `llm_call` line per model call (tokens, cost,
  latency).
- Demo data comes from `make seed` (idempotent) or `make reset` (wipe and reseed). Seed docs live
  in `backend/app/seed_data/<collection-folder>/*.md`.
- E2E runs with `make e2e` (Playwright, resets demo data via `make reset` in global setup; set
  `E2E_SKIP_RESET=1` to skip). CI runs it on the compose stack with fake embeddings.
- Delivery is `backend/Dockerfile.prod`, `frontend/Dockerfile`, `docker-compose.prod.yml` (the
  e2e flow passes against it), the `infra/aws` Terraform (validated, never applied) and a manual
  `.github/workflows/deploy.yml`. Screenshots: `make reset && node
  frontend/scripts/capture-screenshots.mjs`.
