# AegisRAG Backend

FastAPI backend for the AegisRAG secure enterprise RAG platform.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Running Docker Compose stack (postgres, redis, qdrant, ollama)

## Setup

```bash
# Copy and edit environment file
cp .env.example .env

# Install dependencies
uv sync

# Run database migrations
uv run alembic upgrade head
```

## Run locally (outside Docker)

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Run Celery worker locally

```bash
uv run celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

## Run tests

```bash
uv run pytest
```

## Lint and format

```bash
# Check
uv run ruff check app/

# Fix
uv run ruff check --fix app/

# Format
uv run ruff format app/
```

## Generate a new Alembic migration

After changing SQLAlchemy models:

```bash
uv run alembic revision --autogenerate -m "describe your change"
uv run alembic upgrade head
```

## API docs

Interactive docs available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project layout

```
app/
  main.py              FastAPI app entry point
  core/                Config, security, logging
  db/                  SQLAlchemy engine and session
  models/              ORM models (SQLAlchemy 2.0)
  schemas/             Pydantic request/response models
  services/            Business logic (auth, RAG, PDF, etc.)
  api/
    deps.py            FastAPI dependencies (auth, tenant guard)
    routes/            One router per domain
  workers/
    celery_app.py      Celery app instance
    tasks.py           process_document task
  tests/               pytest suite
alembic/               Migrations
```
