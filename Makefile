.PHONY: up down logs test test-backend test-frontend lint migrate seed eval e2e

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

migrate:
	docker compose exec api alembic upgrade head

seed:          ## load demo users, collections, documents and tickets
	docker compose exec api python -m app.cli seed
