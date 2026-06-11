# Security Hardening Guide

## Authentication and Authorization

AegisRAG uses JWT-based authentication with role-based access control (RBAC).

**Roles:** `tenant_admin`, `compliance_officer`, `analyst`, `viewer`

**Classification access matrix:**

| Role | Public | Internal | Confidential | Restricted |
|------|--------|----------|--------------|------------|
| viewer | ✓ | ✓ | — | — |
| analyst | ✓ | ✓ | ✓ | Own docs only |
| compliance_officer | ✓ | ✓ | ✓ | ✓ |
| tenant_admin | ✓ | ✓ | ✓ | ✓ |

## Rate Limiting

The `/auth/login` endpoint is rate-limited to 10 requests/minute per IP (configurable via `LOGIN_RATE_LIMIT`). Brute-force detection triggers a `SecurityAlert` after `FAILED_LOGIN_ALERT_THRESHOLD` (default: 5) failures within `FAILED_LOGIN_WINDOW_MINUTES` (default: 15 min).

## Prompt Injection Detection

All user queries are checked against a keyword + regex pattern set before entering the RAG pipeline. Blocked queries are:
- Logged to `prompt_security_events` table
- Reported as a `SecurityAlert`
- Counted in `aegisrag_prompt_injection_blocked_total` Prometheus metric

To add custom patterns, extend `prompt_security_service.py`.

## Field-Level Encryption

Sensitive fields can be encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256). Set `FIELD_ENCRYPTION_KEY` to a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Limitations:** Fernet is symmetric — key compromise exposes all stored ciphertext. Use HashiCorp Vault or AWS KMS for the key in production.

## Vector Search Isolation

Every Qdrant search call enforces `tenant_id` AND `classification` filters. Cross-tenant data leakage is structurally impossible — the filters are applied server-side in the vector database, not in application code.

Restricted data queries are **never** cached globally to prevent cross-context exposure.

## Data Retention

Configure per-tenant data retention via the compliance API:

```
PUT /api/v1/compliance/retention-policy
{"retention_days": 90, "auto_delete_enabled": true}
```

When `auto_delete_enabled=true`, a scheduled Celery task purges documents older than `retention_days`.

## Audit Logging

Every significant action (login, document upload, RAG query, classification change) is logged to `audit_events`. Audit logs can be exported as JSON or CSV:

```
POST /api/v1/compliance/export-audit?format=csv&since=2025-01-01
```

Audit logs are immutable — they are insert-only and no update/delete operations are exposed via the API.

## Container Security

- All images run as non-root
- Read-only root filesystem where possible
- Secrets injected via Kubernetes Secrets (not environment files)
- Weekly automated Trivy container scans in CI

## Network Policies

Apply Kubernetes NetworkPolicy to restrict pod-to-pod communication:

```yaml
# Only allow aegisrag-api to reach postgres, redis, qdrant
# Deny all other inter-pod traffic
```

See `infra/k8s/base/` for policy templates (add NetworkPolicy manifests as required by your cluster CNI).

## TLS

All external traffic is TLS-terminated at the NGINX ingress. Backend-to-backend traffic within the cluster uses plaintext on the cluster network. If you require mTLS between services, configure a service mesh (Istio, Linkerd).

## Secret Rotation

1. Generate new `SECRET_KEY` — existing JWT tokens will be invalidated (users must re-login)
2. Generate new `FIELD_ENCRYPTION_KEY` — requires re-encrypting all stored ciphertext before retiring the old key
3. Rotate `POSTGRES_PASSWORD` — update the secret and restart all pods

Never commit secrets to source control. Use Sealed Secrets or External Secrets Operator for GitOps workflows.
