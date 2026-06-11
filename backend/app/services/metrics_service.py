"""Prometheus metrics registry for AegisRAG.

All metrics are registered once at module import. Endpoints that want to
record a measurement call the helper functions below.

The /metrics endpoint (added in main.py) exposes these via prometheus_client.
"""
from __future__ import annotations

import time
from contextlib import contextmanager

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
)

# ── Counters ──────────────────────────────────────────────────────────────────

rag_queries_total = Counter(
    "aegisrag_rag_queries_total",
    "Total RAG queries processed",
    ["tenant_id", "model", "cached"],
)

rag_query_errors_total = Counter(
    "aegisrag_rag_query_errors_total",
    "Total RAG query errors",
    ["tenant_id", "error_type"],
)

ingestion_total = Counter(
    "aegisrag_ingestion_total",
    "Total documents ingested",
    ["tenant_id", "status"],
)

cache_ops_total = Counter(
    "aegisrag_cache_ops_total",
    "Cache operations",
    ["op", "result"],  # op: embed|retrieve|response, result: hit|miss
)

auth_events_total = Counter(
    "aegisrag_auth_events_total",
    "Authentication events",
    ["event_type"],  # login_success, login_failed
)

security_alerts_total = Counter(
    "aegisrag_security_alerts_total",
    "Security alerts generated",
    ["severity", "event_type"],
)

tokens_used_total = Counter(
    "aegisrag_tokens_used_total",
    "Total LLM tokens consumed",
    ["tenant_id", "model", "token_type"],  # token_type: prompt|completion
)

prompt_injection_blocked_total = Counter(
    "aegisrag_prompt_injection_blocked_total",
    "Prompt injection attempts blocked",
    ["tenant_id"],
)

# ── Histograms ────────────────────────────────────────────────────────────────

_LATENCY_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)

rag_query_latency = Histogram(
    "aegisrag_rag_query_latency_seconds",
    "End-to-end RAG query latency",
    ["tenant_id"],
    buckets=_LATENCY_BUCKETS,
)

embedding_latency = Histogram(
    "aegisrag_embedding_latency_seconds",
    "Embedding generation latency",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
)

vector_search_latency = Histogram(
    "aegisrag_vector_search_latency_seconds",
    "Qdrant vector search latency",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
)

rerank_latency = Histogram(
    "aegisrag_rerank_latency_seconds",
    "Cross-encoder reranking latency",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
)

llm_latency = Histogram(
    "aegisrag_llm_latency_seconds",
    "LLM inference latency",
    ["provider", "model"],
    buckets=_LATENCY_BUCKETS,
)

ingestion_latency = Histogram(
    "aegisrag_ingestion_latency_seconds",
    "Document ingestion pipeline latency",
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

# ── Gauges ────────────────────────────────────────────────────────────────────

celery_queue_depth = Gauge(
    "aegisrag_celery_queue_depth",
    "Number of tasks in the Celery queue",
)

active_tenants = Gauge(
    "aegisrag_active_tenants_total",
    "Number of tenants in the system",
)

# ── Context managers for latency timing ───────────────────────────────────────

@contextmanager
def measure_embedding():
    start = time.monotonic()
    try:
        yield
    finally:
        embedding_latency.observe(time.monotonic() - start)


@contextmanager
def measure_vector_search():
    start = time.monotonic()
    try:
        yield
    finally:
        vector_search_latency.observe(time.monotonic() - start)


@contextmanager
def measure_rerank():
    start = time.monotonic()
    try:
        yield
    finally:
        rerank_latency.observe(time.monotonic() - start)


@contextmanager
def measure_llm(provider: str, model: str):
    start = time.monotonic()
    try:
        yield
    finally:
        llm_latency.labels(provider=provider, model=model).observe(time.monotonic() - start)
