"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, Plus, Receipt, Undo2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/form";
import { Pagination } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { formatDate, P } from "@/lib/hooks";
import { formatMoney } from "@/lib/money";
import { region } from "@/lib/region";
import type { ContractListItem, CostCode, CostTransactionItem, CostTransactionPage, Project } from "@/lib/types";

const msg = (err: unknown) => (err instanceof ApiError ? err.message : "Something went wrong");
const SIGNED_MONEY = /^-?\d+(\.\d{1,2})?$/;
const LIMIT = 50;

function PostDialog({ project, codes, open, onOpenChange }: { project: Project; codes: CostCode[]; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const { notify } = useToast();
  const [v, setV] = useState({ transaction_type: "actual", transaction_date: "", description: "", amount: "", reference: "", cost_code_id: "", commitment_id: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const commitments = useQuery({ queryKey: ["commitments", project.id, "executed-pick"], queryFn: () => api<ContractListItem[]>("/commitments", { query: { project_id: project.id, status: "executed" } }), enabled: open });
  useEffect(() => {
    if (open) {
      setV({ transaction_type: "actual", transaction_date: new Date().toISOString().slice(0, 10), description: "", amount: "", reference: "", cost_code_id: "", commitment_id: "" });
      setError(null);
    }
  }, [open]);
  const set = (k: keyof typeof v) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setV({ ...v, [k]: e.target.value });
  const save = async () => {
    setError(null);
    const amount = v.amount.replace(/[,\s$£]/g, "");
    if (!v.description.trim()) return setError("Enter a description");
    if (!SIGNED_MONEY.test(amount) || /^-?0+(\.0+)?$/.test(amount)) return setError("Amount: a non-zero number with up to 2 decimals (negative for credits)");
    if (!v.transaction_date) return setError("Enter the date");
    setBusy(true);
    try {
      await api(`/projects/${project.id}/cost-transactions`, { method: "POST", body: {
        transaction_type: v.transaction_type, transaction_date: v.transaction_date, description: v.description.trim(), amount,
        reference: v.reference.trim() || null, cost_code_id: v.cost_code_id || null, commitment_id: v.commitment_id || null,
      } });
      await qc.invalidateQueries({ queryKey: ["ledger", project.id] });
      void qc.invalidateQueries({ queryKey: ["project", project.id, "summary"] });
      notify("Cost posted");
      onOpenChange(false);
    } catch (err) {
      setError(msg(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Post cost" description="Ledger entries cannot be edited later — mistakes are corrected by reversal."
      footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={busy} onClick={save}>Post</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        {error && <Alert tone="danger" className="sm:col-span-2">{error}</Alert>}
        <Field label="Type">{(p) => <Select {...p} value={v.transaction_type} onChange={set("transaction_type")}><option value="actual">Actual (invoice, payroll, receipt)</option><option value="accrual">Accrual (incurred, not yet invoiced)</option></Select>}</Field>
        <Field label="Date" required>{(p) => <Input {...p} type="date" max={new Date().toISOString().slice(0, 10)} value={v.transaction_date} onChange={set("transaction_date")} />}</Field>
        <Field label="Description" required className="sm:col-span-2">{(p) => <Input {...p} value={v.description} onChange={set("description")} maxLength={300} />}</Field>
        <Field label={`Amount (${project.currency})`} required>{(p) => <Input {...p} value={v.amount} onChange={set("amount")} inputMode="decimal" className="num" />}</Field>
        <Field label="Reference" hint="Invoice / ticket number">{(p) => <Input {...p} value={v.reference} onChange={set("reference")} maxLength={80} />}</Field>
        <Field label="Cost code">{(p) => <Select {...p} value={v.cost_code_id} onChange={set("cost_code_id")}><option value="">Unassigned</option>{codes.map((c) => <option key={c.id} value={c.id}>{" ".repeat(c.level - 1)}{c.code} — {c.title}</option>)}</Select>}</Field>
        <Field label="Against commitment">{(p) => <Select {...p} value={v.commitment_id} onChange={set("commitment_id")}><option value="">None</option>{commitments.data?.map((c) => <option key={c.id} value={c.id}>{c.number} — {c.counterparty}</option>)}</Select>}</Field>
      </div>
    </Dialog>
  );
}

function ImportDialog({ project, open, onOpenChange }: { project: Project; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const { notify } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<{ row: number; message: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setFile(null); setErrors([]); setError(null); } }, [open]);
  const run = async () => {
    if (!file) return setError("Choose a CSV file");
    setBusy(true); setError(null); setErrors([]);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await api<{ created: number; total: string; errors: { row: number; message: string }[] }>(`/projects/${project.id}/cost-transactions/import`, { method: "POST", body: fd });
      if (r.errors.length) setErrors(r.errors);
      else {
        await qc.invalidateQueries({ queryKey: ["ledger", project.id] });
        void qc.invalidateQueries({ queryKey: ["project", project.id, "summary"] });
        notify(`${r.created} entries imported (${formatMoney(r.total, project.currency)})`);
        onOpenChange(false);
      }
    } catch (err) {
      setError(msg(err));
    } finally {
      setBusy(false);
    }
  };
  const dateFmt = region() === "GB" ? "DD/MM/YYYY" : "MM/DD/YYYY";
  return (
    <Dialog open={open} onOpenChange={onOpenChange} wide title="Import costs from accounting"
      footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={busy} onClick={run}><FileUp className="size-4" />Import</Button></>}>
      <div className="space-y-4">
        <p className="text-sm text-muted">CSV with headers <code className="font-mono text-fg">date,cost_code,description,amount</code> and optionally <code className="font-mono text-fg">reference,type,commitment</code>. Dates as YYYY-MM-DD or {dateFmt}. Amounts may include currency symbols, commas, or parentheses for credits. Nothing is imported if any row has an error, and the same file cannot be imported twice.</p>
        <pre className="overflow-x-auto rounded-md bg-sunken p-3 text-xs">{`date,cost_code,description,amount,reference,type,commitment\n2026-11-03,05-100,Steel application 2,"95,000.00",INV-2207,actual,SC-001\n2026-11-30,,Site cleaning,1500,,accrual,`}</pre>
        {error && <Alert tone="danger">{error}</Alert>}
        {errors.length > 0 && (
          <Alert tone="danger" title={`${errors.length} problem${errors.length === 1 ? "" : "s"} — nothing was imported`}>
            <ul className="mt-1 max-h-48 list-disc overflow-y-auto pl-5">{errors.map((e, i) => <li key={i}>Row {e.row}: {e.message}</li>)}</ul>
          </Alert>
        )}
        <Field label="CSV file" required>{(p) => <Input {...p} type="file" accept=".csv,text/csv" className="py-1.5" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />}</Field>
      </div>
    </Dialog>
  );
}

function ReverseDialog({ project, tx, onClose }: { project: Project; tx: CostTransactionItem | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { notify } = useToast();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setReason(""); setError(null); }, [tx]);
  const m = useMutation({
    mutationFn: () => api(`/projects/${project.id}/cost-transactions/${tx!.id}/reverse`, { method: "POST", body: { reason: reason.trim() } }),
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ["ledger", project.id] }); void qc.invalidateQueries({ queryKey: ["project", project.id, "summary"] }); notify("Reversing entry posted"); onClose(); },
    onError: (err) => setError(msg(err)),
  });
  return (
    <Dialog open={!!tx} onOpenChange={(o) => !o && onClose()} title="Reverse entry" description={tx ? `Posts ${formatMoney(tx.amount.startsWith("-") ? tx.amount.slice(1) : `-${tx.amount}`, project.currency)} dated today, cancelling “${tx.description}”.` : undefined}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button variant="danger" loading={m.isPending} onClick={() => { setError(null); if (reason.trim().length < 3) return setError("Give a reason"); m.mutate(); }}>Post reversal</Button></>}>
      <div className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <Field label="Reason" required>{(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} placeholder="Posted to the wrong project" />}</Field>
      </div>
    </Dialog>
  );
}

export function CostLedger({ project }: { project: Project }) {
  const { can } = useAuth();
  const [type, setType] = useState("");
  const [offset, setOffset] = useState(0);
  const [postOpen, setPostOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [reversing, setReversing] = useState<CostTransactionItem | null>(null);
  const q = useQuery({ queryKey: ["ledger", project.id, type, offset], queryFn: () => api<CostTransactionPage>(`/projects/${project.id}/cost-transactions`, { query: { transaction_type: type, limit: LIMIT, offset } }) });
  const setIdQ = useQuery({ queryKey: ["project", project.id, "budgets"], queryFn: () => api<{ status: string; cost_code_set_id: string | null }[]>(`/projects/${project.id}/budgets`), enabled: can(P.BUDGETS_VIEW) });
  const setId = setIdQ.data?.find((b) => b.status === "approved")?.cost_code_set_id;
  const codes = useQuery({ queryKey: ["cost-codes", setId, false], queryFn: () => api<CostCode[]>(`/cost-code-sets/${setId}/codes`), enabled: !!setId });
  const edit = can(P.COSTS_EDIT) && !project.archived_at;
  const c = project.currency;
  return (
    <Card>
      <CardHeader title="Cost ledger" description="Actual cost and accruals. Entries are permanent; corrections are reversing entries."
        actions={edit && <><Button size="sm" variant="secondary" onClick={() => setImportOpen(true)}><FileUp className="size-4" />Import CSV</Button><Button size="sm" onClick={() => setPostOpen(true)}><Plus className="size-4" />Post cost</Button></>} />
      <div className="flex flex-wrap items-center gap-3 border-b border-border p-4">
        <Select className="w-48" aria-label="Filter by type" value={type} onChange={(e) => { setType(e.target.value); setOffset(0); }}>
          <option value="">Actuals and accruals</option><option value="actual">Actuals only</option><option value="accrual">Accruals only</option>
        </Select>
        <div className="flex-1" />
        {q.data && <p className="num text-sm text-muted">{q.data.total} entries · total <span className="font-semibold text-fg">{formatMoney(q.data.amount_total, c)}</span></p>}
      </div>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorState error={q.error} /> : !q.data?.items.length ? (
        <EmptyState icon={<Receipt className="size-6" />} title="No cost recorded yet" description="Post invoices and accruals, or import them from your accounting system." />
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Cost ledger</caption>
              <thead><tr className="border-b border-border bg-surface-2/60 text-left text-xs font-semibold uppercase tracking-wide text-subtle">
                <th className="px-4 py-2.5">Date</th><th className="px-4 py-2.5">Code</th><th className="px-4 py-2.5">Description</th><th className="px-4 py-2.5">Ref.</th><th className="px-4 py-2.5">Vendor / commitment</th><th className="px-4 py-2.5 text-right">Amount</th>{edit && <th><span className="sr-only">Actions</span></th>}
              </tr></thead>
              <tbody>
                {q.data.items.map((t) => (
                  <tr key={t.id} className={cn("border-b border-border", t.reversed && "text-subtle line-through decoration-subtle/50")}>
                    <td className="num px-4 py-2.5 whitespace-nowrap">{formatDate(t.transaction_date)}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">{t.cost_code?.code ?? "—"}</td>
                    <td className="px-4 py-2.5">{t.description}{t.transaction_type === "accrual" && <Badge className="ml-2">Accrual</Badge>}{t.reverses_id && <Badge tone="warning" className="ml-2">Reversal</Badge>}{t.imported && <Badge className="ml-2">Imported</Badge>}</td>
                    <td className="px-4 py-2.5 text-muted">{t.reference ?? ""}</td>
                    <td className="px-4 py-2.5 text-muted">{[t.vendor_name, t.commitment_number].filter(Boolean).join(" · ") || "—"}</td>
                    <td className={cn("num px-4 py-2.5 text-right", t.amount.startsWith("-") && "text-danger")}>{formatMoney(t.amount, c)}</td>
                    {edit && <td className="px-2 text-right">{!t.reversed && !t.reverses_id && <Button size="sm" variant="ghost" onClick={() => setReversing(t)} aria-label={`Reverse ${t.description}`}><Undo2 className="size-4" /></Button>}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination total={q.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      )}
      <PostDialog project={project} codes={codes.data ?? []} open={postOpen} onOpenChange={setPostOpen} />
      <ImportDialog project={project} open={importOpen} onOpenChange={setImportOpen} />
      <ReverseDialog project={project} tx={reversing} onClose={() => setReversing(null)} />
    </Card>
  );
}
