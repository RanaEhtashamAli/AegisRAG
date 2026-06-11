import uuid
from datetime import UTC, datetime

from app.core.logging import logger
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.pii_finding import PiiFinding
from app.services.audit_service import AuditService
from app.services.chunking_service import chunk_text
from app.services.document_parser import extract_pages
from app.services.embedding_service import embedding_service
from app.services.pii_service import detect_pii, hash_raw_value
from app.services.qdrant_service import qdrant_service
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_document(self, document_id: str) -> None:
    """Extract, chunk, embed, and index a PDF document into Qdrant.

    Handles both initial indexing and re-indexing: existing chunks/vectors
    are removed before the new ones are written.
    """
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error("process_document_not_found", document_id=document_id)
            return

        doc.status = "processing"
        db.commit()
        logger.info("document_processing_started", document_id=document_id)

        # --- Clean up stale chunks/vectors from previous indexing runs ---
        existing_chunks = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == doc.id)
            .all()
        )
        if existing_chunks:
            try:
                qdrant_service.delete_by_document(str(doc.id), str(doc.tenant_id))
            except Exception as e:
                logger.warning(
                    "qdrant_cleanup_failed", document_id=document_id, error=str(e)
                )
            db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
            db.query(PiiFinding).filter(PiiFinding.document_id == doc.id).delete()
            db.commit()

        # --- Text extraction & chunking ---
        pages = extract_pages(doc.file_path)
        chunks = chunk_text(pages)

        if not chunks:
            raise ValueError("No text could be extracted from the document.")

        texts = [c.text for c in chunks]
        vectors = embedding_service.embed_texts(texts)

        qdrant_service.ensure_collection()

        points: list[dict] = []
        chunk_records: list[DocumentChunk] = []
        pii_records: list[PiiFinding] = []

        for chunk, vector in zip(chunks, vectors):
            point_id = str(uuid.uuid4())

            points.append(
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": {
                        "tenant_id": str(doc.tenant_id),
                        "document_id": str(doc.id),
                        "chunk_id": point_id,
                        "chunk_index": chunk.chunk_index,
                        "page_number": chunk.page_number,
                        "text": chunk.text,
                        "original_filename": doc.original_filename,
                        # Phase 2: classification and uploader are required for retrieval filtering
                        "classification": doc.classification,
                        "uploaded_by_id": str(doc.uploaded_by_id) if doc.uploaded_by_id else None,
                    },
                }
            )

            chunk_records.append(
                DocumentChunk(
                    tenant_id=doc.tenant_id,
                    document_id=doc.id,
                    qdrant_point_id=point_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    page_number=chunk.page_number,
                    token_count=len(chunk.text.split()),
                )
            )

            # --- PII detection on each chunk ---
            pii_matches = detect_pii(chunk.text)
            for match in pii_matches:
                pii_records.append(
                    PiiFinding(
                        tenant_id=doc.tenant_id,
                        document_id=doc.id,
                        chunk_id=point_id,
                        pii_type=match.pii_type,
                        matched_text_hash=hash_raw_value(match.raw_value),
                        matched_text_preview=match.masked_preview,
                        page_number=chunk.page_number,
                    )
                )

        # --- Persist to Qdrant and PostgreSQL ---
        qdrant_service.upsert_chunks(points)

        db.add_all(chunk_records)
        db.add_all(pii_records)
        doc.status = "indexed"
        doc.indexed_at = datetime.now(UTC)
        db.commit()

        AuditService(db).log(
            event_type="document.indexed",
            tenant_id=doc.tenant_id,
            entity_type="document",
            entity_id=str(doc.id),
            metadata={
                "chunk_count": len(chunk_records),
                "filename": doc.original_filename,
                "classification": doc.classification,
            },
        )

        if pii_records:
            pii_summary: dict[str, int] = {}
            for p in pii_records:
                pii_summary[p.pii_type] = pii_summary.get(p.pii_type, 0) + 1

            AuditService(db).log(
                event_type="pii.detected",
                tenant_id=doc.tenant_id,
                entity_type="document",
                entity_id=str(doc.id),
                metadata={
                    "filename": doc.original_filename,
                    "pii_count": len(pii_records),
                    "pii_types": pii_summary,
                },
            )

        logger.info(
            "document_indexed",
            document_id=document_id,
            chunks=len(chunk_records),
            pii_findings=len(pii_records),
        )

    except Exception as exc:
        db.rollback()
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = "failed"
            doc.error_message = str(exc)
            db.commit()
            AuditService(db).log(
                event_type="document.index_failed",
                tenant_id=doc.tenant_id,
                entity_type="document",
                entity_id=str(doc.id),
                metadata={"error": str(exc)},
            )
        logger.error(
            "document_indexing_failed",
            document_id=document_id,
            error=str(exc),
        )
        raise self.retry(exc=exc)

    finally:
        db.close()
