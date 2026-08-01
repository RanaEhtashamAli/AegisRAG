"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Header } from "@/components/layout/Header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────

interface HealthStatus {
  db: boolean;
  redis: boolean;
  qdrant: boolean;
  ollama: boolean;
  vllm: boolean | null;
  vllm_enabled: boolean;
}

interface Alert {
  id: string;
  severity: string;
  event_type: string;
  description: string;
  resolved: boolean;
  created_at: string;
}

interface UsageTotals {
  total_queries: number;
  total_tokens: number;
  estimated_cost_usd: number;
  cache_hits: number;
  cache_misses: number;
}

interface UsageDay {
  period_date: string;
  total_queries: number;
  total_tokens: number;
  avg_latency_ms: number;
  cache_hits: number;
  cache_misses: number;
  estimated_cost_usd: number;
}

interface CacheStats {
  available: boolean;
  used_memory_human: string | null;
  connected_clients: number | null;
}

// ── Service ───────────────────────────────────────────────────────────────────

const svc = {
  health: () => api.get<HealthStatus>("/monitoring/health").then((r) => r.data),
  alerts: (resolved = false) =>
    api.get<Alert[]>(`/monitoring/alerts?resolved=${resolved}`).then((r) => r.data),
  resolveAlert: (id: string) =>
    api.patch(`/monitoring/alerts/${id}/resolve`).then((r) => r.data),
  usage: () => api.get<UsageTotals>("/monitoring/usage").then((r) => r.data),
  usageHistory: (days = 30) =>
    api.get<UsageDay[]>(`/monitoring/usage/history?days=${days}`).then((r) => r.data),
  cacheStats: () => api.get<CacheStats>("/monitoring/cache-stats").then((r) => r.data),
};

// ── Sub-components ────────────────────────────────────────────────────────────

function StatusDot({ ok }: { ok: boolean | null }) {
  if (ok === null)
    return <span className="inline-block h-2.5 w-2.5 rounded-full bg-slate-300" />;
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${ok ? "bg-green-500" : "bg-red-500"}`}
    />
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const variant =
    severity === "critical" || severity === "high"
      ? "destructive"
      : severity === "medium"
      ? "secondary"
      : "outline";
  return <Badge variant={variant}>{severity}</Badge>;
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function MonitoringPage() {
  const qc = useQueryClient();
  const [showResolved, setShowResolved] = useState(false);

  const { data: health } = useQuery({
    queryKey: ["monitoring-health"],
    queryFn: svc.health,
    refetchInterval: 30_000,
  });

  const { data: alerts = [], isLoading: alertsLoading } = useQuery({
    queryKey: ["monitoring-alerts", showResolved],
    queryFn: () => svc.alerts(showResolved),
    refetchInterval: 60_000,
  });

  const { data: usage } = useQuery({
    queryKey: ["monitoring-usage"],
    queryFn: svc.usage,
  });

  const { data: history = [] } = useQuery({
    queryKey: ["monitoring-usage-history"],
    queryFn: () => svc.usageHistory(30),
  });

  const { data: cacheStats } = useQuery({
    queryKey: ["monitoring-cache"],
    queryFn: svc.cacheStats,
    refetchInterval: 60_000,
  });

  const resolveMutation = useMutation({
    mutationFn: (id: string) => svc.resolveAlert(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["monitoring-alerts"] }),
  });

  const cacheHitRate =
    usage && usage.cache_hits + usage.cache_misses > 0
      ? ((usage.cache_hits / (usage.cache_hits + usage.cache_misses)) * 100).toFixed(1)
      : null;

  // Format date labels for chart
  const chartData = history.map((r) => ({
    ...r,
    label: r.period_date.slice(5), // "MM-DD"
  }));

  return (
    <div className="flex flex-col">
      <Header title="Monitoring" />
      <div className="p-6 space-y-6">

        {/* System health */}
        {health && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">System Health</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                {[
                  { label: "Database", ok: health.db },
                  { label: "Redis", ok: health.redis },
                  { label: "Qdrant", ok: health.qdrant },
                  { label: "Ollama", ok: health.ollama },
                  ...(health.vllm_enabled ? [{ label: "vLLM", ok: health.vllm }] : []),
                ].map(({ label, ok }) => (
                  <div key={label} className="flex items-center gap-2">
                    <StatusDot ok={ok} />
                    <span className="text-sm text-slate-700">{label}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Usage summary cards */}
        {usage && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              { label: "Total Queries", value: usage.total_queries.toLocaleString() },
              { label: "Total Tokens", value: usage.total_tokens.toLocaleString() },
              { label: "Est. Cost (USD)", value: `$${usage.estimated_cost_usd.toFixed(4)}` },
              { label: "Cache Hit Rate", value: cacheHitRate ? `${cacheHitRate}%` : "—" },
            ].map(({ label, value }) => (
              <Card key={label}>
                <CardContent className="pt-4">
                  <p className="text-xs text-slate-500">{label}</p>
                  <p className="text-xl font-bold text-slate-900">{value}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Usage history chart */}
        {chartData.length > 0 && (
          <Card>
            <CardHeader className="pb-1">
              <CardTitle className="text-base">Daily Queries — Last 30 Days</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorQueries" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="total_queries"
                    name="queries"
                    stroke="#6366f1"
                    fill="url(#colorQueries)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* Latency trend chart */}
        {chartData.length > 0 && (
          <Card>
            <CardHeader className="pb-1">
              <CardTitle className="text-base">Avg Latency (ms) — Last 30 Days</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorLatency" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="avg_latency_ms"
                    name="avg latency (ms)"
                    stroke="#f59e0b"
                    fill="url(#colorLatency)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* Cache stats */}
        {cacheStats && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Redis Cache</CardTitle>
            </CardHeader>
            <CardContent>
              {cacheStats.available ? (
                <div className="flex gap-6 text-sm text-slate-900">
                  <span>
                    Memory: <strong>{cacheStats.used_memory_human ?? "—"}</strong>
                  </span>
                  <span>
                    Connections: <strong>{cacheStats.connected_clients ?? "—"}</strong>
                  </span>
                </div>
              ) : (
                <p className="text-sm text-red-600">Redis unavailable</p>
              )}
            </CardContent>
          </Card>
        )}

        {/* Security alerts */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">
                Security Alerts
                {alerts.length > 0 && !showResolved && (
                  <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                    {alerts.length}
                  </span>
                )}
              </CardTitle>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowResolved((v) => !v)}
              >
                {showResolved ? "Show Unresolved" : "Show Resolved"}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {alertsLoading ? (
              <p className="text-sm text-slate-500">Loading…</p>
            ) : alerts.length === 0 ? (
              <p className="text-sm text-slate-500">
                {showResolved ? "No resolved alerts." : "No active alerts."}
              </p>
            ) : (
              <div className="space-y-3">
                {alerts.map((alert) => (
                  <div
                    key={alert.id}
                    className="flex items-start justify-between gap-4 rounded-lg border border-slate-200 p-3"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex items-center gap-2">
                        <SeverityBadge severity={alert.severity} />
                        <span className="text-xs text-slate-400">{alert.event_type}</span>
                      </div>
                      <p className="truncate text-sm text-slate-700">{alert.description}</p>
                      <p className="mt-1 text-xs text-slate-400">{formatDate(alert.created_at)}</p>
                    </div>
                    {!alert.resolved && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => resolveMutation.mutate(alert.id)}
                        disabled={resolveMutation.isPending}
                      >
                        Resolve
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
