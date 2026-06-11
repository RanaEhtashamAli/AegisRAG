"use client";

import { useQuery } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { evalsService } from "@/services/evals";
import { formatDate } from "@/lib/utils";

function Score({ label, value }: { label: string; value: number | null }) {
  if (value == null) return null;
  const pct = (value * 100).toFixed(1);
  const color =
    value >= 0.8
      ? "text-green-700"
      : value >= 0.5
      ? "text-yellow-700"
      : "text-red-700";
  return (
    <div className="text-center">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-lg font-bold ${color}`}>{pct}%</p>
    </div>
  );
}

export default function EvalsPage() {
  const { data: runs = [], isLoading } = useQuery({
    queryKey: ["eval-runs"],
    queryFn: () => evalsService.list(),
  });

  return (
    <div className="flex flex-col">
      <Header title="Evaluations" />
      <div className="p-6 space-y-4">
        <p className="text-sm text-slate-500">
          RAGAS evaluation runs. Run{" "}
          <code className="rounded bg-slate-100 px-1 py-0.5 text-xs">
            uv run python evals/run_ragas_eval.py
          </code>{" "}
          to create a new evaluation.
        </p>

        {isLoading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : runs.length === 0 ? (
          <p className="text-sm text-slate-500">No evaluation runs yet.</p>
        ) : (
          <div className="space-y-3">
            {runs.map((run) => (
              <Card key={run.id}>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{run.run_name}</CardTitle>
                    <Badge
                      variant={
                        run.status === "completed"
                          ? "default"
                          : run.status === "failed"
                          ? "destructive"
                          : "secondary"
                      }
                    >
                      {run.status}
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-400">{formatDate(run.created_at)}</p>
                </CardHeader>
                {run.status === "completed" && (
                  <CardContent>
                    <div className="flex flex-wrap gap-6">
                      <Score label="Faithfulness" value={run.faithfulness} />
                      <Score label="Answer Relevancy" value={run.answer_relevancy} />
                      <Score label="Context Recall" value={run.context_recall} />
                      <Score label="Context Precision" value={run.context_precision} />
                    </div>
                    <p className="mt-3 text-xs text-slate-400">
                      {run.completed_questions}/{run.total_questions} questions completed
                      {run.completed_at && ` · finished ${formatDate(run.completed_at)}`}
                    </p>
                  </CardContent>
                )}
                {run.error_message && (
                  <CardContent>
                    <p className="text-sm text-red-600">{run.error_message}</p>
                  </CardContent>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
