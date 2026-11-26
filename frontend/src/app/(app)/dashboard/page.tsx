"use client";

import { useQuery } from "@tanstack/react-query";
import { CalendarClock, FolderKanban, Lock, Plus } from "lucide-react";
import Link from "next/link";
import { ActivityList } from "@/components/domain/activity";
import { StatusBadge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { PageHeader, Stat } from "@/components/ui/page";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate, label, P, useVocabulary } from "@/lib/hooks";
import { formatMoney, formatMoneyCompact, formatPercent } from "@/lib/money";
import { region } from "@/lib/region";
import type { CurrencyTotal, DashboardSummary } from "@/lib/types";

function MoneyTotals({ totals }: { totals: CurrencyTotal[] | null }) {
  if (totals === null) return <span className="inline-flex items-center gap-1.5 text-base text-muted"><Lock className="size-4" />Restricted</span>;
  if (totals.length === 0) return <>{formatMoneyCompact("0", "USD")}</>;
  return (
    <span className="flex flex-col">
      {totals.map((t) => (
        <span key={t.currency} title={formatMoney(t.amount, t.currency)}>
          {formatMoneyCompact(t.amount, t.currency)}
          {totals.length > 1 && <span className="ml-1 text-xs font-normal text-subtle">{t.currency}</span>}
        </span>
      ))}
    </span>
  );
}

function missingNote(totals: CurrencyTotal[] | null) {
  if (!totals) return "Requires the commercial figures permission";
  const projects = totals.reduce((n, t) => n + t.project_count, 0);
  const missing = totals.reduce((n, t) => n + t.projects_without_value, 0);
  return `${projects} project${projects === 1 ? "" : "s"}${missing ? ` · ${missing} without a contract value` : ""}`;
}

function forecastNote(f: { projects_forecast: number; projects_without_forecast: number }[]) {
  const n = f.reduce((a, x) => a + x.projects_forecast, 0);
  const m = f.reduce((a, x) => a + x.projects_without_forecast, 0);
  return `Latest approved forecasts · ${n} project${n === 1 ? "" : "s"}${m ? ` · ${m} without one` : ""}`;
}

function budgetNote(totals: CurrencyTotal[]) {
  const withBudget = totals.reduce((n, t) => n + t.project_count, 0);
  const without = totals.reduce((n, t) => n + t.projects_without_value, 0);
  return `${withBudget} live project${withBudget === 1 ? "" : "s"} budgeted${without ? ` · ${without} without an approved budget` : ""}`;
}

/** Single-series magnitude: one hue, direct count labels, no legend. */
function StatusBars({ byStatus, labels }: { byStatus: Record<string, number>; labels?: Record<string, string> }) {
  const entries = Object.entries(labels ?? {}).map(([key, text]) => [key, text, byStatus[key] ?? 0] as const).filter(([, , n]) => n > 0);
  const max = Math.max(1, ...entries.map(([, , n]) => n));
  if (entries.length === 0) return <p className="text-sm text-muted">No projects yet.</p>;
  return (
    <ul className="space-y-2.5" aria-label="Projects by status">
      {entries.map(([key, text, n]) => (
        <li key={key} className="grid grid-cols-[minmax(0,11rem)_1fr_2rem] items-center gap-3 text-sm" title={`${text}: ${n}`}>
          <span className="truncate text-muted">{text}</span>
          <span className="h-2.5 rounded-r-[4px] bg-accent" style={{ width: `${(n / max) * 100}%` }} />
          <span className="num text-right font-medium">{n}</span>
        </li>
      ))}
    </ul>
  );
}

export default function DashboardPage() {
  const { can, session } = useAuth();
  const vocab = useVocabulary();
  // Always refetch on mount: the dashboard must never show a stale snapshot after edits elsewhere.
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api<DashboardSummary>("/dashboard/summary"), refetchOnMount: "always" });

  if (q.isLoading) return <Spinner label="Loading dashboard" />;
  if (q.error || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data;
  const live = (d.by_status.preconstruction ?? 0) + (d.by_status.active ?? 0) + (d.by_status.on_hold ?? 0) + (d.by_status.closeout ?? 0);

  return (
    <>
      <PageHeader
        title="Executive Dashboard"
        description={`Portfolio overview${can(P.PROJECTS_VIEW_ALL) ? " across all projects" : " for your assigned projects"}.`}
        actions={
          can(P.PROJECTS_CREATE) && (
            <Link href="/projects/new" className="inline-flex h-10 items-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-fg hover:bg-accent-hover">
              <Plus className="size-4" /> New project
            </Link>
          )
        }
      />

      {d.total_projects === 0 ? (
        <Card>
          <EmptyState
            icon={<FolderKanban className="size-6" />}
            title={`Welcome, ${session?.user.full_name.split(" ")[0] ?? ""}`}
            description="Create your first project to start building your portfolio. Contract values you enter appear here immediately."
            action={
              can(P.PROJECTS_CREATE) && (
                <Link href="/projects/new" className="inline-flex h-10 items-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-fg">
                  <Plus className="size-4" /> Create a project
                </Link>
              )
            }
          />
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <Stat label="Projects in portfolio" value={d.total_projects} sub={`${live} live (preconstruction to closeout)`} />
            <Stat label="Live contract value" value={<MoneyTotals totals={d.live_contract_value} />} sub={missingNote(d.live_contract_value)} />
            <Stat label="Pursuit pipeline" value={<MoneyTotals totals={d.pursuit_value} />} sub={missingNote(d.pursuit_value)} />
            {d.original_budget && (
              <Stat label="Approved original budgets" value={<MoneyTotals totals={d.original_budget} />} sub={budgetNote(d.original_budget)} />
            )}
            {d.forecast && d.forecast.some((f) => f.projects_forecast > 0) && (
              <>
                <Stat label="Forecast revenue" value={<MoneyTotals totals={d.forecast.map((f) => ({ currency: f.currency, amount: f.revenue, project_count: f.projects_forecast, projects_without_value: f.projects_without_forecast }))} />} sub={forecastNote(d.forecast)} />
                <Stat label="Forecast final cost" value={<MoneyTotals totals={d.forecast.map((f) => ({ currency: f.currency, amount: f.final_cost, project_count: f.projects_forecast, projects_without_value: 0 }))} />} sub={<>Actual cost to date {d.forecast.map((f) => formatMoneyCompact(f.cost_to_date, f.currency)).join(" · ")}</>} />
                <Stat label="Forecast gross profit" value={<MoneyTotals totals={d.forecast.map((f) => ({ currency: f.currency, amount: f.gross_profit, project_count: f.projects_forecast, projects_without_value: 0 }))} />} sub={<>Margin {d.forecast.map((f) => (f.margin_percent ? `${formatPercent(f.margin_percent)}${d.forecast!.length > 1 ? ` ${f.currency}` : ""}` : "—")).join(" · ")}</>} />
              </>
            )}
            {d.forecast && !d.forecast.some((f) => f.projects_forecast > 0) && (
              <Stat label="Forecast margin" value="—" sub="No approved forecasts yet — figures appear once a project forecast is approved" />
            )}
            {d.pending_changes && (
              <Stat
                label={region() === "GB" ? "Variations awaiting decision" : "Pending change orders"}
                value={d.pending_changes.length ? <span className="flex flex-col">{d.pending_changes.map((p) => <span key={p.currency} title={formatMoney(p.amount, p.currency)}>{formatMoneyCompact(p.amount, p.currency)}</span>)}</span> : formatMoneyCompact("0", "USD")}
                sub={(() => { const n = d.pending_changes.reduce((a, p) => a + p.count, 0); const o = d.pending_changes.reduce((a, p) => a + p.overdue_count, 0); return `${n} submitted${o ? ` · ${o} overdue` : ""}`; })()}
              />
            )}
            {d.payments && (
              <Stat
                label="Outstanding payments"
                value={d.payments.length ? <span className="flex flex-col">{d.payments.map((p) => <span key={p.currency} className={p.overdue_count ? "text-danger" : undefined} title={formatMoney(p.outstanding, p.currency)}>{formatMoneyCompact(p.outstanding, p.currency)}</span>)}</span> : formatMoneyCompact("0", "USD")}
                sub={d.payments.length ? (() => { const o = d.payments.reduce((a, p) => a + p.overdue_count, 0); return `Certified, not yet paid${o ? ` · ${o} overdue` : ""} · awaiting certification ${d.payments.map((p) => formatMoneyCompact(p.awaiting_certification, p.currency)).join(" · ")}`; })() : `No ${region() === "GB" ? "valuations" : "pay applications"} submitted yet`}
              />
            )}
            {d.payments && d.payments.some((p) => p.projects_billed > 0) && (
              <Stat
                label="Over / under billing"
                value={<span className="flex flex-col">{d.payments.filter((p) => p.projects_billed > 0).map((p) => <span key={p.currency}>{p.over_billed !== "0.00" ? <span className="text-warning">{formatMoneyCompact(p.over_billed, p.currency)} over</span> : null}{p.over_billed !== "0.00" && p.under_billed !== "0.00" ? " · " : null}{p.under_billed !== "0.00" || p.over_billed === "0.00" ? <span>{formatMoneyCompact(p.under_billed, p.currency)} under</span> : null}</span>)}</span>}
                sub={`Billed to date vs earned revenue (approved forecasts) · ${d.payments.reduce((a, p) => a + p.projects_billed, 0)} project${d.payments.reduce((a, p) => a + p.projects_billed, 0) === 1 ? "" : "s"}`}
              />
            )}
            {d.committed_cost && (
              <Stat label="Committed cost" value={<MoneyTotals totals={d.committed_cost} />} sub="Executed subcontracts and purchase orders" />
            )}
            <Stat label="Completing in 90 days" value={d.upcoming_completions.length} sub="Planned completion dates" />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <CardHeader title="Portfolio by status" />
              <CardBody>
                <StatusBars byStatus={d.by_status} labels={vocab.data?.project_statuses} />
              </CardBody>
            </Card>
            <Card className="lg:col-span-2">
              <CardHeader title="Recently updated projects" actions={<Link href="/projects" className="text-sm font-medium text-accent hover:underline">View all</Link>} />
              <ul className="divide-y divide-border">
                {d.recent_projects.map((p) => (
                  <li key={p.id}>
                    <Link href={`/projects/${p.id}`} className="flex items-center gap-4 px-5 py-3 hover:bg-surface-2/60">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{p.name}</p>
                        <p className="truncate text-xs text-subtle">
                          {p.number} · {label(vocab.data?.sectors, p.sector)}
                          {p.city ? ` · ${p.city}, ${p.state_code ?? ""}` : ""}
                        </p>
                      </div>
                      <span className="num hidden text-sm sm:block">{formatMoney(p.original_contract_value, p.currency, { cents: false })}</span>
                      <StatusBadge status={p.status} label={label(vocab.data?.project_statuses, p.status)} />
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <CardHeader title="Upcoming completions" description="Next 90 days" />
              {d.upcoming_completions.length === 0 ? (
                <EmptyState icon={<CalendarClock className="size-5" />} title="Nothing due" description="No live projects have planned completion in the next 90 days." />
              ) : (
                <ul className="divide-y divide-border">
                  {d.upcoming_completions.map((p) => (
                    <li key={p.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
                      <Link href={`/projects/${p.id}`} className="min-w-0 truncate font-medium hover:underline">{p.name}</Link>
                      <span className="num shrink-0 text-muted">{formatDate(p.planned_completion_date)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card className="lg:col-span-2">
              <CardHeader title="Recent activity" description="From the audit trail" />
              <ActivityList events={d.recent_activity} showChanges={false} />
            </Card>
          </div>

          <Card>
            <CardHeader
              title="Commercial metrics"
              description="Shown only when they can be calculated from verified records — never estimated."
            />
            <CardBody>
              <p className="text-sm text-muted">{d.unavailable_reason}</p>
              <ul className="mt-3 flex flex-wrap gap-2">
                {d.unavailable_metrics.map((m) => (
                  <li key={m} className="rounded-full border border-dashed border-border-strong px-2.5 py-0.5 text-xs text-subtle">
                    {m}
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>
        </div>
      )}
    </>
  );
}
