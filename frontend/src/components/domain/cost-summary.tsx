"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardHeader } from "@/components/ui/card";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney } from "@/lib/money";
import type { CommercialSummary, Project } from "@/lib/types";

export function CostSummary({ project }: { project: Project }) {
  const q = useQuery({ queryKey: ["project", project.id, "summary"], queryFn: () => api<CommercialSummary>(`/projects/${project.id}/commercial-summary`) });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  const s = q.data!;
  const c = s.currency;
  const neg = (v: string) => v.startsWith("-");
  return (
    <div className="space-y-4">
      {!s.has_approved_budget && <Alert tone="info" title="No approved original budget yet">Budget figures appear once the original budget is approved on the Budget tab.</Alert>}
      {s.warnings.map((w) => <Alert key={w} tone="warning">{w}</Alert>)}
      <Card>
        <CardHeader title="Budget vs committed by cost code" description="Revised budget = original + approved budget changes. Committed = executed subcontracts and POs plus approved changes. Pending = drafts and unapproved changes. Uncommitted = revised budget − committed." />
        {s.rows.length === 0 ? <EmptyState title="Nothing to summarize yet" description="Approve a budget and add subcontracts or purchase orders." /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Budget vs committed by cost code</caption>
              <thead>
                <tr className="border-b border-border bg-surface-2/60 text-left text-xs font-semibold uppercase tracking-wide text-subtle">
                  <th className="px-4 py-2.5">Code</th><th className="px-4 py-2.5">Description</th>
                  <th className="px-4 py-2.5 text-right">Budget</th><th className="px-4 py-2.5 text-right">Changes</th>
                  <th className="px-4 py-2.5 text-right">Revised budget</th><th className="px-4 py-2.5 text-right">Committed</th>
                  <th className="px-4 py-2.5 text-right">Uncommitted</th><th className="px-4 py-2.5 text-right">Pending</th>
                  <th className="px-4 py-2.5 text-right">Cost to date</th>
                  <th className="px-4 py-2.5 text-right">Contract value</th>
                </tr>
              </thead>
              <tbody className="num">
                {[...s.rows, s.totals].map((r, i) => {
                  const total = i === s.rows.length;
                  return (
                    <tr key={r.cost_code_id ?? `${r.title}-${i}`} className={cn("border-b border-border", total && "border-t-2 border-border-strong font-semibold")}>
                      <td className="px-4 py-2.5 font-mono text-xs">{total ? "" : r.code ?? "—"}</td>
                      <td className="px-4 py-2.5 font-sans">{r.title}</td>
                      <td className="px-4 py-2.5 text-right text-muted">{formatMoney(r.budget, c)}</td>
                      <td className="px-4 py-2.5 text-right text-muted">{formatMoney(r.budget_changes, c)}</td>
                      <td className="px-4 py-2.5 text-right">{formatMoney(r.revised_budget, c)}</td>
                      <td className="px-4 py-2.5 text-right">{formatMoney(r.committed, c)}</td>
                      <td className={cn("px-4 py-2.5 text-right", neg(r.uncommitted) && "text-danger")}>{formatMoney(r.uncommitted, c)}</td>
                      <td className="px-4 py-2.5 text-right text-muted">{formatMoney(r.pending, c)}</td>
                      <td className="px-4 py-2.5 text-right">{formatMoney(r.cost_to_date, c)}</td>
                      <td className="px-4 py-2.5 text-right text-muted">{formatMoney(r.contract_value, c)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
