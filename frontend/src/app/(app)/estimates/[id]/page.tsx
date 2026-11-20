"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Copy, GitCompare, Lock, Percent, Plus, Send } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { EstimateLineDialog } from "@/components/domain/estimate-line-dialog";
import { ESTIMATE_TYPES } from "@/components/domain/estimates-list";
import { MarkupsDialog } from "@/components/domain/markups-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ConfirmButton, Dialog } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Select } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { formatDate, formatDecimal, P } from "@/lib/hooks";
import { formatMoney } from "@/lib/money";
import { terms } from "@/lib/region";
import type { CostCode, Estimate, EstimateCompare, EstimateLine, EstimateVersion } from "@/lib/types";

const msg = (err: unknown) => (err instanceof ApiError ? err.message : "Something went wrong");
const STATUS_TONE = { draft: "neutral", issued: "accent", approved: "success" } as const;

function CompareDialog({ estimate, open, onOpenChange }: { estimate: Estimate; open: boolean; onOpenChange: (o: boolean) => void }) {
  const numbers = estimate.versions.map((v) => v.version_number);
  const [from, setFrom] = useState(numbers[Math.max(0, numbers.length - 2)] ?? 1);
  const [to, setTo] = useState(numbers[numbers.length - 1] ?? 1);
  const q = useQuery({
    queryKey: ["estimate-compare", estimate.id, from, to],
    queryFn: () => api<EstimateCompare>(`/estimates/${estimate.id}/compare`, { query: { from_version: from, to_version: to } }),
    enabled: open && from !== to,
  });
  const c = estimate.currency;
  return (
    <Dialog open={open} onOpenChange={onOpenChange} wide title="Compare versions" description="Base scope by cost code, plus markups.">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <Select className="w-32" aria-label="From version" value={from} onChange={(e) => setFrom(Number(e.target.value))}>{numbers.map((n) => <option key={n} value={n}>v{n}</option>)}</Select>
          <span>→</span>
          <Select className="w-32" aria-label="To version" value={to} onChange={(e) => setTo(Number(e.target.value))}>{numbers.map((n) => <option key={n} value={n}>v{n}</option>)}</Select>
        </div>
        {from === to ? <p className="text-sm text-muted">Choose two different versions.</p> : q.isLoading ? <Spinner /> : q.data && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-border text-left text-xs uppercase text-subtle"><th className="py-2">Code</th><th>Description</th><th className="text-right">v{from}</th><th className="text-right">v{to}</th><th className="text-right">Change</th></tr></thead>
              <tbody className="num">
                {q.data.rows.map((r, i) => (
                  <tr key={i} className="border-b border-border">
                    <td className="py-2 font-mono">{r.cost_code ?? "—"}</td><td>{r.title}</td>
                    <td className="text-right">{formatMoney(r.from_amount, c)}</td><td className="text-right">{formatMoney(r.to_amount, c)}</td>
                    <td className={cn("text-right", r.change.startsWith("-") ? "text-success" : r.change !== "0.00" && "text-danger")}>{formatMoney(r.change, c)}</td>
                  </tr>
                ))}
                <tr className="font-semibold"><td className="py-2" colSpan={2}>Total</td><td className="text-right">{formatMoney(q.data.from_total, c)}</td><td className="text-right">{formatMoney(q.data.to_total, c)}</td><td className="text-right">{formatMoney(q.data.change, c)}</td></tr>
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Dialog>
  );
}

export default function EstimatePage() {
  const { id } = useParams<{ id: string }>();
  const { can } = useAuth();
  const { notify } = useToast();
  const qc = useQueryClient();
  const t = terms();
  const [versionNo, setVersionNo] = useState<number | null>(null);
  const [lineOpen, setLineOpen] = useState(false);
  const [editing, setEditing] = useState<EstimateLine | null>(null);
  const [markupsOpen, setMarkupsOpen] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);

  const est = useQuery({ queryKey: ["estimate", id], queryFn: () => api<Estimate>(`/estimates/${id}`) });
  useEffect(() => {
    if (est.data && versionNo === null) setVersionNo(est.data.current_version_number);
  }, [est.data, versionNo]);
  const ver = useQuery({
    queryKey: ["estimate", id, "version", versionNo],
    queryFn: () => api<EstimateVersion>(`/estimates/${id}/versions/${versionNo}`),
    enabled: versionNo !== null,
  });
  const codes = useQuery({
    queryKey: ["cost-codes", est.data?.cost_code_set_id, false],
    queryFn: () => api<CostCode[]>(`/cost-code-sets/${est.data!.cost_code_set_id}/codes`),
    enabled: !!est.data?.cost_code_set_id,
  });

  const base = `/estimates/${id}/versions/${versionNo}`;
  const applyVersion = (v: EstimateVersion) => {
    qc.setQueryData(["estimate", id, "version", v.version_number], v);
    void qc.invalidateQueries({ queryKey: ["estimate", id], exact: true });
    void qc.invalidateQueries({ queryKey: ["estimates"] });
  };
  const action = useMutation({
    mutationFn: (path: string) => api<EstimateVersion>(path, { method: "POST" }),
    onSuccess: (v) => {
      applyVersion(v);
      setVersionNo(v.version_number);
      notify(v.status === "draft" ? `Version ${v.version_number} created` : `Version ${v.version_number} ${v.status}`);
    },
    onError: (err) => notify(msg(err), "danger"),
  });

  if (est.isLoading) return <Spinner label="Loading estimate" />;
  if (est.error instanceof ApiError && [403, 404].includes(est.error.status)) {
    return <EmptyState title="Estimate not available" description="It may not exist, or you may not have access to it." action={<Link href="/estimating" className="text-accent hover:underline">Back to estimating</Link>} />;
  }
  if (est.error || !est.data) return <ErrorState error={est.error} />;
  const e = est.data;
  const v = ver.data;
  const c = e.currency;
  const isLatest = versionNo === e.current_version_number;

  return (
    <>
      <PageHeader
        breadcrumb={<><Link href="/estimating" className="hover:underline">Estimating</Link> / <Link href={`/projects/${e.project_id}`} className="hover:underline">{e.project_number} {e.project_name}</Link></>}
        title={e.name}
        description={`${ESTIMATE_TYPES[e.estimate_type] ?? e.estimate_type} · ${c}${v?.price_base_date ? ` · price base ${formatDate(v.price_base_date)}` : ""}`}
        actions={
          <>
            <Select className="w-52" aria-label="Version" value={versionNo ?? ""} onChange={(ev) => setVersionNo(Number(ev.target.value))}>
              {[...e.versions].reverse().map((x) => <option key={x.version_number} value={x.version_number}>Version {x.version_number} — {x.status}{x.label ? ` (${x.label})` : ""}</option>)}
            </Select>
            {e.versions.length > 1 && <Button variant="secondary" onClick={() => setCompareOpen(true)}><GitCompare className="size-4" />Compare</Button>}
          </>
        }
      />

      {!v ? <Spinner /> : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <Badge tone={STATUS_TONE[v.status]}>{v.status === "draft" ? "Draft — editable" : v.status === "issued" ? "Issued — locked" : "Approved — locked"}</Badge>
            {v.issued_at && <span className="text-xs text-subtle">Issued {formatDate(v.issued_at)}</span>}
            {v.approved_at && <span className="text-xs text-subtle">· Approved {formatDate(v.approved_at)}</span>}
            <div className="flex-1" />
            {v.is_editable && (
              <>
                <Button variant="secondary" onClick={() => setMarkupsOpen(true)}><Percent className="size-4" />Markups</Button>
                <Button variant="secondary" onClick={() => { setEditing(null); setLineOpen(true); }}><Plus className="size-4" />Add line</Button>
                <ConfirmButton size="md" buttonVariant="secondary" variant="primary" label={<><Send className="size-4" />Issue version</>} title={`Issue version ${v.version_number}?`} description="Issuing locks this version and records its totals. Further changes need a new version." confirmLabel="Issue" onConfirm={() => action.mutateAsync(`${base}/issue`)} />
              </>
            )}
            {v.status === "issued" && can(P.ESTIMATES_APPROVE) && (
              <ConfirmButton size="md" buttonVariant="secondary" variant="primary" label={<><CheckCircle2 className="size-4" />Approve</>} title={`Approve version ${v.version_number}?`} description="Approved versions can be used to create the project's original budget." confirmLabel="Approve" onConfirm={() => action.mutateAsync(`${base}/approve`)} />
            )}
            {v.status !== "draft" && isLatest && e.can_edit && (
              <Button onClick={() => action.mutate(`/estimates/${id}/versions`)} loading={action.isPending}><Copy className="size-4" />New version</Button>
            )}
          </div>
          {v.status === "approved" && <Alert tone="success" className="mb-4" title="Approved estimate">Create the original budget from this version on the project's Budget tab.</Alert>}

          <div className="grid gap-6 xl:grid-cols-[1fr_20rem]">
            <Card className="min-w-0">
              <CardHeader title="Lines" description={`${v.lines.length} line${v.lines.length === 1 ? "" : "s"} · select a line to see its build-up`} />
              {v.lines.length === 0 ? (
                <EmptyState title="No lines yet" description={v.is_editable ? "Add measured items, allowances and provisional sums." : undefined} action={v.is_editable && <Button onClick={() => { setEditing(null); setLineOpen(true); }}><Plus className="size-4" />Add line</Button>} />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <caption className="sr-only">Estimate lines</caption>
                    <thead>
                      <tr className="border-b border-border bg-surface-2/60 text-left text-xs font-semibold uppercase tracking-wide text-subtle">
                        <th scope="col" className="px-4 py-2.5">Code</th>
                        <th scope="col" className="px-4 py-2.5">Description</th>
                        <th scope="col" className="px-4 py-2.5 text-right">Qty</th>
                        <th scope="col" className="px-4 py-2.5">Unit</th>
                        <th scope="col" className="px-4 py-2.5 text-right">Rate</th>
                        <th scope="col" className="px-4 py-2.5 text-right">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {v.lines.map((ln) => (
                        <tr key={ln.id} className={cn("cursor-pointer border-b border-border last:border-0 hover:bg-surface-2/70", ln.inclusion !== "base" && "text-muted")} onClick={() => { setEditing(ln); setLineOpen(true); }}>
                          <td className="px-4 py-2.5 font-mono text-xs">{ln.cost_code?.code ?? "—"}</td>
                          <td className="px-4 py-2.5">
                            <button type="button" className="text-left hover:underline" onClick={(ev) => { ev.stopPropagation(); setEditing(ln); setLineOpen(true); }}>{ln.description}</button>
                            <span className="ml-2 inline-flex gap-1">
                              {ln.line_type !== "item" && <Badge>{ln.line_type.replace(/_/g, " ")}</Badge>}
                              {ln.inclusion === "alternate" && <Badge tone="accent">{ln.alternate_label}</Badge>}
                              {ln.inclusion === "excluded" && <Badge tone="warning">Excluded</Badge>}
                            </span>
                          </td>
                          <td className="num px-4 py-2.5 text-right">{formatDecimal(ln.quantity)}</td>
                          <td className="px-4 py-2.5">{ln.unit}</td>
                          <td className="num px-4 py-2.5 text-right">{formatDecimal(ln.calc.unit_cost, 2)}</td>
                          <td className="num px-4 py-2.5 text-right font-medium">{formatMoney(ln.calc.total, c)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            <Card className="h-fit">
              <CardHeader title="Summary" actions={!v.is_editable && <Lock className="size-4 text-subtle" aria-label="Locked" />} />
              <CardBody className="space-y-4 text-sm">
                <dl className="num space-y-1.5">
                  {([["labour", t.labour], ["material", "Material"], ["equipment", t.equipment], ["subcontract", "Subcontract"], ["other", "Other"]] as const).map(([k, l]) => (
                    <div key={k} className="flex justify-between text-muted"><dt>{l}</dt><dd>{formatMoney(v.totals.components[k], c)}</dd></div>
                  ))}
                  <div className="flex justify-between border-t border-border pt-2 font-medium"><dt>Direct cost</dt><dd>{formatMoney(v.totals.direct_cost, c)}</dd></div>
                  {v.markups.map((m) => (
                    <div key={m.name} className="flex justify-between gap-2">
                      <dt className="min-w-0">{m.name} <span className="text-xs text-subtle">{formatDecimal(m.percent)}%{m.basis === "cumulative" ? " running" : ""}{!m.include_in_budget ? " · not budgeted" : ""}</span></dt>
                      <dd>{formatMoney(m.amount, c)}</dd>
                    </div>
                  ))}
                  <div className="flex justify-between border-t-2 border-border-strong pt-2 text-base font-semibold"><dt>Total</dt><dd>{formatMoney(v.totals.total, c)}</dd></div>
                </dl>
                {v.totals.alternates.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-subtle">Alternates (not in total)</p>
                    <dl className="num mt-1 space-y-1">{v.totals.alternates.map((a) => <div key={a.label} className="flex justify-between"><dt>{a.label}</dt><dd>{formatMoney(a.amount, c)}</dd></div>)}</dl>
                  </div>
                )}
                {v.totals.excluded_total !== "0.00" && <p className="num text-xs text-muted">Excluded items (information only): {formatMoney(v.totals.excluded_total, c)}</p>}
                {v.totals.labour_hours !== "0.0000" && <p className="num text-xs text-muted">{t.labour} hours: {formatDecimal(v.totals.labour_hours)}</p>}
              </CardBody>
            </Card>
          </div>

          <EstimateLineDialog
            open={lineOpen}
            onOpenChange={setLineOpen}
            line={editing}
            editable={v.is_editable}
            currency={c}
            codes={codes.data ?? []}
            onSave={async (body) => {
              const path = editing ? `${base}/lines/${editing.id}` : `${base}/lines`;
              applyVersion(await api<EstimateVersion>(path, { method: editing ? "PUT" : "POST", body }));
              notify(editing ? "Line saved" : "Line added");
            }}
            onDelete={editing ? async () => { applyVersion(await api<EstimateVersion>(`${base}/lines/${editing.id}`, { method: "DELETE" })); notify("Line deleted"); } : undefined}
          />
          <MarkupsDialog open={markupsOpen} onOpenChange={setMarkupsOpen} markups={v.markups} onSave={async (rows) => { applyVersion(await api<EstimateVersion>(`${base}/markups`, { method: "PUT", body: { markups: rows } })); notify("Markups saved"); }} />
          <CompareDialog estimate={e} open={compareOpen} onOpenChange={setCompareOpen} />
        </>
      )}
    </>
  );
}
