from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchAny,
    MatchValue,
    PointStruct,
    ScoredPoint,
    VectorParams,
)

from app.core.config import settings
from app.core.logging import logger

# Must match the output dimension of EMBEDDING_MODEL (all-MiniLM-L6-v2 → 384)
VECTOR_SIZE = 384


class QdrantService:
    """Singleton Qdrant client.

    All searches enforce tenant_id AND classification filters — cross-tenant
    and cross-classification leakage is structurally impossible.
    """

    _client: QdrantClient | None = None

    def _get_client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        return self._client

    def ensure_collection(self) -> None:
        client = self._get_client()
        existing = {c.name for c in client.get_collections().collections}
        if settings.QDRANT_COLLECTION not in existing:
            client.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info("qdrant_collection_created", name=settings.QDRANT_COLLECTION)

    def upsert_chunks(self, points: list[dict]) -> None:
        """Upsert a list of {id, vector, payload} dicts."""
        client = self._get_client()
        structs = [
            PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"]) for p in points
        ]
        client.upsert(collection_name=settings.QDRANT_COLLECTION, points=structs)

    def search(
        self,
        query_vector: list[float],
        tenant_id: str,
        allowed_classifications: list[str],
        top_k: int = 5,
    ) -> list[ScoredPoint]:
        """Mandatory dual filter: tenant_id + classification allow-list."""
        client = self._get_client()
        response = client.query_points(
            collection_name=settings.QDRANT_COLLECTION,
            query=query_vector,
            query_filter=Filter(
                must=[
                    FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
                    FieldCondition(
                        key="classification",
                        match=MatchAny(any=allowed_classifications),
                    ),
                ]
            ),
            limit=top_k,
            with_payload=True,
        )
        return response.points

    def delete_by_document(self, document_id: str, tenant_id: str) -> None:
        """Delete all Qdrant points for a document, scoped to the owning tenant."""
        client = self._get_client()
        client.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
                        FieldCondition(
                            key="document_id", match=MatchValue(value=document_id)
                        ),
                    ]
                )
            ),
        )
        logger.info("qdrant_points_deleted", document_id=document_id, tenant_id=tenant_id)


qdrant_service = QdrantService()
