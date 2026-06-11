# Monitoring and Observability

## Prometheus Metrics

AegisRAG exposes Prometheus metrics at `GET /metrics` (no auth required — restrict at the network level).

### Key Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `aegisrag_rag_queries_total` | Counter | RAG queries by tenant, model, cache_hit |
| `aegisrag_rag_query_latency_seconds` | Histogram | End-to-end query latency |
| `aegisrag_llm_latency_seconds` | Histogram | Inference latency by provider and model |
| `aegisrag_tokens_used_total` | Counter | LLM tokens by tenant, model, type |
| `aegisrag_cache_ops_total` | Counter | Cache operations (hit/miss) by tier |
| `aegisrag_prompt_injection_blocked_total` | Counter | Blocked queries per tenant |
| `aegisrag_security_alerts_total` | Counter | Security alerts by severity |
| `aegisrag_celery_queue_depth` | Gauge | Current Celery task queue depth |

### SLO Queries

**p95 query latency by tenant (5-min window):**
```promql
histogram_quantile(0.95, sum by (tenant_id, le)(
  rate(aegisrag_rag_query_latency_seconds_bucket[5m])
))
```

**Cache hit rate:**
```promql
sum(rate(aegisrag_cache_ops_total{result="hit"}[5m]))
/ sum(rate(aegisrag_cache_ops_total[5m])) * 100
```

**Error rate:**
```promql
rate(aegisrag_rag_query_errors_total[5m])
/ rate(aegisrag_rag_queries_total[5m])
```

## Grafana Dashboards

Import `infra/monitoring/grafana-dashboard-rag.json` into Grafana (Dashboards → Import).

The dashboard covers:
- Query rate and error rate
- p50/p95/p99 latency time series
- Cache hit rate gauge
- Token usage by type
- LLM latency by provider
- Security event counts
- Celery queue depth

## Alerting

Prometheus alert rules are in `infra/monitoring/alert_rules.yml`. Key alerts:

- **HighRAGQueryLatency** — p95 > 10s for 5 minutes (warning)
- **HighErrorRate** — error rate > 5% for 2 minutes (critical)
- **LLMProviderDown** — no LLM traffic for 5 minutes (critical)
- **HighPromptInjectionRate** — > 0.5 blocks/sec for 2 minutes (high)
- **CeleryQueueBacklog** — queue depth > 100 for 5 minutes (warning)

## Application-Level Observability

### Security Alerts (REST API)
```
GET /api/v1/monitoring/alerts          # unresolved alerts
PATCH /api/v1/monitoring/alerts/{id}/resolve
```

### Usage Metrics
```
GET /api/v1/monitoring/usage           # all-time totals
GET /api/v1/monitoring/usage/history?days=30  # daily breakdown
```

### System Health
```
GET /api/v1/monitoring/health          # DB, Redis, Qdrant, Ollama, vLLM
GET /api/v1/monitoring/cache-stats     # Redis memory and connection info
```

## Langfuse (Optional)

Set `LANGFUSE_SECRET_KEY` and `LANGFUSE_PUBLIC_KEY` to enable trace-level observability. Langfuse captures:
- Full prompt/response pairs per query
- Retrieval span (candidates returned, cache hit)
- Generation span (model, latency, output preview)

Traces are associated with `user_id` for per-user analysis.

## OpenTelemetry (Optional)

Set `OTEL_ENABLED=true` and `OTEL_EXPORTER_OTLP_ENDPOINT` to export traces to Jaeger, Tempo, or any OTLP-compatible backend. The FastAPIInstrumentor automatically traces all HTTP requests.
