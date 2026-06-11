# Phase 1 Scope

## What is included in Phase 1

- User registration and JWT-based authentication (Argon2 password hashing)
- Tenant creation and assignment
- PDF upload endpoint with SHA-256 checksum verification
- Async document processing pipeline (Celery + Redis)
  - PDF text extraction (pypdf)
  - Word-based chunking with overlap
  - Embedding generation (sentence-transformers/all-MiniLM-L6-v2)
  - Vector storage in Qdrant with tenant-scoped payloads
- RAG query endpoint
  - Question embedding
  - Tenant-filtered Qdrant search
  - Answer generation via Ollama (local LLM)
  - Cited sources in response
- Immutable audit log (JSONB metadata) for all key events
- Full Docker Compose stack (postgres, redis, qdrant, ollama, backend, backend-worker)
- Alembic migrations
- Basic pytest suite (health, security functions)
- Structured logging (structlog)

## Intentionally Excluded from Phase 1

- Frontend / dashboard UI
- Full role-based access control (RBAC) — Phase 1 has a single user role per tenant
- Langfuse observability integration
- RAGAS evaluation pipeline
- Document classification or metadata enrichment
- Support for file types other than PDF
- vLLM or other GPU-accelerated inference backends
- Kubernetes / Helm deployment
- Rate limiting and API throttling
- Email verification
- Password reset flow
- Document deletion and re-indexing
- Streaming LLM responses

## Planned Phase 2 Items

| Feature | Description |
|---|---|
| Full RBAC | Owner / Admin / Member / Viewer roles per tenant |
| Document classification | Auto-tag documents on ingest |
| Langfuse | LLM observability, trace every RAG call |
| RAGAS evaluation | Automated RAG quality metrics |
| Frontend dashboard | React or Next.js UI for document management and chat |
| vLLM support | GPU-optimized inference backend option |
| Kubernetes | Helm chart for production deployment |
| Streaming answers | Server-Sent Events for token-by-token LLM output |
| Multi-file upload | Batch upload endpoint |
| Document versioning | Re-upload replaces old vector chunks cleanly |
