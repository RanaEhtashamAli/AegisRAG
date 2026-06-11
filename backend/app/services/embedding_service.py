from sentence_transformers import SentenceTransformer

from app.core.config import settings


class EmbeddingService:
    """Singleton wrapper around a SentenceTransformer model."""

    _model: SentenceTransformer | None = None

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        return self._model

    def embed_text(self, text: str) -> list[float]:
        vector = self._get_model().encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = self._get_model().encode(texts, normalize_embeddings=True, batch_size=32)
        return [v.tolist() for v in vectors]


embedding_service = EmbeddingService()
