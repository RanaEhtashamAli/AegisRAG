# Disaster Recovery

## Backup Strategy

### PostgreSQL
AegisRAG stores all relational data (users, documents, audit events, chat sessions) in PostgreSQL. Back up with:

```bash
# Continuous WAL archiving (recommended for production)
# Configure archive_command in postgresql.conf

# Daily logical backup
pg_dump -U aegisrag aegisrag | gzip > backup-$(date +%Y%m%d).sql.gz

# With Kubernetes
kubectl exec -n aegisrag postgres-0 -- \
  pg_dump -U aegisrag aegisrag | gzip > backup-$(date +%Y%m%d).sql.gz
```

**RPO target:** 1 hour (with WAL archiving)  
**RTO target:** 30 minutes (point-in-time restore from WAL)

### Qdrant
Qdrant vectors can be re-indexed from the source documents. However, for faster recovery:

```bash
# Qdrant snapshot
curl -X POST "http://qdrant:6333/collections/aegisrag_chunks/snapshots"
# Download and store snapshot in object storage
```

If no snapshot is available, trigger re-ingestion of all documents after DB restore — the Celery worker will rebuild the vector index from stored files.

### Document Files
Documents uploaded to MinIO/S3 are the source of truth. Enable versioning and cross-region replication:

```bash
# MinIO replication
mc mirror --watch minio/aegisrag-uploads s3/aegisrag-backup
```

## Recovery Procedures

### Database restore

```bash
# Stop API and worker pods to prevent writes during restore
kubectl scale deployment aegisrag-api aegisrag-worker --replicas=0 -n aegisrag

# Restore from backup
kubectl exec -n aegisrag postgres-0 -- \
  psql -U aegisrag aegisrag < backup-20250101.sql

# Run pending migrations
kubectl exec -n aegisrag deployment/aegisrag-api -- alembic upgrade head

# Resume service
kubectl scale deployment aegisrag-api --replicas=2 -n aegisrag
kubectl scale deployment aegisrag-worker --replicas=2 -n aegisrag
```

### Vector index rebuild

If the Qdrant volume is lost but the PostgreSQL `document_chunks` table and original files are intact:

1. Clear the collection: `DELETE /collections/aegisrag_chunks`
2. Trigger re-ingestion via the Celery task for all existing documents
3. Monitor `aegisrag_ingestion_total` metric until counts match

### Cache loss

Redis is a cache — loss is non-critical. The application falls back to full database and Qdrant queries automatically. No recovery action needed. Cache warms up organically over time.

## Runbooks

### API returning 500s
1. Check `kubectl logs deployment/aegisrag-api -n aegisrag`
2. Check DB connectivity: `GET /api/v1/monitoring/health`
3. Check Qdrant: `curl http://qdrant:6333/readyz`
4. Roll back if recent deploy: `kubectl rollout undo deployment/aegisrag-api -n aegisrag`

### High latency
1. Check `aegisrag_rag_query_latency_seconds` p95 in Grafana
2. Check cache hit rate — if near 0%, Redis may be down
3. Check vLLM health: `GET /api/v1/monitoring/health`
4. Scale API replicas if CPU > 80%: `kubectl scale deployment aegisrag-api --replicas=4 -n aegisrag`

### Security incident
1. Immediately rotate `SECRET_KEY` (invalidates all sessions)
2. Rotate `FIELD_ENCRYPTION_KEY` (requires re-encrypt of stored ciphertext)
3. Export full audit log: `POST /api/v1/compliance/export-audit?format=json`
4. Review `security_alerts` table for scope of compromise
5. Apply pod restart to pick up new secrets

## RTO / RPO Targets

| Component | RPO | RTO |
|-----------|-----|-----|
| PostgreSQL | 1 hour | 30 min |
| Qdrant vectors | Re-ingestable | 2 hours |
| Document files | Near-zero (S3 versioning) | 1 hour |
| Redis cache | N/A (ephemeral) | Instant |
