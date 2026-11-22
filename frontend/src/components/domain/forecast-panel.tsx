"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, LineChart, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ConfirmButton, Dialog } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Stat } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { formatDate, P } from "@/lib/hooks";
import { formatMoney, formatPercent } from "@/lib/money";
import type { ForecastDetail, ForecastLineItem, ForecastSummaryItem, Project } from "@/lib/types";

const msg = (err: unknown) => (err instanceof ApiError ? err.message : "Something went wrong");
const METHODS: Record<string, string> = {
  greater_of: "Greater of budget or commitments remaining",
  budget_remaining: "Budget remaining",
  committed_remaining: "Commitments remaining",
  manual: "Manual",
};
const monthLabel = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: "long", year: "numeric" });

function LineEditor({ f, line, onSaved, onClose }: { f: ForecastDetail; line: ForecastLineItem | null; onSaved: (x: ForecastDetail) => void; onClose: () => void }) {
  const [method, setMethod] = useState("greater_of");
  const [manual, setManual] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (line) { setMethod(line.method); setManual(line.manual_ctc ?? ""); setNotes(line.notes ?? ""); setError(null); }
  }, [line]);
  const save = async () => {
    setError(null);
    const m = manual.replace(/[,\s]/g, "");
    if (method === "manual" && !/^\d+(\.\d{1,2})?$/.test(m)) return setError("Enter the cost to complete (zero or more, up to 2 decimals)");
    setBusy(true);
    try {
      onSaved(await api<ForecastDetail>(`/forecasts/${f.id}/lines/${line!.id}`, { method: "PUT", body: { method, manual_ctc: method === "manual" ? m : null, notes: notes.trim() || null } }));
      onClose();
    } catch (err) {
      setError(msg(err));
    } finally {
      setBusy(false);
    }
  };
  const c = f.currency;
  return (
    <Dialog open={!!line} onOpenChange={(o) => !o && onClose()} title={`Cost to complete — ${line?.cost_code ? `${line.cost_code.code} ${line.cost_code.title}` : "Unassigned"}`}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={save}>Save</Button></>}>
      {line && (
        <div className="space-y-4">
          {error && <Alert tone="danger">{error}</Alert>}
          <dl className="num grid grid-cols-3 gap-3 rounded-md bg-surface-2 p-3 text-sm">
            <div><dt className="text-xs text-subtle">Revised budget</dt><dd>{formatMoney(line.revised_budget, c)}</dd></div>
            <div><dt className="text-xs text-subtle">Committed</dt><dd>{formatMoney(line.committed, c)}</dd></div>
            <div><dt className="text-xs text-subtle">Cost to date</dt><dd>{formatMoney(line.cost_to_date, c)}</dd></div>
          </dl>
          <Field label="Method">{(p) => <Select {...p} value={method} onChange={(e) => setMethod(e.target.value)}>{Object.entries(METHODS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</Select>}</Field>
          {method === "manual" && <Field label={`Cost to complete (${c})`} required>{(p) => <Input {...p} value={manual} onChange={(e) => setManual(e.target.value)} inputMode="decimal" className="num" />}</Field>}
          <Field label="Notes" hint="Explain judgement calls for reviewers">{(p) => <Textarea {...p} value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />}</Field>
        </div>
      )}
    </Dialog>
  );
}

function ForecastView({ id, onDeleted }: { id: string; onDeleted: () => void }) {
  const qc = useQueryClient();
  const { notify } = useToast();
  const [editing, setEditing] = useState<ForecastLineItem | null>(null);
  const [adj, setAdj] = useState("");
  const [adjNote, setAdjNote] = useState("");
  const q = useQuery({ queryKey: ["forecast", id], queryFn: () => api<ForecastDetail>(`/forecasts/${id}`) });
  useEffect(() => { if (q.data) { setAdj(q.data.revenue_adjustment === "0.00" ? "" : q.data.revenue_adjustment); setAdjNote(q.data.revenue_adjustment_note ?? ""); } }, [q.data?.id, q.data?.version]);
  const apply = (f: ForecastDetail) => { qc.setQueryData(["forecast", id], f); void qc.invalidateQueries({ queryKey: ["forecasts", f.project_id] }); void qc.invalidateQueries({ queryKey: ["dashboard"] }); };
  const saveAdj = useMutation({
    mutationFn: () => api<ForecastDetail>(`/forecasts/${id}`, { method: "PATCH", body: { version: q.data!.version, revenue_adjustment: adj.replace(/[,\s]/g, "") || "0.00", revenue_adjustment_note: adjNote.trim() || null } }),
    onSuccess: (f) => { apply(f); notify("Revenue adjustment saved"); },
    onError: (err) => notify(msg(err), "danger"),
  });
  const approve = useMutation({ mutationFn: () => api<ForecastDetail>(`/forecasts/${id}/approve`, { method: "POST", body: { version: q.data!.version } }), onSuccess: (f) => { apply(f); notify("Forecast approved"); }, onError: (err) => notify(msg(err), "danger") });
  const remove = useMutation({ mutationFn: () => api(`/forecasts/${id}`, { method: "DELETE" }), onSuccess: () => { notify("Draft forecast deleted"); onDeleted(); }, onError: (err) => notify(msg(err), "danger") });
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorState error={q.error} />;
  const f = q.data;
  const c = f.currency;
  const neg = (v: string) => v.startsWith("-");
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-lg font-semibold">{monthLabel(f.period)}</h3>
        <Badge tone={f.status === "approved" ? "success" : "neutral"}>{f.status === "approved" ? `Approved ${formatDate(f.approved_at)}` : "Draft — live figures"}</Badge>
        <span className="text-xs text-subtle">Cost to date as at {formatDate(f.period_end)}</span>
        <div className="flex-1" />
        {f.is_editable && <ConfirmButton size="md" label={<><Trash2 className="size-4" />Delete draft</>} title="Delete this draft forecast?" description="Approved forecasts cannot be deleted." confirmLabel="Delete" onConfirm={() => remove.mutateAsync()} />}
        {f.can_approve && <ConfirmButton size="md" buttonVariant="secondary" variant="primary" label={<><CheckCircle2 className="size-4" />Approve forecast</>} title="Approve this forecast?" description="Locks a snapshot of every figure for this period. Dashboards use approved forecasts only." confirmLabel="Approve" onConfirm={() => approve.mutateAsync()} />}
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Forecast revenue" value={formatMoney(f.revenue, c)} sub={`Revised contract ${formatMoney(f.revised_contract, c)}${f.revenue_adjustment !== "0.00" ? ` ${neg(f.revenue_adjustment) ? "−" : "+"} adjustment ${formatMoney(f.revenue_adjustment.replace("-", ""), c)}` : ""}`} />
        <Stat label="Forecast final cost" value={formatMoney(f.final_cost, c)} sub={`Cost to date ${formatMoney(f.cost_to_date, c)} + to complete ${formatMoney(f.cost_to_complete, c)}`} />
        <Stat label="Forecast gross profit" value={<span className={cn(neg(f.gross_profit) && "text-danger")}>{formatMoney(f.gross_profit, c)}</span>} sub={f.margin_percent ? `Margin ${formatPercent(f.margin_percent)}` : "Margin undefined (no revenue)"} />
        <Stat label="Percent complete" value={f.percent_complete ? formatPercent(f.percent_complete) : "—"} sub={f.earned_revenue ? `Earned revenue ${formatMoney(f.earned_revenue, c)} (cost-to-cost)` : undefined} />
      </div>
      {f.is_editable && (
        <Card>
          <CardHeader title="Revenue adjustment" description="Probable changes not yet approved (positive) or expected deductions (negative). Explain the basis." />
          <CardBody className="grid gap-4 sm:grid-cols-[12rem_1fr_auto] sm:items-end">
            <Field label={`Amount (${c})`}>{(p) => <Input {...p} value={adj} onChange={(e) => setAdj(e.target.value)} inputMode="decimal" className="num" placeholder="0.00" />}</Field>
            <Field label="Basis">{(p) => <Input {...p} value={adjNote} onChange={(e) => setAdjNote(e.target.value)} maxLength={2000} placeholder="Probable approval of CO-004 and CO-006" />}</Field>
            <Button variant="secondary" loading={saveAdj.isPending} onClick={() => { if (adj && !/^-?\d+(\.\d{1,2})?$/.test(adj.replace(/[,\s]/g, ""))) return notify("Adjustment: up to 2 decimals", "danger"); saveAdj.mutate(); }}>Save</Button>
          </CardBody>
        </Card>
      )}
      {f.status === "approved" && f.revenue_adjustment !== "0.00" && <Alert tone="info" title={`Revenue adjustment ${formatMoney(f.revenue_adjustment, c)}`}>{f.revenue_adjustment_note}</Alert>}
      <Card>
        <CardHeader title="By cost code" description={f.is_editable ? "Select a row to change how its cost to complete is forecast." : "Approved snapshot."} />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">Forecast by cost code</caption>
            <thead><tr className="border-b border-border bg-surface-2/60 text-left text-xs font-semibold uppercase tracking-wide text-subtle">
              <th className="px-4 py-2.5">Code</th><th className="px-4 py-2.5">Method</th><th className="px-4 py-2.5 text-right">Revised budget</th><th className="px-4 py-2.5 text-right">Committed</th><th className="px-4 py-2.5 text-right">Cost to date</th><th className="px-4 py-2.5 text-right">To complete</th><th className="px-4 py-2.5 text-right">Final cost</th><th className="px-4 py-2.5 text-right">Variance</th>
            </tr></thead>
            <tbody className="num">
              {f.lines.map((l) => (
                <tr key={l.id} className={cn("border-b border-border", f.is_editable && "cursor-pointer hover:bg-surface-2/70")} onClick={f.is_editable ? () => setEditing(l) : undefined}>
                  <td className="px-4 py-2.5 font-sans">{l.cost_code ? <><span className="font-mono text-xs">{l.cost_code.code}</span> {l.cost_code.title}</> : "Unassigned"}</td>
                  <td className="px-4 py-2.5 font-sans text-xs text-muted">{METHODS[l.method]}{l.notes && <span className="block text-subtle">{l.notes}</span>}</td>
                  <td className="px-4 py-2.5 text-right">{formatMoney(l.revised_budget, c)}</td>
                  <td className="px-4 py-2.5 text-right">{formatMoney(l.committed, c)}</td>
                  <td className="px-4 py-2.5 text-right">{formatMoney(l.cost_to_date, c)}</td>
                  <td className="px-4 py-2.5 text-right">{formatMoney(l.cost_to_complete, c)}</td>
                  <td className="px-4 py-2.5 text-right font-medium">{formatMoney(l.final_cost, c)}</td>
                  <td className={cn("px-4 py-2.5 text-right", neg(l.variance) && "text-danger")}>{formatMoney(l.variance, c)}</td>
                </tr>
              ))}
              <tr className="border-t-2 border-border-strong font-semibold">
                <td className="px-4 py-3 font-sans" colSpan={2}>Total</td>
                <td className="px-4 py-3 text-right">{formatMoney(f.revised_budget, c)}</td><td className="px-4 py-3 text-right">{formatMoney(f.committed, c)}</td>
                <td className="px-4 py-3 text-right">{formatMoney(f.cost_to_date, c)}</td><td className="px-4 py-3 text-right">{formatMoney(f.cost_to_complete, c)}</td>
                <td className="px-4 py-3 text-right">{formatMoney(f.final_cost, c)}</td><td className={cn("px-4 py-3 text-right", neg(f.variance) && "text-danger")}>{formatMoney(f.variance, c)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
      <LineEditor f={f} line={editing} onSaved={(x) => { apply(x); notify("Line updated"); }} onClose={() => setEditing(null)} />
      <p className="text-xs text-subtle">Final cost = cost to date + cost to complete. Margin = gross profit ÷ revenue. Percent complete = cost to date ÷ final cost. Commitments never add to cost directly — they set a floor on the forecast.</p>
    </div>
  );
}

export function ForecastPanel({ project }: { project: Project }) {
  const { can } = useAuth();
  const { notify } = useToast();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const thisMonth = new Date().toISOString().slice(0, 7);
  const [period, setPeriod] = useState(thisMonth);
  const list = useQuery({ queryKey: ["forecasts", project.id], queryFn: () => api<ForecastSummaryItem[]>(`/projects/${project.id}/forecasts`) });
  useEffect(() => { if (!selected && list.data?.[0]) setSelected(list.data[0].id); }, [list.data, selected]);
  const create = useMutation({
    mutationFn: () => api<ForecastDetail>(`/projects/${project.id}/forecasts`, { method: "POST", body: { period: `${period}-01` } }),
    onSuccess: async (f) => { await qc.invalidateQueries({ queryKey: ["forecasts", project.id] }); setSelected(f.id); setOpen(false); notify("Draft forecast started"); },
    onError: (err) => notify(msg(err), "danger"),
  });
  if (list.isLoading) return <Spinner />;
  if (list.error) return <ErrorState error={list.error} />;
  const items = list.data ?? [];
  const c = project.currency;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        {items.length > 0 && (
          <Select className="w-64" aria-label="Forecast period" value={selected ?? ""} onChange={(e) => setSelected(e.target.value)}>
            {items.map((f) => <option key={f.id} value={f.id}>{monthLabel(f.period)} — {f.status}{f.margin_percent ? ` (${formatPercent(f.margin_percent)})` : ""}</option>)}
          </Select>
        )}
        <div className="flex-1" />
        {can(P.FORECASTS_EDIT) && !project.archived_at && <Button onClick={() => { setPeriod(thisMonth); setOpen(true); }}><Plus className="size-4" />New forecast</Button>}
      </div>
      {items.length === 0 ? (
        <Card><EmptyState icon={<LineChart className="size-6" />} title="No forecasts yet" description="Start a monthly forecast. It is calculated live from the budget, commitments, changes and cost ledger until approved." /></Card>
      ) : selected ? <ForecastView key={selected} id={selected} onDeleted={() => { setSelected(null); void qc.invalidateQueries({ queryKey: ["forecasts", project.id] }); }} /> : null}
      {items.filter((f) => f.status === "approved").length > 1 && (
        <Card>
          <CardHeader title="Forecast history" description="Approved snapshots" />
          <div className="overflow-x-auto">
            <table className="w-full text-sm"><thead><tr className="border-b border-border text-left text-xs uppercase text-subtle"><th className="px-4 py-2">Period</th><th className="px-4 py-2 text-right">Revenue</th><th className="px-4 py-2 text-right">Final cost</th><th className="px-4 py-2 text-right">Gross profit</th><th className="px-4 py-2 text-right">Margin</th></tr></thead>
              <tbody className="num">{items.filter((f) => f.status === "approved").map((f) => <tr key={f.id} className="border-b border-border"><td className="px-4 py-2 font-sans">{monthLabel(f.period)}</td><td className="px-4 py-2 text-right">{formatMoney(f.revenue, c)}</td><td className="px-4 py-2 text-right">{formatMoney(f.final_cost, c)}</td><td className="px-4 py-2 text-right">{formatMoney(f.gross_profit, c)}</td><td className="px-4 py-2 text-right">{formatPercent(f.margin_percent)}</td></tr>)}</tbody>
            </table>
          </div>
        </Card>
      )}
      <Dialog open={open} onOpenChange={setOpen} title="New forecast" description="Methods carry over from the last approved forecast."
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button loading={create.isPending} onClick={() => create.mutate()}>Start draft</Button></>}>
        <Field label="Period" required>{(p) => <Input {...p} type="month" max={thisMonth} value={period} onChange={(e) => setPeriod(e.target.value)} />}</Field>
      </Dialog>
    </div>
  );
}
