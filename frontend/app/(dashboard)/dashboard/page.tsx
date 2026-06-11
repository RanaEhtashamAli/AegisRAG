"use client";

import { useQuery } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { documentsService } from "@/services/documents";
import { auditService } from "@/services/audit";
import { useAuth } from "@/hooks/useAuth";
import { FileText, Activity, Clock } from "lucide-react";
import { formatDate } from "@/lib/utils";

export default function DashboardPage() {
  const { user } = useAuth();

  const { data: documents = [] } = useQuery({
    queryKey: ["documents"],
    queryFn: () => documentsService.list(),
  });

  const { data: auditEvents = [] } = useQuery({
    queryKey: ["audit", "recent"],
    queryFn: () => auditService.list({ limit: 5 }),
    enabled: user?.role === "tenant_admin" || user?.role === "compliance_officer",
  });

  const indexed = documents.filter((d) => d.status === "indexed").length;

  return (
    <div className="flex flex-col">
      <Header title="Dashboard" />
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-slate-500">Total Documents</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-slate-400" />
                <span className="text-2xl font-bold">{documents.length}</span>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-slate-500">Indexed</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <Activity className="h-5 w-5 text-green-500" />
                <span className="text-2xl font-bold">{indexed}</span>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-slate-500">Your Role</CardTitle>
            </CardHeader>
            <CardContent>
              <span className="text-2xl font-bold capitalize">
                {user?.role?.replace("_", " ") ?? "—"}
              </span>
            </CardContent>
          </Card>
        </div>

        {auditEvents.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Clock className="h-4 w-4" />
                Recent Activity
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {auditEvents.map((e) => (
                  <li key={e.id} className="flex items-center justify-between text-sm">
                    <span className="font-mono text-slate-700">{e.event_type}</span>
                    <span className="text-slate-400">{formatDate(e.created_at)}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
