# Scaling Strategy

## Bottlenecks by Load Level

### < 10 req/s (Small deployment)
- Single API replica, single worker, CPU-bound Ollama
- Default configuration is sufficient
- SQLite-level Postgres (1 CPU, 512MB)

### 10–100 req/s (Medium deployment)
- 2–3 API replicas behind load balancer
- 4–8 Celery workers for document ingestion
- Redis cache becomes critical — aim for >70% hit rate
- Upgrade to GPU-backed vLLM for inference
- Consider connection pooling (PgBouncer) in front of Postgres

### 100+ req/s (Large deployment)
- HPA on API and worker deployments (CPU-based, see `backend-worker.yaml`)
- Qdrant clustering or managed Qdrant Cloud
- Postgres read replicas for query-heavy workloads
- vLLM tensor parallelism across multiple GPUs (`--tensor-parallel-size 4`)
- Redis Cluster or Valkey for cache sharding

## Component-Specific Scaling

### API (aegisrag-api)
Stateless — scale horizontally without limit. Target 70% CPU utilization.

### Workers (aegisrag-worker)
CPU-bound (embedding + chunking). Each worker uses ~1.5GB RAM for embedding model. Scale by CPU, not memory. HPA configured at 70% CPU.

### Qdrant
Single-node supports millions of vectors. For HA, use Qdrant's distributed mode:
- 3 nodes minimum
- Replication factor 2
- Enable quantization for memory efficiency: `ScalarQuantization(type=ScalarType.INT8)`

### PostgreSQL
Use `pgvector` extension if you want to co-locate embeddings with metadata. Otherwise, keep Postgres for relational data only and scale by:
- Read replicas for audit/usage queries
- Connection pooling (PgBouncer) to reduce connection overhead

### Redis Cache
Cache hit rate is the primary scaling lever. Tune TTLs:
- Embedding TTL: 1h (embeddings are deterministic)
- Retrieval TTL: 5m (documents change infrequently)
- Response TTL: 1m (queries may have different context)

For distributed cache, upgrade to Redis Cluster. The `cache_service` only uses standard Redis commands and is cluster-compatible.

## Embedding Bottleneck

The sentence-transformers embedding model runs on CPU by default. For high throughput:
1. Enable GPU in the worker deployment
2. Use a faster embedding model (e.g., `BAAI/bge-small-en-v1.5`)
3. Or run a dedicated embedding microservice (e.g., infinity-emb) and update `embedding_service.py`

## Load Test Results (Baseline)

Run with `locust -f backend/load_tests/locustfile.py`:

| Scenario | Concurrency | p50 | p95 | p99 | Failure rate |
|----------|-------------|-----|-----|-----|--------------|
| RAG query (cached) | 20 users | ~50ms | ~200ms | ~500ms | 0% |
| RAG query (cold) | 20 users | ~2s | ~5s | ~10s | <1% |
| Document upload | 10 users | ~3s | ~8s | ~15s | <1% |

*Baseline measured on: 4 CPU / 16GB RAM, Ollama llama3.1:8b, no GPU.*
