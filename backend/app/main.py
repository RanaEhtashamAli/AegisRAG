from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import (
    audit,
    auth,
    chat,
    compliance,
    documents,
    evals,
    health,
    monitoring,
    rag,
    tenants,
    users,
)
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(
    title=settings.APP_NAME,
    version="0.4.0",
    description="Secure Enterprise RAG Platform — Phase 4",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenTelemetry instrumentation (no-op if OTEL_ENABLED=false)
if settings.OTEL_ENABLED:
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider()
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
            )
        )
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        pass  # OTEL is optional; never block startup

prefix = settings.API_V1_PREFIX
app.include_router(health.router, prefix=prefix)
app.include_router(auth.router, prefix=prefix)
app.include_router(tenants.router, prefix=prefix)
app.include_router(documents.router, prefix=prefix)
app.include_router(rag.router, prefix=prefix)
app.include_router(audit.router, prefix=prefix)
app.include_router(users.router, prefix=prefix)
app.include_router(chat.router, prefix=prefix)
app.include_router(evals.router, prefix=prefix)
app.include_router(compliance.router, prefix=prefix)
app.include_router(monitoring.router, prefix=prefix)


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
