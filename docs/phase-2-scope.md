# Phase 2 Scope

## What is Included in Phase 2

### RBAC
- Four roles: `tenant_admin`, `compliance_officer`, `analyst`, `viewer`
- `role` field on the User model
- Permission helper functions in `app/core/permissions.py`
- FastAPI dependency factories (`require_tenant_admin`, `require_upload_permission`, etc.)
- Tenant creator automatically becomes `tenant_admin`

### Document Classification
- Four levels: `public`, `internal`, `confidential`, `restricted`
- `classification` field on the Document model (default: `internal`)
- Upload endpoint accepts `classification` as a form field
- Document list and detail endpoints filter by user's allowed classifications
- `PATCH /api/v1/documents/{id}/classification` — admin/compliance_officer only

### Access-Controlled Retrieval
- `qdrant_service.search()` now requires `allowed_classifications` parameter
- Qdrant point payload includes `classification` and `uploaded_by_id`
- Every RAG query enforces both tenant and classification filters at the vector layer
- Existing documents indexed without `classification` in payload must be reindexed

### User Invitation Flow
- `POST /api/v1/users/invite` — admin creates invitation, raw token returned in response
- `POST /api/v1/users/accept-invite` — user accepts with token + password
- `TenantInvitation` model with status tracking (pending/accepted/revoked/expired)
- 72-hour token expiry; token stored as SHA-256 hash only

### User Management
- `GET /api/v1/users` — list tenant users (admin/compliance officer)
- `PATCH /api/v1/users/{id}/role` — update role (admin only)
- `DELETE /api/v1/users/{id}` — deactivate user (admin only; cannot self-deactivate)

### Stronger Audit Logging
- `ip_address` and `user_agent` fields on `AuditEvent`
- New event types: `auth.login_success`, `auth.login_failed`, `tenant.created`, `user.invited`, `user.invite_accepted`, `user.role_updated`, `user.deactivated`, `document.deleted`, `document.classification_updated`, `document.reindex_requested`, `pii.detected`
- Audit endpoint supports filters: `event_type`, `entity_type`, `user_id`, `limit`, `offset`
- Audit access restricted to `tenant_admin` and `compliance_officer`

### PII Detection
- Regex-based detection for: email, phone, SSN, credit card, IBAN
- Runs on each chunk during document indexing
- `PiiFinding` model: stores hash + masked preview only; raw value never persisted
- `GET /api/v1/documents/{id}/pii-findings` — admin/compliance officer only
- PII count visible in document response for privileged roles

### Admin Document Controls
- `DELETE /api/v1/documents/{id}` — admin only; deletes from DB, Qdrant, filesystem
- `POST /api/v1/documents/{id}/reindex` — admin/compliance officer; re-runs pipeline

### Security Documentation
- `docs/security-model.md` — RBAC, classification, retrieval filtering, audit, PII
- `docs/threat-model.md` — 8 threat categories with mitigations and residual risks

---

## Intentionally Excluded from Phase 2

- Frontend / dashboard UI
- Langfuse observability
- RAGAS evaluation pipeline
- vLLM backend support
- Kubernetes / Helm deployment
- Encryption at rest for uploaded files
- SSO / SAML / OIDC authentication
- Production secrets manager
- Rate limiting and account lockout
- Email delivery for invitations (token returned in API response for local testing)
- ML-based PII detection (regex only in Phase 2)
- Analyst access to restricted documents is fully blocked at both the application and Qdrant layers
- Streaming LLM responses

---

## Phase 3 Planned Items

| Feature | Description |
|---|---|
| Langfuse | LLM observability — trace every RAG call end to end |
| RAGAS | Automated RAG quality evaluation (faithfulness, relevance, recall) |
| Evaluation dashboard | Visualize RAGAS scores over time |
| Prompt injection checks | Input sanitization and classification before LLM call |
| Frontend dashboard | React/Next.js UI for document management and chat |
| vLLM support | GPU-accelerated inference backend |
| Deployment hardening | HTTPS, secrets manager, encryption at rest, K8s Helm chart |
| Email invitations | SMTP delivery of invite links |
| Streaming answers | Server-Sent Events for token-by-token output |
| ML PII detection | Named entity recognition for context-aware PII detection |
| Account lockout | Failed login counter + temporary lockout |
| MFA | TOTP-based multi-factor authentication |
