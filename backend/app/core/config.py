from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "AegisRAG"
    APP_ENV: str = "local"
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str = "change-me-in-production-very-secret-key-at-least-32-chars"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "aegisrag"
    POSTGRES_USER: str = "aegisrag"
    POSTGRES_PASSWORD: str = "aegisrag"
    DATABASE_URL: str = ""

    REDIS_URL: str = "redis://localhost:6379/0"

    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "aegisrag_chunks"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"

    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    UPLOAD_DIR: str = "/tmp/aegisrag_uploads"

    # Langfuse observability (optional — no-op if keys not set)
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_HOST: str = "http://localhost:3000"

    # Phase 3 retrieval settings
    HYBRID_RETRIEVAL_ENABLED: bool = True
    RERANKING_ENABLED: bool = False
    RERANKING_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    BM25_TOP_K_MULTIPLIER: int = 3

    # Chat sessions
    CHAT_SESSION_MAX_MESSAGES: int = 50

    # ── Phase 4 ────────────────────────────────────────────────────────────────

    # vLLM inference
    VLLM_BASE_URL: str = "http://localhost:8080"
    VLLM_MODEL: str = "mistralai/Mistral-7B-Instruct-v0.3"
    VLLM_ENABLED: bool = False
    VLLM_TIMEOUT: int = 120
    VLLM_MAX_RETRIES: int = 3

    # Model routing
    COMPLEX_QUERY_TOKEN_THRESHOLD: int = 500  # tokens above which strong model is used

    # Redis caching
    CACHE_ENABLED: bool = True
    EMBEDDING_CACHE_TTL: int = 3600   # 1 hour
    RETRIEVAL_CACHE_TTL: int = 300    # 5 minutes
    RESPONSE_CACHE_TTL: int = 60      # 1 minute

    # Encryption (Fernet key, base64-encoded — leave empty to disable at-rest encryption)
    FIELD_ENCRYPTION_KEY: str = ""

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    LOGIN_RATE_LIMIT: str = "10/minute"
    REGISTER_RATE_LIMIT: str = "10/minute"
    TENANT_CREATE_RATE_LIMIT: str = "10/minute"

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_UPLOAD_MIMETYPES: str = (
        "application/pdf,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "text/markdown,text/plain"
    )

    # OpenTelemetry
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "aegisrag-backend"

    # Security alert thresholds
    FAILED_LOGIN_ALERT_THRESHOLD: int = 5   # failures within window
    FAILED_LOGIN_WINDOW_MINUTES: int = 15
    SUSPICIOUS_QUERY_RATE_THRESHOLD: int = 100  # queries per hour per tenant

    @model_validator(mode="after")
    def assemble_database_url(self) -> "Settings":
        if not self.DATABASE_URL:
            object.__setattr__(
                self,
                "DATABASE_URL",
                (
                    f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                    f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
                ),
            )
        return self


settings = Settings()
