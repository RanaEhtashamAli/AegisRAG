"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { documentsService } from "@/services/documents";
import { useAuth } from "@/hooks/useAuth";
import { cn, classificationColor, formatDate } from "@/lib/utils";
import { Upload, Trash2, RotateCcw } from "lucide-react";
import Link from "next/link";

const CLASSIFICATIONS = ["public", "internal", "confidential", "restricted"];

export default function DocumentsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [classification, setClassification] = useState("internal");
  const [uploading, setUploading] = useState(false);

  const { data: documents = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: () => documentsService.list(),
  });

  const canUpload = ["tenant_admin", "compliance_officer", "analyst"].includes(user?.role ?? "");
  const canDelete = user?.role === "tenant_admin";
  const canReindex = ["tenant_admin", "compliance_officer"].includes(user?.role ?? "");

  const deleteMutation = useMutation({
    mutationFn: (id: string) => documentsService.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  const reindexMutation = useMutation({
    mutationFn: (id: string) => documentsService.reindex(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await documentsService.upload(file, classification);
      qc.invalidateQueries({ queryKey: ["documents"] });
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="flex flex-col">
      <Header title="Documents" />
      <div className="p-6 space-y-4">
        {canUpload && (
          <Card>
            <CardContent className="pt-4">
              <div className="flex flex-wrap items-center gap-3">
                <select
                  className="h-10 rounded-md border border-slate-200 px-3 text-sm"
                  value={classification}
                  onChange={(e) => setClassification(e.target.value)}
                >
                  {CLASSIFICATIONS.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.docx,.md,.txt"
                  className="hidden"
                  onChange={handleUpload}
                />
                <Button
                  onClick={() => fileRef.current?.click()}
                  disabled={uploading}
                  size="sm"
                >
                  <Upload className="mr-2 h-4 w-4" />
                  {uploading ? "Uploading…" : "Upload Document"}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {isLoading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : documents.length === 0 ? (
          <p className="text-sm text-slate-500">No documents yet.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Filename</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Classification</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Uploaded</th>
                  <th className="px-4 py-3 text-right font-medium text-slate-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Link
                        href={`/dashboard/documents/${doc.id}`}
                        className="font-medium text-slate-900 hover:underline"
                      >
                        {doc.original_filename}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
                          classificationColor(doc.classification)
                        )}
                      >
                        {doc.classification}
                      </span>
                    </td>
                    <td className="px-4 py-3">
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
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatDate(doc.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        {canReindex && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => reindexMutation.mutate(doc.id)}
                            title="Reindex"
                          >
                            <RotateCcw className="h-4 w-4" />
                          </Button>
                        )}
                        {canDelete && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => {
                              if (confirm("Delete this document?")) deleteMutation.mutate(doc.id);
                            }}
                            title="Delete"
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        )}
                      </div>
                    </td>
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
