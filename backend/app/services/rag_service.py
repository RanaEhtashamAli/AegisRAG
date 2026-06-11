from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import get_allowed_classifications
from app.models.user import User
from app.schemas.rag import RAGQueryResponse, SourceReference
from app.services.audit_service import AuditService
from app.services.cache_service import cache_service
from app.services.chat_service import ChatService
from app.services.embedding_service import embedding_service
from app.services.hybrid_retrieval_service import hybrid_retrieval_service
from app.services.metrics_service import (
    cache_ops_total,
    measure_embedding,
    measure_llm,
    measure_rerank,
    measure_vector_search,
    prompt_injection_blocked_total,
    rag_queries_total,
    rag_query_latency,
    tokens_used_total,
)
from app.services.model_router import model_router
from app.services.observability_service import TraceContext
from app.services.prompt_security_service import prompt_security_service
from app.services.qdrant_service import qdrant_service
from app.services.reranking_service import reranking_service
from app.services.usage_metrics_service import UsageMetricsService


def _format_history_for_context(messages) -> str:
    if not messages:
        return ""
    lines = []
    for m in messages:
        role = "User" if m.role == "user" else "Assistant"
        lines.append(f"{role}: {m.content}")
    return "\n".join(lines)


def _vector_hits_to_candidates(hits) -> list[dict]:
    return [
        {"chunk_id": str(h.id), "score": h.score, "payload": h.payload or {}}
        for h in hits
    ]


def _build_sources_and_context(
    candidates: list[dict],
) -> tuple[list[SourceReference], list[str], list[str]]:
    sources: list[SourceReference] = []
    context_chunks: list[str] = []
    retrieved_doc_ids: list[str] = []

    for c in candidates:
        payload = c.get("payload") or {}
        doc_id = payload.get("document_id")
        if not doc_id:
            continue
        sources.append(
            SourceReference(
                document_id=uuid.UUID(doc_id),
                filename=payload.get("original_filename", ""),
                page_number=payload.get("page_number"),
                chunk_index=payload.get("chunk_index", 0),
                score=c.get("score", 0.0),
                text_preview=payload.get("text", "")[:300],
            )
        )
        context_chunks.append(payload.get("text", ""))
        retrieved_doc_ids.append(doc_id)

    return sources, context_chunks, retrieved_doc_ids


class RAGService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _retrieve(
        self,
        question: str,
        top_k: int,
        user: User,
        allowed_classifications: list[str],
    ) -> tuple[list[dict], bool]:
        """Returns (candidates, cache_hit)."""
        # Try retrieval cache first
        cached = cache_service.get_retrieval(
            str(user.tenant_id), question, allowed_classifications
        )
        if cached is not None:
            cache_ops_total.labels(op="retrieve", result="hit").inc()
            return cached, True
        cache_ops_total.labels(op="retrieve", result="miss").inc()

        if settings.HYBRID_RETRIEVAL_ENABLED:
            with measure_vector_search():
                candidates = hybrid_retrieval_service.search(
                    query=question,
                    tenant_id=str(user.tenant_id),
                    allowed_classifications=allowed_classifications,
                    top_k=top_k,
                    db=self.db,
                )
        else:
            with measure_embedding():
                query_vector = embedding_service.embed_text(question)
            with measure_vector_search():
                hits = qdrant_service.search(
                    query_vector=query_vector,
                    tenant_id=str(user.tenant_id),
                    allowed_classifications=allowed_classifications,
                    top_k=top_k,
                )
            candidates = _vector_hits_to_candidates(hits)

        if settings.RERANKING_ENABLED:
            with measure_rerank():
                candidates = reranking_service.rerank(question, candidates)

        cache_service.set_retrieval(
            str(user.tenant_id), question, allowed_classifications, candidates
        )
        return candidates, False

    def query(
        self,
        question: str,
        top_k: int,
        user: User,
        session_id: uuid.UUID | None = None,
    ) -> RAGQueryResponse:
        start = time.monotonic()
        allowed_classifications = get_allowed_classifications(user)
        chat_svc = ChatService(self.db)
        usage_svc = UsageMetricsService(self.db)

        sec_result = prompt_security_service.check(question)
        if not sec_result.is_safe:
            prompt_security_service.log_event(
                db=self.db,
                tenant_id=user.tenant_id,
                user_id=user.id,
                input_text=question,
                result=sec_result,
                action_taken="blocked",
            )
            prompt_injection_blocked_total.labels(tenant_id=str(user.tenant_id)).inc()
            return RAGQueryResponse(
                answer="Your query was flagged by the security filter. Please rephrase.",
                sources=[],
                warning="prompt_injection_detected",
            )

        # Response cache
        cached_answer = cache_service.get_response(
            str(user.tenant_id), question, allowed_classifications
        )
        cache_hit = cached_answer is not None

        history_prefix = ""
        if session_id:
            prior = chat_svc.get_context_messages(session_id)
            history_prefix = _format_history_for_context(prior)

        trace = TraceContext(
            name="rag.query",
            metadata={"top_k": top_k, "allowed_classifications": allowed_classifications},
            user_id=str(user.id),
        )

        retrieval_span = trace.span("retrieval", input=question)
        candidates, retrieval_cache_hit = self._retrieve(
            question, top_k, user, allowed_classifications
        )
        retrieval_span.end(output={"count": len(candidates)})

        sources, context_chunks, retrieved_doc_ids = _build_sources_and_context(candidates)

        if cache_hit and cached_answer:
            answer = cached_answer
            prompt_tokens = completion_tokens = 0
            provider_name = "cache"
            model_name = "cache"
        else:
            gen_span = trace.span("generation", input=question)
            provider, inference_request = model_router.build_request(
                question=question,
                context_chunks=context_chunks,
                history_prefix=history_prefix,
                classification=max(
                    (c.get("payload", {}).get("classification", "public") for c in candidates),
                    default="public",
                    key=lambda x: ["public", "internal", "confidential", "restricted"].index(x)
                    if x in ["public", "internal", "confidential", "restricted"]
                    else 0,
                ),
            )
            import asyncio
            with measure_llm(provider.provider_name, inference_request.model):
                response = asyncio.get_event_loop().run_until_complete(
                    provider.generate(inference_request)
                )
            answer = response.content
            prompt_tokens = response.prompt_tokens
            completion_tokens = response.completion_tokens
            provider_name = provider.provider_name
            model_name = inference_request.model
            gen_span.end(output=answer[:500])

            cache_service.set_response(
                str(user.tenant_id), question, allowed_classifications, answer
            )

        latency_ms = int((time.monotonic() - start) * 1000)
        trace.update(output=answer[:500], metadata={"latency_ms": latency_ms})

        # Metrics
        rag_queries_total.labels(
            tenant_id=str(user.tenant_id), model=model_name, cached=str(cache_hit)
        ).inc()
        rag_query_latency.labels(tenant_id=str(user.tenant_id)).observe(
            time.monotonic() - start
        )
        if prompt_tokens:
            tokens_used_total.labels(
                tenant_id=str(user.tenant_id), model=model_name, token_type="prompt"
            ).inc(prompt_tokens)
        if completion_tokens:
            tokens_used_total.labels(
                tenant_id=str(user.tenant_id), model=model_name, token_type="completion"
            ).inc(completion_tokens)
        cache_ops_total.labels(op="response", result="hit" if cache_hit else "miss").inc()

        # Usage metrics
        try:
            usage_svc.record_query(
                tenant_id=user.tenant_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                model=model_name,
                cache_hit=cache_hit,
                estimated_cost_usd=(prompt_tokens + completion_tokens) * 0.000002,
            )
        except Exception:
            pass  # never fail a query because of metrics

        if session_id:
            chat_svc.add_message(session_id, "user", question)
            chat_svc.add_message(
                session_id,
                "assistant",
                answer,
                retrieved_doc_ids=list(set(retrieved_doc_ids)),
                latency_ms=latency_ms,
            )

        AuditService(self.db).log(
            event_type="rag.query",
            user_id=user.id,
            tenant_id=user.tenant_id,
            metadata={
                "question": question,
                "top_k": top_k,
                "allowed_classifications": allowed_classifications,
                "retrieved_document_ids": list(set(retrieved_doc_ids)),
                "latency_ms": latency_ms,
                "model": model_name,
                "provider": provider_name,
                "number_of_sources": len(sources),
                "cache_hit": cache_hit,
                "hybrid": settings.HYBRID_RETRIEVAL_ENABLED,
                "reranked": settings.RERANKING_ENABLED,
            },
        )

        return RAGQueryResponse(answer=answer, sources=sources)

    async def query_stream(
        self,
        question: str,
        top_k: int,
        user: User,
        session_id: uuid.UUID | None = None,
    ) -> AsyncIterator[str]:
        allowed_classifications = get_allowed_classifications(user)
        chat_svc = ChatService(self.db)
        start = time.monotonic()

        sec_result = prompt_security_service.check(question)
        if not sec_result.is_safe:
            prompt_security_service.log_event(
                db=self.db,
                tenant_id=user.tenant_id,
                user_id=user.id,
                input_text=question,
                result=sec_result,
                action_taken="blocked",
            )
            prompt_injection_blocked_total.labels(tenant_id=str(user.tenant_id)).inc()
            yield json.dumps({"type": "error", "content": "Query blocked by security filter."})
            return

        history_prefix = ""
        if session_id:
            prior = chat_svc.get_context_messages(session_id)
            history_prefix = _format_history_for_context(prior)
            chat_svc.add_message(session_id, "user", question)

        candidates, _ = self._retrieve(question, top_k, user, allowed_classifications)
        sources, context_chunks, retrieved_doc_ids = _build_sources_and_context(candidates)

        sources_payload = [
            {
                "document_id": str(s.document_id),
                "filename": s.filename,
                "page_number": s.page_number,
                "score": s.score,
                "text_preview": s.text_preview,
            }
            for s in sources
        ]
        yield json.dumps({"type": "sources", "sources": sources_payload})

        top_classification = max(
            (c.get("payload", {}).get("classification", "public") for c in candidates),
            default="public",
            key=lambda x: ["public", "internal", "confidential", "restricted"].index(x)
            if x in ["public", "internal", "confidential", "restricted"]
            else 0,
        )
        provider, inference_request = model_router.build_request(
            question=question,
            context_chunks=context_chunks,
            history_prefix=history_prefix,
            classification=top_classification,
        )
        inference_request.stream = True

        full_answer: list[str] = []
        with measure_llm(provider.provider_name, inference_request.model):
            async for token in provider.generate_stream(inference_request):
                full_answer.append(token)
                yield json.dumps({"type": "token", "content": token})

        yield json.dumps({"type": "done"})

        latency_ms = int((time.monotonic() - start) * 1000)
        assembled = "".join(full_answer)

        rag_queries_total.labels(
            tenant_id=str(user.tenant_id), model=inference_request.model, cached="False"
        ).inc()

        if session_id:
            chat_svc.add_message(
                session_id,
                "assistant",
                assembled,
                retrieved_doc_ids=list(set(retrieved_doc_ids)),
                latency_ms=latency_ms,
            )

        AuditService(self.db).log(
            event_type="rag.query",
            user_id=user.id,
            tenant_id=user.tenant_id,
            metadata={
                "question": question,
                "top_k": top_k,
                "allowed_classifications": allowed_classifications,
                "retrieved_document_ids": list(set(retrieved_doc_ids)),
                "model": inference_request.model,
                "provider": provider.provider_name,
                "streaming": True,
                "latency_ms": latency_ms,
            },
        )

    def debug_query(self, question: str, top_k: int, user: User) -> dict:
        allowed_classifications = get_allowed_classifications(user)
        start = time.monotonic()

        with measure_embedding():
            query_vector = embedding_service.embed_text(question)
        with measure_vector_search():
            vector_hits = qdrant_service.search(
                query_vector=query_vector,
                tenant_id=str(user.tenant_id),
                allowed_classifications=allowed_classifications,
                top_k=top_k,
            )

        vector_debug = [
            {
                "chunk_id": str(h.id),
                "score": h.score,
                "document_id": (h.payload or {}).get("document_id"),
                "filename": (h.payload or {}).get("original_filename"),
                "text_preview": (h.payload or {}).get("text", "")[:200],
            }
            for h in vector_hits
        ]

        fts_rows = hybrid_retrieval_service._fts_search(
            question, str(user.tenant_id), allowed_classifications, top_k, self.db
        )
        fts_debug = [
            {
                "chunk_id": str(r.get("chunk_id")),
                "document_id": str(r.get("document_id")),
                "filename": r.get("original_filename"),
                "text_preview": (r.get("content") or "")[:200],
            }
            for r in fts_rows
        ]

        with measure_vector_search():
            hybrid_candidates = hybrid_retrieval_service.search(
                query=question,
                tenant_id=str(user.tenant_id),
                allowed_classifications=allowed_classifications,
                top_k=top_k,
                db=self.db,
            )

        latency_ms = int((time.monotonic() - start) * 1000)
        cache_stats = cache_service.stats()

        return {
            "question": question,
            "allowed_classifications": allowed_classifications,
            "vector_results": vector_debug,
            "fts_results": fts_debug,
            "hybrid_merged": [
                {
                    "chunk_id": c["chunk_id"],
                    "rrf_score": c["score"],
                    "vector_score": c.get("vector_score"),
                    "text_preview": c.get("payload", {}).get("text", "")[:200],
                }
                for c in hybrid_candidates
            ],
            "reranking_enabled": settings.RERANKING_ENABLED,
            "hybrid_enabled": settings.HYBRID_RETRIEVAL_ENABLED,
            "vllm_enabled": settings.VLLM_ENABLED,
            "cache_stats": cache_stats,
            "latency_ms": latency_ms,
        }
