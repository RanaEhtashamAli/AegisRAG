"use client";

import { useQuery } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import { documentsService } from "@/services/documents";
import { formatDate } from "@/lib/utils";
import Link from "next/link";

export default function PiiPage() {
  const { data: documents = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: () => documentsService.list(),
  });

  const docsWithPii = documents.filter(
    (d) => d.pii_findings_count != null && d.pii_findings_count > 0
  );

  return (
    <div className="flex flex-col">
      <Header title="PII Findings" />
      <div className="p-6 space-y-4">
        <p className="text-sm text-slate-500">
          Documents with detected PII. Click a document to view detailed findings.
        </p>

        {isLoading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : docsWithPii.length === 0 ? (
          <p className="text-sm text-slate-500">No PII findings across indexed documents.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Document</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">PII Count</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Classification</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Uploaded</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {docsWithPii.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Link
                        href={`/documents/${doc.id}`}
                        className="font-medium text-slate-900 hover:underline"
                      >
                        {doc.original_filename}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-800">
                        {doc.pii_findings_count}
                      </span>
                    </td>
                    <td className="px-4 py-3 capitalize">{doc.classification}</td>
                    <td className="px-4 py-3 text-slate-400">{formatDate(doc.created_at)}</td>
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
