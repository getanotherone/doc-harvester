.PHONY: up down build restart migrate test test-fast shell shell-db health logs

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

restart:
	docker compose restart backend

migrate:
	docker compose exec backend alembic upgrade head

test:
	docker compose exec backend python -m pytest tests/ -v

test-fast:
	docker compose exec backend python -m pytest tests/ -v -x --tb=short

shell:
	docker compose exec backend bash

shell-db:
	docker compose exec postgres psql -U doc_proc -d doc_proc

health:
	curl -s localhost:8000/health | python3 -m json.tool

logs:
	docker compose logs -f backend
