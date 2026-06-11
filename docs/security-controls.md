# Security Controls — Phase 3 Additions

This document supplements `security-model.md` with Phase 3-specific security additions.

---

## Prompt Injection Detection

Every RAG query (both `/query` and `/query-stream`) passes through `PromptSecurityService.check()` before any retrieval or LLM call occurs.

### Detection layers

| Layer | Mechanism | Examples |
|---|---|---|
| Keyword | Substring match (case-insensitive) | "ignore previous instructions", "jailbreak", "act as" |
| Pattern | Regex | ` ```system `, `<system>`, `[INST].*override` |
| Heuristic | Statistical anomaly | Input >2000 chars with <10 spaces |

### On detection

1. Query is **blocked** — retrieval and LLM call are skipped
2. Event logged to `prompt_security_events` table (input_text capped at 1000 chars, pattern matched recorded)
3. User receives: `"Your query was flagged by the security filter. Please rephrase."`
4. Response is identical for all detection types — no signal leakage about which rule fired

### Known gaps

- No ML-based injection classifier (Phase 4 candidate)
- Short, cleverly-worded injections may bypass keyword/pattern detection
- The system prompt still instructs the LLM to answer only from context — defense in depth

---

## Chat Session Isolation

Chat sessions are scoped to `(tenant_id, user_id)` — the API enforces both filters on every read and write operation. A user cannot read another user's sessions even within the same tenant.

---

## Langfuse Data Handling

When Langfuse observability is enabled:

- **Inputs sent to Langfuse**: question text (first 500 chars of answer), chunk counts, latency, allowed_classifications
- **Not sent**: full document content, PII findings, JWT tokens, passwords
- Langfuse is self-hosted (Docker Compose profile) — no data leaves your infrastructure by default
- If `LANGFUSE_SECRET_KEY` is empty, all observability calls are no-ops and nothing is transmitted

---

## New Audit Events (Phase 3)

No new audit event types are added in Phase 3. The existing `rag.query` event is enriched with `hybrid` and `reranked` boolean flags in `metadata_json`.

Prompt injection blocks are recorded in `prompt_security_events` (separate table) rather than `audit_events` to keep the audit log focused on authorization decisions.

---

## Residual Risks Added in Phase 3

| Risk | Severity | Mitigation |
|---|---|---|
| Chat history leakage | Low | Sessions scoped to tenant+user; cascade delete on session removal |
| Streaming response interception | Medium | Requires HTTPS termination at reverse proxy (not AegisRAG's responsibility in dev) |
| Langfuse misconfiguration | Medium | If `LANGFUSE_HOST` points to a remote endpoint, query text is transmitted; document clearly |
| Keyword injection bypass | Medium | Layered with system prompt instruction; ML classifier planned for Phase 4 |
