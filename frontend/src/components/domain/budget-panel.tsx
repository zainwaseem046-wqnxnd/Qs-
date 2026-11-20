"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Plus, Trash2, Wallet } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { ConfirmButton, Dialog } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate, P } from "@/lib/hooks";
import { formatMoney, parseMoneyInput } from "@/lib/money";
import type { Budget, BudgetLine, CostCode, Estimate, Project } from "@/lib/types";

const msg = (err: unknown) => (err instanceof ApiError ? err.message : "Something went wrong");

function CreateBudgetDialog({ project, open, onOpenChange }: { project: Project; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const { notify } = useToast();
  const [source, setSource] = useState("");
  const [name, setName] = useState("Original budget");
  const [error, setError] = useState<string | null>(null);
  const estimates = useQuery({ queryKey: ["estimates", project.id], queryFn: () => api<Estimate[]>("/estimates", { query: { project_id: project.id } }), enabled: open });
  const approved = (estimates.data ?? []).flatMap((e) => e.versions.filter((v) => v.status === "approved").map((v) => ({ e, v })));
  useEffect(() => {
    if (open) { setName("Original budget"); setError(null); setSource(""); }
  }, [open]);
  const create = useMutation({
    mutationFn: () => {
      if (source) {
        const [estimate_id, version] = source.split(":");
        return api<Budget>(`/projects/${project.id}/budgets/from-estimate`, { method: "POST", body: { estimate_id, version_number: Number(version), name: name.trim() } });
      }
      return api<Budget>(`/projects/${project.id}/budgets`, { method: "POST", body: { name: name.trim() } });
    },
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ["project", project.id, "budgets"] }); notify("Draft budget created"); onOpenChange(false); },
    onError: (err) => setError(msg(err)),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Create budget" description="Budgets created from an approved estimate get one line per cost code, plus markups marked 'in budget'."
      footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={create.isPending} onClick={() => { setError(null); if (name.trim().length < 2) return setError("Enter a name"); create.mutate(); }}>Create draft budget</Button></>}>
      <div className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <Field label="Source" hint={approved.length ? undefined : "No approved estimate versions on this project yet."}>
          {(p) => (
            <Select {...p} value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="">Blank budget (enter lines manually)</option>
              {approved.map(({ e, v }) => <option key={`${e.id}:${v.version_number}`} value={`${e.id}:${v.version_number}`}>{e.name} — v{v.version_number} ({formatMoney(v.total, e.currency)})</option>)}
            </Select>
          )}
        </Field>
        <Field label="Name" required>{(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />}</Field>
      </div>
    </Dialog>
  );
}

function LineDialog({ budget, line, open, onOpenChange, codes }: { budget: Budget; line: BudgetLine | null; open: boolean; onOpenChange: (o: boolean) => void; codes: CostCode[] }) {
  const qc = useQueryClient();
  const { notify } = useToast();
  const [codeId, setCodeId] = useState("");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      setCodeId(line?.cost_code?.id ?? ""); setDescription(line?.description ?? ""); setAmount(line?.amount ?? ""); setNotes(line?.notes ?? ""); setError(null);
    }
  }, [open, line]);
  const save = useMutation({
    mutationFn: () => {
      const body = { cost_code_id: codeId || null, description: description.trim(), amount: parseMoneyInput(amount), notes: notes.trim() || null };
      return line
        ? api<Budget>(`/budgets/${budget.id}/lines/${line.id}`, { method: "PUT", body })
        : api<Budget>(`/budgets/${budget.id}/lines`, { method: "POST", body });
    },
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ["project", budget.project_id, "budgets"] }); notify(line ? "Line saved" : "Line added"); onOpenChange(false); },
    onError: (err) => setError(msg(err)),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={line ? "Edit budget line" : "Add budget line"}
      footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={save.isPending} onClick={() => { setError(null); if (!description.trim()) return setError("Enter a description"); if (parseMoneyInput(amount) === null) return setError("Enter an amount with up to 2 decimals"); save.mutate(); }}>Save</Button></>}>
      <div className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <Field label="Cost code">{(p) => <Select {...p} value={codeId} onChange={(e) => setCodeId(e.target.value)}><option value="">None</option>{codes.map((c) => <option key={c.id} value={c.id}>{" ".repeat(c.level - 1)}{c.code} — {c.title}</option>)}</Select>}</Field>
        <Field label="Description" required>{(p) => <Input {...p} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} />}</Field>
        <Field label={`Amount (${budget.currency})`} required>{(p) => <Input {...p} value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" className="num" />}</Field>
        <Field label="Notes">{(p) => <Textarea {...p} value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />}</Field>
      </div>
    </Dialog>
  );
}

function BudgetCard({ budget, project }: { budget: Budget; project: Project }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const { notify } = useToast();
  const [lineOpen, setLineOpen] = useState(false);
  const [editing, setEditing] = useState<BudgetLine | null>(null);
  const codes = useQuery({ queryKey: ["cost-codes", budget.cost_code_set_id, false], queryFn: () => api<CostCode[]>(`/cost-code-sets/${budget.cost_code_set_id}/codes`), enabled: !!budget.cost_code_set_id && budget.is_editable });
  const invalidate = () => { void qc.invalidateQueries({ queryKey: ["project", project.id, "budgets"] }); void qc.invalidateQueries({ queryKey: ["dashboard"] }); };
  const approve = useMutation({ mutationFn: () => api(`/budgets/${budget.id}/approve`, { method: "POST" }), onSuccess: () => { invalidate(); notify("Original budget approved"); }, onError: (err) => notify(msg(err), "danger") });
  const remove = useMutation({ mutationFn: () => api(`/budgets/${budget.id}`, { method: "DELETE" }), onSuccess: () => { invalidate(); notify("Draft budget deleted"); }, onError: (err) => notify(msg(err), "danger") });
  const removeLine = useMutation({ mutationFn: (id: string) => api(`/budgets/${budget.id}/lines/${id}`, { method: "DELETE" }), onSuccess: () => { invalidate(); notify("Line deleted"); }, onError: (err) => notify(msg(err), "danger") });
  const c = budget.currency;
  return (
    <Card>
      <CardHeader
        title={<span className="flex items-center gap-2">{budget.name}<Badge tone={budget.status === "approved" ? "success" : "neutral"}>{budget.status === "approved" ? "Approved original budget" : "Draft"}</Badge></span>}
        description={<>{budget.source_description ? `From ${budget.source_description}` : "Entered manually"}{budget.approved_at ? ` · approved ${formatDate(budget.approved_at)}` : ""}</>}
        actions={budget.is_editable && (
          <>
            <ConfirmButton label={<Trash2 className="size-4" />} buttonVariant="ghost" title={`Delete draft "${budget.name}"?`} description="Draft budgets can be deleted; approved budgets cannot." confirmLabel="Delete" onConfirm={() => remove.mutateAsync()} />
            <Button size="sm" variant="secondary" onClick={() => { setEditing(null); setLineOpen(true); }}><Plus className="size-4" />Add line</Button>
            {can(P.BUDGETS_APPROVE) && <ConfirmButton size="sm" buttonVariant="secondary" variant="primary" label={<><CheckCircle2 className="size-4" />Approve</>} title="Approve as the original budget?" description="The approved original budget is locked. Later changes come through budget transfers and change orders." confirmLabel="Approve" onConfirm={() => approve.mutateAsync()} />}
          </>
        )}
      />
      {budget.lines.length === 0 ? <EmptyState title="No lines yet" /> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">Budget lines</caption>
            <thead><tr className="border-b border-border bg-surface-2/60 text-left text-xs font-semibold uppercase tracking-wide text-subtle"><th className="px-4 py-2.5">Code</th><th className="px-4 py-2.5">Description</th><th className="px-4 py-2.5 text-right">Amount</th>{budget.is_editable && <th className="px-4 py-2.5"><span className="sr-only">Actions</span></th>}</tr></thead>
            <tbody>
              {budget.lines.map((ln) => (
                <tr key={ln.id} className="border-b border-border">
                  <td className="px-4 py-2.5 font-mono text-xs">{ln.cost_code?.code ?? "—"}</td>
                  <td className="px-4 py-2.5">{ln.description}{ln.notes && <span className="block text-xs text-subtle">{ln.notes}</span>}</td>
                  <td className="num px-4 py-2.5 text-right">{formatMoney(ln.amount, c)}</td>
                  {budget.is_editable && (
                    <td className="px-4 py-1.5 text-right whitespace-nowrap">
                      <Button size="sm" variant="ghost" onClick={() => { setEditing(ln); setLineOpen(true); }}>Edit</Button>
                      <ConfirmButton label={<Trash2 className="size-4" />} buttonVariant="ghost" title="Delete this line?" description={ln.description} confirmLabel="Delete" onConfirm={() => removeLine.mutateAsync(ln.id)} />
                    </td>
                  )}
                </tr>
              ))}
              <tr className="font-semibold"><td className="px-4 py-3" colSpan={2}>Total</td><td className="num px-4 py-3 text-right">{formatMoney(budget.total, c)}</td>{budget.is_editable && <td />}</tr>
            </tbody>
          </table>
        </div>
      )}
      <LineDialog budget={budget} line={editing} open={lineOpen} onOpenChange={setLineOpen} codes={codes.data ?? []} />
    </Card>
  );
}

export function BudgetPanel({ project }: { project: Project }) {
  const { can } = useAuth();
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["project", project.id, "budgets"], queryFn: () => api<Budget[]>(`/projects/${project.id}/budgets`) });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  const budgets = q.data ?? [];
  const hasApproved = budgets.some((b) => b.status === "approved");
  return (
    <div className="space-y-6">
      {can(P.BUDGETS_EDIT) && !project.archived_at && !hasApproved && (
        <div className="flex justify-end"><Button onClick={() => setOpen(true)}><Plus className="size-4" />Create budget</Button></div>
      )}
      {budgets.length === 0 ? (
        <Card><EmptyState icon={<Wallet className="size-6" />} title="No budget yet" description="Approve an estimate version, then create the original budget from it — or enter a budget manually." /></Card>
      ) : (
        budgets.map((b) => <BudgetCard key={b.id} budget={b} project={project} />)
      )}
      <CreateBudgetDialog project={project} open={open} onOpenChange={setOpen} />
    </div>
  );
}
