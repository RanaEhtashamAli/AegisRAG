"""DB integration tests for UsageMetricsService."""
import json
import uuid

from app.services.usage_metrics_service import UsageMetricsService


def _record(svc, tenant_id, *, tokens=100, latency=200, model="llama3.1:8b",
            cache_hit=False, cost=0.001):
    svc.record_query(
        tenant_id=tenant_id,
        prompt_tokens=tokens,
        completion_tokens=tokens // 2,
        latency_ms=latency,
        model=model,
        cache_hit=cache_hit,
        estimated_cost_usd=cost,
    )


class TestUsageMetricsService:
    def test_record_increments_query_count(self, db, tenant):
        svc = UsageMetricsService(db)
        _record(svc, tenant.id)
        assert svc.get_totals(tenant.id)["total_queries"] == 1

    def test_record_accumulates_tokens(self, db, tenant):
        svc = UsageMetricsService(db)
        _record(svc, tenant.id, tokens=100)   # 100 + 50 = 150
        _record(svc, tenant.id, tokens=200)   # 200 + 100 = 300
        assert svc.get_totals(tenant.id)["total_tokens"] == 450

    def test_running_avg_latency(self, db, tenant):
        svc = UsageMetricsService(db)
        _record(svc, tenant.id, latency=100)
        _record(svc, tenant.id, latency=300)
        history = svc.get_history(tenant.id, days=1)
        assert len(history) == 1
        assert abs(history[0].avg_latency_ms - 200.0) < 0.5

    def test_cache_hits_and_misses(self, db, tenant):
        svc = UsageMetricsService(db)
        _record(svc, tenant.id, cache_hit=True)
        _record(svc, tenant.id, cache_hit=False)
        totals = svc.get_totals(tenant.id)
        assert totals["cache_hits"] == 1
        assert totals["cache_misses"] == 1

    def test_model_breakdown_json(self, db, tenant):
        svc = UsageMetricsService(db)
        _record(svc, tenant.id, model="llama3.1:8b")
        _record(svc, tenant.id, model="llama3.1:8b")
        _record(svc, tenant.id, model="mistral-7b")
        history = svc.get_history(tenant.id, days=1)
        breakdown = json.loads(history[0].model_breakdown_json)
        assert breakdown["llama3.1:8b"] == 2
        assert breakdown["mistral-7b"] == 1

    def test_totals_no_records_returns_zeros(self, db, tenant):
        totals = UsageMetricsService(db).get_totals(tenant.id)
        assert totals["total_queries"] == 0
        assert totals["total_tokens"] == 0
        assert totals["cache_hits"] == 0

    def test_get_history_returns_today(self, db, tenant):
        svc = UsageMetricsService(db)
        _record(svc, tenant.id)
        assert len(svc.get_history(tenant.id, days=7)) == 1

    def test_get_history_excludes_other_tenant(self, db, tenant):
        from app.models.tenant import Tenant
        other = Tenant(name="Other Corp", slug=f"other-{uuid.uuid4().hex[:8]}")
        db.add(other)
        db.flush()
        svc = UsageMetricsService(db)
        _record(svc, other.id)
        assert len(svc.get_history(tenant.id, days=7)) == 0

    def test_cost_accumulates(self, db, tenant):
        svc = UsageMetricsService(db)
        _record(svc, tenant.id, cost=0.001)
        _record(svc, tenant.id, cost=0.002)
        totals = svc.get_totals(tenant.id)
        assert abs(totals["estimated_cost_usd"] - 0.003) < 1e-9

    def test_multiple_queries_count(self, db, tenant):
        svc = UsageMetricsService(db)
        for _ in range(5):
            _record(svc, tenant.id)
        assert svc.get_totals(tenant.id)["total_queries"] == 5
