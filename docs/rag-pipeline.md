# RAG Pipeline — Phase 3

## Overview

Phase 3 introduces hybrid retrieval, cross-encoder reranking, SSE streaming, and Langfuse observability to the RAG pipeline.

---

## Retrieval Modes

### Vector-only (default when `HYBRID_RETRIEVAL_ENABLED=false`)

1. Embed query with `sentence-transformers/all-MiniLM-L6-v2`
2. Qdrant cosine similarity search with mandatory dual filter: `tenant_id` + `classification`
3. Return top-K scored points

### Hybrid (default, `HYBRID_RETRIEVAL_ENABLED=true`)

Combines two independent signals using Reciprocal Rank Fusion (RRF):

| Signal | Source | Score |
|---|---|---|
| Semantic | Qdrant cosine similarity | RRF rank-weighted |
| Keyword | PostgreSQL FTS (`plainto_tsquery`) | RRF rank-weighted |

**RRF formula**: `score(d) = Σ 1 / (k + rank(d))` where `k=60`

Both signals fetch `top_k × BM25_TOP_K_MULTIPLIER` candidates before merging, then the merged list is truncated to `top_k`.

PostgreSQL FTS uses the `english` dictionary and indexes `document_chunks.content`. The join to `documents` ensures both `tenant_id` and `classification` filters are applied at the SQL layer — the same security guarantees as vector search.

---

## Reranking (optional, `RERANKING_ENABLED=true`)

After retrieval (vector-only or hybrid), a cross-encoder model (`cross-encoder/ms-marco-MiniLM-L-6-v2`) scores each `(query, chunk)` pair and re-orders the candidate list.

Cross-encoder reranking is CPU-heavy and disabled by default. Enable only on hardware where latency budget allows.

---

## Prompt Injection Check

Before retrieval, every query is scanned by `PromptSecurityService.check()`:

1. **Keyword scan**: checks for known injection phrases ("ignore previous instructions", "jailbreak", etc.)
2. **Pattern scan**: regex patterns for structured injection (`<system>`, `[INST]`, code blocks)
3. **Heuristic**: long input with almost no spaces (potential base64 or obfuscated payload)

If flagged: the event is logged to `prompt_security_events`, the query is blocked, and a sanitized error response is returned. The LLM is never called.

---

## Streaming

`POST /api/v1/rag/query-stream` returns a Server-Sent Events stream. Each line is:

```
data: <json>\n\n
```

Event types:

| type | Content |
|---|---|
| `sources` | `{ "type": "sources", "sources": [...] }` — emitted before any tokens |
| `token` | `{ "type": "token", "content": "word" }` — one token at a time |
| `done` | `{ "type": "done" }` — stream complete |
| `error` | `{ "type": "error", "content": "..." }` — security block or server error |

The Ollama `/api/generate` endpoint is called with `stream: true`, and tokens are forwarded directly.

---

## Langfuse Observability

When `LANGFUSE_SECRET_KEY` and `LANGFUSE_PUBLIC_KEY` are set, every `RAGService.query()` call creates a Langfuse trace with:

- `retrieval` span: input=question, output=chunk count
- `generation` span: input=question, output=first 500 chars of answer
- Trace metadata: latency_ms, allowed_classifications, model name

If Langfuse is not configured (empty keys), all observability calls are silent no-ops — the pipeline runs identically.

---

## Debug Endpoint

`GET /api/v1/rag/debug-query?question=...&top_k=5`

Available to `tenant_admin` and `compliance_officer` only. Returns:

```json
{
  "question": "...",
  "allowed_classifications": ["public", "internal", "confidential"],
  "vector_results": [...],
  "fts_results": [...],
  "hybrid_merged": [{ "chunk_id": "...", "rrf_score": 0.03, "vector_score": 0.82 }],
  "reranking_enabled": false,
  "hybrid_enabled": true,
  "latency_ms": 124
}
```

---

## Configuration Reference

| Variable | Default | Effect |
|---|---|---|
| `HYBRID_RETRIEVAL_ENABLED` | `true` | Enable vector+FTS+RRF |
| `RERANKING_ENABLED` | `false` | Enable cross-encoder reranking |
| `RERANKING_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder model name |
| `BM25_TOP_K_MULTIPLIER` | `3` | Multiplier for FTS/vector candidate pool |
| `LANGFUSE_SECRET_KEY` | `""` | Langfuse server key (blank = disabled) |
| `LANGFUSE_PUBLIC_KEY` | `""` | Langfuse public key |
| `LANGFUSE_HOST` | `http://localhost:3000` | Langfuse server URL |
