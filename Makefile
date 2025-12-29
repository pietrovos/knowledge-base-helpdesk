.PHONY: reset up down logs test test-backend test-frontend lint migrate seed eval e2e check

up:            ## start the full local stack
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api worker

test: test-backend test-frontend

test-backend:  ## unit + integration tests (needs `docker compose up -d db redis minio`)
	cd backend && uv run pytest

test-frontend:
	cd frontend && npm test && npm run typecheck

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint

reset:         ## wipe the local database and reload the demo data
	docker compose exec -T db psql -U supportlens -d postgres -c 'DROP DATABASE IF EXISTS supportlens WITH (FORCE)' -c 'CREATE DATABASE supportlens'
	docker compose exec -T redis redis-cli FLUSHDB
	docker compose restart api worker
	until curl -sf localhost:8000/api/health >/dev/null; do sleep 1; done
	docker compose exec -T api python -m app.cli seed

eval:          ## run the AI eval suite (free by default; ARGS="--llm anthropic --judge claude" for the real model)
	docker compose exec api python -m evals.run $(ARGS)

e2e:           ## Playwright demo flow against the running stack (resets demo data first)
	cd frontend && npx playwright test

migrate:
	docker compose exec api alembic upgrade head

seed:          ## load demo users, collections, documents and tickets
	docker compose exec api python -m app.cli seed

check:         ## everything CI runs: lint, typecheck, unit + integration tests
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest
	cd frontend && npm run lint && npm run typecheck && npm test
