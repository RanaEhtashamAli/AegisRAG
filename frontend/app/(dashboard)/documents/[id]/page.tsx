"use client";

import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { documentsService } from "@/services/documents";
import { useAuth } from "@/hooks/useAuth";
import { cn, classificationColor, formatDate } from "@/lib/utils";
import { RotateCcw } from "lucide-react";

const CLASSIFICATIONS = ["public", "internal", "confidential", "restricted"];

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const qc = useQueryClient();

  const { data: doc, isLoading } = useQuery({
    queryKey: ["document", id],
    queryFn: () => documentsService.get(id),
  });

  const { data: piiFindings = [] } = useQuery({
    queryKey: ["pii", id],
    queryFn: () => documentsService.piiFindings(id),
    enabled:
      !!doc && ["tenant_admin", "compliance_officer"].includes(user?.role ?? ""),
  });

  const classifyMutation = useMutation({
    mutationFn: (classification: string) =>
      documentsService.updateClassification(id, classification),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["document", id] }),
  });

  const reindexMutation = useMutation({
    mutationFn: () => documentsService.reindex(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["document", id] }),
  });

  const canClassify = ["tenant_admin", "compliance_officer"].includes(user?.role ?? "");
  const canReindex = canClassify;
  const canViewPii = canClassify;

  if (isLoading) return <div className="p-6 text-sm text-slate-500">Loading…</div>;
  if (!doc) return <div className="p-6 text-sm text-red-500">Document not found</div>;

  return (
    <div className="flex flex-col">
      <Header title={doc.original_filename} />
      <div className="p-6 space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center gap-2">
              <span className="w-32 font-medium text-slate-500">Status</span>
              <Badge
                variant={
                  doc.status === "indexed"
                    ? "default"
                    : doc.status === "failed"
                    ? "destructive"
                    : "secondary"
                }
              >
                {doc.status}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-32 font-medium text-slate-500">Classification</span>
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
                  classificationColor(doc.classification)
                )}
              >
                {doc.classification}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-32 font-medium text-slate-500">Uploaded</span>
              <span className="text-slate-900">{formatDate(doc.created_at)}</span>
            </div>
            {doc.pii_findings_count != null && (
              <div className="flex items-center gap-2">
                <span className="w-32 font-medium text-slate-500">PII Findings</span>
                <span className="text-slate-900">{doc.pii_findings_count}</span>
              </div>
            )}
          </CardContent>
        </Card>

        {(canClassify || canReindex) && (
          <Card>
            <CardHeader>
              <CardTitle>Actions</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-3">
              {canClassify && (
                <div className="flex items-center gap-2">
                  <select
                    className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900"
                    defaultValue={doc.classification}
                    onChange={(e) => classifyMutation.mutate(e.target.value)}
                  >
                    {CLASSIFICATIONS.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {canReindex && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => reindexMutation.mutate()}
                  disabled={reindexMutation.isPending}
                >
                  <RotateCcw className="mr-2 h-4 w-4" />
                  Reindex
                </Button>
              )}
            </CardContent>
          </Card>
        )}

        {canViewPii && piiFindings.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>PII Findings ({piiFindings.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-sm">
                <thead className="border-b border-slate-200">
                  <tr>
                    <th className="pb-2 text-left font-medium text-slate-500">Type</th>
                    <th className="pb-2 text-left font-medium text-slate-500">Preview</th>
                    <th className="pb-2 text-left font-medium text-slate-500">Detected</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {piiFindings.map((f) => (
                    <tr key={f.id}>
                      <td className="py-2 font-mono text-xs text-slate-700">{f.pii_type}</td>
                      <td className="py-2 font-mono text-xs text-slate-900">{f.matched_text_preview}</td>
                      <td className="py-2 text-slate-400">{formatDate(f.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
