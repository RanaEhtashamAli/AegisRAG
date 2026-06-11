# AegisRAG Threat Model

## Scope

This document covers the Phase 2 threat model for the AegisRAG backend. The system processes potentially sensitive enterprise documents and generates answers using a local LLM.

---

## Assets

| Asset | Description |
|---|---|
| Uploaded PDF documents | May contain confidential or restricted business information |
| Extracted text and embeddings | Derived from documents; stored in PostgreSQL and Qdrant |
| User credentials | Hashed passwords, JWT tokens |
| Audit logs | Immutable record of all security-relevant events |
| PII findings | Masked; raw values are never stored |
| Tenant boundary | Logical separation between tenants |

---

## Threats and Mitigations

### T1: Cross-Tenant Data Leakage

**Description**: A user from Tenant A accesses documents or vectors belonging to Tenant B.

**Mitigations**:
- All database queries filter by `tenant_id` derived from the authenticated user's JWT
- All Qdrant searches include a mandatory `must` filter on `payload.tenant_id`
- `get_tenant_user` FastAPI dependency blocks users without `tenant_id` from all tenant-scoped endpoints
- No endpoint accepts `tenant_id` as a user-supplied query parameter

**Residual risk**: Low — enforced at multiple independent layers.

---

### T2: Unauthorized Document Access Within a Tenant

**Description**: A `viewer` accesses a `confidential` document, or an `analyst` accesses a `restricted` document.

**Mitigations**:
- `get_documents` filters results by `allowed_classifications` derived from `UserRole`
- `get_document` calls `can_access_document()` before returning any data
- `qdrant_service.search()` filters vectors by `allowed_classifications` — even if application logic is bypassed, the vector DB enforces the restriction
- Role is stored server-side in the database and cannot be self-modified

**Residual risk**: Low. Restricted access is enforced at both the application layer and the Qdrant vector-search layer.

---

### T3: Prompt Injection via Uploaded Documents

**Description**: A malicious document contains instructions designed to manipulate the LLM into ignoring context constraints or leaking information from other chunks.

**Mitigations**:
- The system prompt explicitly instructs the LLM to answer only from the provided context
- Classification filtering limits which chunks appear in any given user's context window
- Local LLM (Ollama) — no data sent to external services

**Residual risk**: Medium — no advanced prompt injection defense (e.g., content classifiers, input sanitization) is implemented in Phase 2. This is a known gap.

---

### T4: Hallucinated Answers

**Description**: The LLM generates factually incorrect answers not supported by the retrieved context.

**Mitigations**:
- System prompt: *"Answer only using the provided context. If the context does not contain enough information, say you do not have enough information. Do not invent facts."*
- `text_preview` in sources allows users to verify citations
- RAG audit log records which document IDs were retrieved

**Residual risk**: Medium — LLM instruction-following is probabilistic. Phase 3 will add RAGAS evaluation.

---

### T5: Sensitive Data Exposure in Logs

**Description**: PII or secret values are written to audit logs or application logs.

**Mitigations**:
- PII findings store only SHA-256 hashes and masked previews
- Raw matched text is never persisted anywhere
- Audit event `metadata_json` does not include document content — only IDs, filenames, and counts
- Application logs (structlog) do not log request bodies

**Residual risk**: Low — developers should audit new `AuditService.log()` calls to ensure no raw sensitive values are placed in `metadata`.

---

### T6: Credential Theft / Account Takeover

**Description**: An attacker obtains user credentials or a JWT token.

**Mitigations**:
- Passwords are hashed with Argon2 (memory-hard, resistant to GPU brute-force)
- JWTs expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60)
- Failed login attempts are audit-logged with IP address
- HTTPS should be terminated at the reverse proxy (not AegisRAG's responsibility in Phase 2)

**Residual risk**: Medium — no refresh token rotation, no MFA, no account lockout implemented yet.

---

### T7: Insecure External LLM Usage

**Description**: In some configurations, the LLM endpoint could be an external cloud service, causing confidential document content to be transmitted to third parties.

**Mitigations**:
- Default configuration uses Ollama running locally in Docker — no external API calls
- `OLLAMA_BASE_URL` is an environment variable; misconfiguring it to a cloud endpoint would leak data, so it must be access-controlled

**Residual risk**: Deployment-dependent — document this clearly in production setup guides.

---

### T8: Privilege Escalation

**Description**: A user elevates their own role or accesses admin-only endpoints.

**Mitigations**:
- `require_tenant_admin()` dependency verifies role from the database, not from the JWT
- Users cannot update their own role — only a `tenant_admin` can update other users' roles
- A `tenant_admin` cannot demote themselves if they are the only admin

**Residual risk**: Low.

---

## Known Gaps (Addressed in Phase 3)

| Gap | Phase 3 Plan |
|---|---|
| No prompt injection defense | Content classifiers, input sanitization |
| No encryption at rest | Encrypt uploaded files; encrypt Qdrant storage volume |
| No SSO / OIDC | SAML / OIDC integration |
| No secrets manager | Vault or cloud KMS integration |
| No full DLP system | Integration with enterprise DLP tools |
| No rate limiting | API gateway or middleware rate limiting |
| No account lockout | Failed login counter + lockout policy |
| No RAGAS evaluation | Automated answer quality monitoring |
