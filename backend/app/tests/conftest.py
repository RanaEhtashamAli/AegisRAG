"""
Test configuration and shared fixtures.

Strategy:
- Session-scoped engine creates / drops all tables once per test run.
- Function-scoped `db` uses nested transactions (SAVEPOINT) so each test
  can call session.commit() freely and still have everything rolled back.
- Function-scoped `client` overrides the FastAPI get_db dependency so
  API integration tests share the same transaction as service tests.
"""
import os
import uuid

# Set env vars before any app module is imported
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-at-least-32-chars")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://aegisrag:aegisrag@localhost:5432/aegisrag_test",
)
os.environ["CACHE_ENABLED"] = "false"
os.environ["HYBRID_RETRIEVAL_ENABLED"] = "false"
os.environ["RERANKING_ENABLED"] = "false"
os.environ["VLLM_ENABLED"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["OTEL_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401 — registers all models with Base
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# ── Database engine (session-scoped: created once per test run) ───────────────

@pytest.fixture(scope="session")
def engine():
    e = create_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    Base.metadata.create_all(bind=e)
    yield e
    Base.metadata.drop_all(bind=e)


# ── Per-test DB session with SAVEPOINT-based rollback ─────────────────────────

@pytest.fixture
def db(engine):
    """
    Each test gets a session joined to an outer connection-level transaction.
    session.commit() releases a savepoint (no real commit to DB).
    After the test, the outer transaction rolls back — DB is pristine.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


# ── FastAPI test client (overrides get_db with the test session) ──────────────

@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ── Domain fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def tenant(db):
    from app.models.tenant import Tenant

    t = Tenant(name="Test Corp", slug=f"testcorp-{uuid.uuid4().hex[:8]}")
    db.add(t)
    db.flush()
    return t


def _make_user(db, role: str, tenant_id, *, suffix: str = ""):
    from app.models.user import User

    suffix = suffix or uuid.uuid4().hex[:6]
    u = User(
        email=f"{role}-{suffix}@test.com",
        full_name=f"{role} user",
        hashed_password=hash_password("testpass123!"),
        role=role,
        tenant_id=tenant_id,
        is_active=True,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def admin_user(db, tenant):
    return _make_user(db, "tenant_admin", tenant.id)


@pytest.fixture
def analyst_user(db, tenant):
    return _make_user(db, "analyst", tenant.id)


@pytest.fixture
def viewer_user(db, tenant):
    return _make_user(db, "viewer", tenant.id)


@pytest.fixture
def compliance_user(db, tenant):
    return _make_user(db, "compliance_officer", tenant.id)


# ── Auth token helpers ────────────────────────────────────────────────────────

@pytest.fixture
def admin_headers(admin_user):
    token = create_access_token(str(admin_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def analyst_headers(analyst_user):
    token = create_access_token(str(analyst_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def viewer_headers(viewer_user):
    token = create_access_token(str(viewer_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def compliance_headers(compliance_user):
    token = create_access_token(str(compliance_user.id))
    return {"Authorization": f"Bearer {token}"}
