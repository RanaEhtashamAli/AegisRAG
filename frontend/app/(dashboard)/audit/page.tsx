"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { auditService } from "@/services/audit";
import { formatDate } from "@/lib/utils";

export default function AuditPage() {
  const [eventType, setEventType] = useState("");
  const [limit, setLimit] = useState(50);

  const { data: events = [], isLoading, refetch } = useQuery({
    queryKey: ["audit", eventType, limit],
    queryFn: () =>
      auditService.list({ event_type: eventType || undefined, limit }),
  });

  return (
    <div className="flex flex-col">
      <Header title="Audit Log" />
      <div className="p-6 space-y-4">
        <div className="flex flex-wrap gap-2">
          <Input
            className="w-48"
            placeholder="Filter by event type…"
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
          />
          <select
            className="h-10 rounded-md border border-slate-200 px-3 text-sm"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          >
            {[20, 50, 100, 200].map((n) => (
              <option key={n} value={n}>
                {n} rows
              </option>
            ))}
          </select>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            Refresh
          </Button>
        </div>

        {isLoading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : (
          <div className="overflow-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Event</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Entity</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">IP</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {events.map((e) => (
                  <tr key={e.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2 font-mono text-xs text-slate-700">{e.event_type}</td>
                    <td className="px-4 py-2 text-slate-500">
                      {e.entity_type ?? "—"} {e.entity_id ? `(${e.entity_id.slice(0, 8)}…)` : ""}
                    </td>
                    <td className="px-4 py-2 text-slate-500">{e.ip_address ?? "—"}</td>
                    <td className="px-4 py-2 text-slate-400">{formatDate(e.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
