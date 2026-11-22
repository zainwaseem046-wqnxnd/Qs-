"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Pencil, Plus, Send, Trash2, Undo2, XCircle } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CO_TONES, useChangeReference } from "@/components/domain/change-orders-list";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, DescriptionList } from "@/components/ui/card";
import { ConfirmButton, Dialog } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Checkbox, Field, Input, Options, Select, Textarea } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { clean } from "@/lib/decimal";
import { formatDate, formatDateTime, formatDecimal, P } from "@/lib/hooks";
import { formatMoney } from "@/lib/money";
import type { ChangeOrder, ChangeOrderLine, CostCode } from "@/lib/types";

const msg = (err: unknown) => (err instanceof ApiError ? err.message : "Something went wrong");
const SIGNED_MONEY = /^-?\d+(\.\d{1,2})?$/;
const SIGNED_QTY = /^-?\d+(\.\d{1,4})?$/;
const RATE = /^\d+(\.\d{1,6})?$/;

function LineDialog({ co, line, open, onOpenChange, codes, onSaved }: {
  co: ChangeOrder; line: ChangeOrderLine | null; open: boolean; onOpenChange: (o: boolean) => void; codes: CostCode[]; onSaved: (c: ChangeOrder) => void;
}) {
  const clientSide = co.target.type === "contract";
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [measured, setMeasured] = useState(false);
  const [qty, setQty] = useState("");
  const [unit, setUnit] = useState("");
  const [rate, setRate] = useState("");
  const [amount, setAmount] = useState("");
  const [budget, setBudget] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) {
      setCode(line?.cost_code?.id ?? ""); setDescription(line?.description ?? ""); setMeasured(!!line?.quantity);
      setQty(line?.quantity ? formatDecimal(line.quantity).replace(/,/g, "") : ""); setUnit(line?.unit ?? "");
      setRate(line?.unit_rate ? formatDecimal(line.unit_rate).replace(/,/g, "") : "");
      setAmount(line && !line.quantity ? line.amount : ""); setBudget(line?.budget_amount ?? ""); setError(null);
    }
  }, [open, line]);
  const save = async () => {
    setError(null);
    if (!description.trim()) return setError("Enter a description");
    const body: Record<string, unknown> = { cost_code_id: code || null, description: description.trim() };
    if (measured) {
      if (!SIGNED_QTY.test(clean(qty))) return setError("Quantity: a number with up to 4 decimals (negative for omissions)");
      if (!RATE.test(clean(rate))) return setError("Unit rate: a positive number with up to 6 decimals");
      if (!unit.trim()) return setError("Enter a unit");
      Object.assign(body, { quantity: clean(qty), unit: unit.trim(), unit_rate: clean(rate) });
    } else {
      if (!SIGNED_MONEY.test(clean(amount))) return setError("Amount: up to 2 decimals; use a minus sign for omissions");
      body.amount = clean(amount);
    }
    if (clientSide && budget.trim()) {
      if (!SIGNED_MONEY.test(clean(budget))) return setError("Budget adjustment: up to 2 decimals");
      body.budget_amount = clean(budget);
    }
    setBusy(true);
    try {
      const path = line ? `/change-orders/${co.id}/lines/${line.id}` : `/change-orders/${co.id}/lines`;
      onSaved(await api<ChangeOrder>(path, { method: line ? "PUT" : "POST", body }));
      onOpenChange(false);
    } catch (err) {
      setError(msg(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={line ? "Edit line" : "Add line"} description="Positive amounts are additions; negative amounts are omissions."
      footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={busy} onClick={save}>Save line</Button></>}>
      <div className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <Field label="Cost code">{(p) => <Select {...p} value={code} onChange={(e) => setCode(e.target.value)}><option value="">Unassigned</option>{codes.map((c) => <option key={c.id} value={c.id}>{" ".repeat(c.level - 1)}{c.code} — {c.title}</option>)}</Select>}</Field>
        <Field label="Description" required>{(p) => <Input {...p} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} />}</Field>
        <Checkbox label="Measured (quantity × rate)" hint="Calculated by the server; negative quantity for omitted work" checked={measured} onChange={(e) => setMeasured(e.target.checked)} />
        {measured ? (
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Quantity" required>{(p) => <Input {...p} value={qty} onChange={(e) => setQty(e.target.value)} inputMode="decimal" className="num" />}</Field>
            <Field label="Unit" required>{(p) => <Input {...p} value={unit} onChange={(e) => setUnit(e.target.value)} maxLength={20} />}</Field>
            <Field label="Unit rate" required>{(p) => <Input {...p} value={rate} onChange={(e) => setRate(e.target.value)} inputMode="decimal" className="num" />}</Field>
          </div>
        ) : (
          <Field label={`Amount (${co.currency})`} required>{(p) => <Input {...p} value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" className="num" />}</Field>
        )}
        {clientSide && (
          <Field label={`Budget adjustment (${co.currency})`} hint="Cost to add to the project budget for this line when approved (optional)">
            {(p) => <Input {...p} value={budget} onChange={(e) => setBudget(e.target.value)} inputMode="decimal" className="num" />}
          </Field>
        )}
      </div>
    </Dialog>
  );
}

function DetailsDialog({ co, open, onOpenChange, onSaved }: { co: ChangeOrder; open: boolean; onOpenChange: (o: boolean) => void; onSaved: (c: ChangeOrder) => void }) {
  const ref = useChangeReference().data;
  const [v, setV] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) {
      setV({ title: co.title, reason: co.reason, reference: co.reference ?? "", description: co.description ?? "", notified_date: co.notified_date ?? "", response_due_date: co.response_due_date ?? "", schedule_impact_days: co.schedule_impact_days?.toString() ?? "" });
      setError(null);
    }
  }, [open, co]);
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setV({ ...v, [k]: e.target.value });
  const save = async () => {
    setError(null);
    if ((v.title ?? "").trim().length < 2) return setError("Enter a title");
    if (v.schedule_impact_days && !/^-?\d{1,4}$/.test(v.schedule_impact_days)) return setError("Schedule impact must be a whole number of days");
    setBusy(true);
    try {
      onSaved(await api<ChangeOrder>(`/change-orders/${co.id}`, { method: "PATCH", body: {
        version: co.version, title: v.title?.trim(), reason: v.reason, reference: v.reference || null, description: v.description || null,
        notified_date: v.notified_date || null, response_due_date: v.response_due_date || null,
        schedule_impact_days: v.schedule_impact_days ? Number.parseInt(v.schedule_impact_days, 10) : null,
      } }));
      onOpenChange(false);
    } catch (err) {
      setError(msg(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange} wide title="Edit details" footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={busy} onClick={save}>Save</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        {error && <Alert tone="danger" className="sm:col-span-2">{error}</Alert>}
        <Field label="Title" required className="sm:col-span-2">{(p) => <Input {...p} value={v.title ?? ""} onChange={set("title")} maxLength={200} />}</Field>
        <Field label="Reason">{(p) => <Select {...p} value={v.reason ?? ""} onChange={set("reason")}><Options map={ref?.reasons} /></Select>}</Field>
        <Field label="Reference">{(p) => <Input {...p} value={v.reference ?? ""} onChange={set("reference")} maxLength={80} />}</Field>
        <Field label="Notified date">{(p) => <Input {...p} type="date" value={v.notified_date ?? ""} onChange={set("notified_date")} />}</Field>
        <Field label="Response due">{(p) => <Input {...p} type="date" value={v.response_due_date ?? ""} onChange={set("response_due_date")} />}</Field>
        <Field label="Schedule impact (days)">{(p) => <Input {...p} value={v.schedule_impact_days ?? ""} onChange={set("schedule_impact_days")} inputMode="numeric" />}</Field>
        <Field label="Description" className="sm:col-span-2">{(p) => <Textarea {...p} value={v.description ?? ""} onChange={set("description")} rows={4} />}</Field>
      </div>
    </Dialog>
  );
}

export default function ChangeOrderPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const { notify } = useToast();
  const ref = useChangeReference().data;
  const { can } = useAuth();
  const [lineOpen, setLineOpen] = useState(false);
  const [editing, setEditing] = useState<ChangeOrderLine | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [decision, setDecision] = useState<"approve" | "reject" | null>(null);
  const [notes, setNotes] = useState("");
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["change-order", id], queryFn: () => api<ChangeOrder>(`/change-orders/${id}`) });
  const targetPath = q.data ? (q.data.target.type === "contract" ? `/contracts/${q.data.target.id}` : `/commitments/${q.data.target.id}`) : "";
  const setId = useQuery({
    queryKey: ["co-target-set", targetPath],
    queryFn: () => api<{ cost_code_set_id: string | null }>(q.data!.target.type === "contract" ? `/contracts/${q.data!.target.id}` : `/commitments/${q.data!.target.id}`),
    enabled: !!q.data?.is_editable,
  });
  const codes = useQuery({ queryKey: ["cost-codes", setId.data?.cost_code_set_id, false], queryFn: () => api<CostCode[]>(`/cost-code-sets/${setId.data!.cost_code_set_id}/codes`), enabled: !!setId.data?.cost_code_set_id });
  const apply = (c: ChangeOrder) => {
    qc.setQueryData(["change-order", id], c);
    void qc.invalidateQueries({ queryKey: ["change-orders"] });
    void qc.invalidateQueries({ queryKey: ["contracts"] });
    void qc.invalidateQueries({ queryKey: ["commitments"] });
    void qc.invalidateQueries({ queryKey: ["project", c.project_id, "summary"] });
    void qc.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const action = useMutation({
    mutationFn: (v: { name: string; body?: Record<string, unknown> }) => api<ChangeOrder>(`/change-orders/${id}/${v.name}`, { method: "POST", body: { version: q.data!.version, ...v.body } }),
    onSuccess: (c) => { apply(c); setDecision(null); notify(`${c.number} ${ref?.statuses[c.status]?.toLowerCase() ?? c.status}`); },
    onError: (err) => { setDecisionError(msg(err)); notify(msg(err), "danger"); },
  });
  const removeLine = useMutation({ mutationFn: (lineId: string) => api<ChangeOrder>(`/change-orders/${id}/lines/${lineId}`, { method: "DELETE" }), onSuccess: (c) => { apply(c); notify("Line deleted"); }, onError: (err) => notify(msg(err), "danger") });
  const remove = useMutation({ mutationFn: () => api(`/change-orders/${id}`, { method: "DELETE" }), onSuccess: () => { void qc.invalidateQueries({ queryKey: ["change-orders"] }); notify("Draft deleted"); router.push("/change-orders"); }, onError: (err) => notify(msg(err), "danger") });

  if (q.isLoading) return <Spinner />;
  if (q.error instanceof ApiError && [403, 404].includes(q.error.status)) return <EmptyState title="Not available" description="It may not exist, or you may not have access to it." action={<Link href="/change-orders" className="text-accent hover:underline">Back</Link>} />;
  if (q.error || !q.data) return <ErrorState error={q.error} />;
  const co = q.data;
  const c = co.currency;
  const clientSide = co.target.type === "contract";
  const measured = co.lines.some((l) => l.quantity);
  const pending = co.status === "draft" || co.status === "submitted";

  return (
    <>
      <PageHeader
        breadcrumb={<><Link href="/change-orders" className="hover:underline">{co.label === "Change order" || co.label === "Subcontract change order" ? "Change orders" : "Variations"}</Link> / <Link href={`/projects/${co.project_id}`} className="hover:underline">{co.project_number} {co.project_name}</Link></>}
        title={<span className="flex flex-wrap items-center gap-3"><span className="num">{co.number}</span> {co.title}<Badge tone={CO_TONES[co.status]}>{ref?.statuses[co.status] ?? co.status}</Badge>{co.overdue && <Badge tone="warning">Response overdue</Badge>}</span>}
        description={<>{co.label} against <Link href={targetPath} className="text-accent hover:underline">{co.target.number} {co.target.title}</Link>{co.target.counterparty ? ` · ${co.target.counterparty}` : ""}</>}
        actions={
          <>
            {co.is_editable && <ConfirmButton size="md" label={<><Trash2 className="size-4" />Delete draft</>} title={`Delete ${co.number}?`} description="Only drafts can be deleted." confirmLabel="Delete" onConfirm={() => remove.mutateAsync()} />}
            {pending && can(P.CHANGES_EDIT) && (
              <ConfirmButton size="md" label="Withdraw" title={`Withdraw ${co.number}?`} description="Withdrawn changes are kept for the record and cannot be reopened." confirmLabel="Withdraw" onConfirm={() => action.mutateAsync({ name: "withdraw" })} />
            )}
            {co.is_editable && <Button variant="secondary" onClick={() => setDetailsOpen(true)}><Pencil className="size-4" />Edit details</Button>}
            {co.is_editable && <ConfirmButton size="md" buttonVariant="secondary" variant="primary" label={<><Send className="size-4" />Submit</>} title={`Submit ${co.number}?`} description={`Submits ${formatMoney(co.total, c)} for a decision. Content is locked while submitted.`} confirmLabel="Submit" onConfirm={() => action.mutateAsync({ name: "submit" })} />}
            {co.status === "submitted" && <Button variant="secondary" onClick={() => action.mutate({ name: "return-to-draft" })}><Undo2 className="size-4" />Return to draft</Button>}
            {co.status === "submitted" && co.can_approve && (
              <>
                <Button variant="secondary" onClick={() => { setNotes(""); setDecisionError(null); setDecision("reject"); }}><XCircle className="size-4" />Reject</Button>
                <Button onClick={() => { setNotes(""); setDecisionError(null); setDecision("approve"); }}><CheckCircle2 className="size-4" />Approve</Button>
              </>
            )}
          </>
        }
      />
      {co.status === "submitted" && <Alert tone="info" className="mb-4" title="Submitted — awaiting a decision">Content is locked. Return it to draft to re-price during negotiation.</Alert>}
      {co.status === "approved" && <Alert tone="success" className="mb-4" title={`Approved ${formatDateTime(co.decided_at)}`}>{clientSide ? "The revised contract sum and revised budget now include this change." : "The revised commitment value now includes this change."}{co.decision_notes ? ` Notes: ${co.decision_notes}` : ""}</Alert>}
      {co.status === "rejected" && <Alert tone="danger" className="mb-4" title={`Rejected ${formatDateTime(co.decided_at)}`}>{co.decision_notes}</Alert>}

      <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
        <Card className="min-w-0">
          <CardHeader title="Pricing" description="Additions are positive, omissions negative." actions={co.is_editable && <Button size="sm" onClick={() => { setEditing(null); setLineOpen(true); }}><Plus className="size-4" />Add line</Button>} />
          {co.lines.length === 0 ? <EmptyState title="No lines yet" description="Price the change before submitting it." /> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <caption className="sr-only">Change lines</caption>
                <thead><tr className="border-b border-border bg-surface-2/60 text-left text-xs font-semibold uppercase tracking-wide text-subtle">
                  <th className="px-4 py-2.5">Code</th><th className="px-4 py-2.5">Description</th>
                  {measured && <><th className="px-4 py-2.5 text-right">Qty</th><th className="px-4 py-2.5">Unit</th><th className="px-4 py-2.5 text-right">Rate</th></>}
                  <th className="px-4 py-2.5 text-right">Amount</th>{clientSide && <th className="px-4 py-2.5 text-right">Budget adj.</th>}{co.is_editable && <th><span className="sr-only">Actions</span></th>}
                </tr></thead>
                <tbody>
                  {co.lines.map((l) => (
                    <tr key={l.id} className="border-b border-border">
                      <td className="px-4 py-2.5 font-mono text-xs">{l.cost_code?.code ?? "—"}</td>
                      <td className="px-4 py-2.5">{l.description}</td>
                      {measured && <><td className="num px-4 py-2.5 text-right">{l.quantity ? formatDecimal(l.quantity) : ""}</td><td className="px-4 py-2.5">{l.unit ?? ""}</td><td className="num px-4 py-2.5 text-right">{l.unit_rate ? formatDecimal(l.unit_rate, 2) : ""}</td></>}
                      <td className={cn("num px-4 py-2.5 text-right", l.amount.startsWith("-") && "text-danger")}>{formatMoney(l.amount, c)}</td>
                      {clientSide && <td className="num px-4 py-2.5 text-right text-muted">{l.budget_amount ? formatMoney(l.budget_amount, c) : "—"}</td>}
                      {co.is_editable && <td className="whitespace-nowrap px-2 text-right"><Button size="sm" variant="ghost" onClick={() => { setEditing(l); setLineOpen(true); }}>Edit</Button><ConfirmButton label={<Trash2 className="size-4" />} buttonVariant="ghost" title="Delete this line?" description={l.description} confirmLabel="Delete" onConfirm={() => removeLine.mutateAsync(l.id)} /></td>}
                    </tr>
                  ))}
                  <tr className="font-semibold"><td className="px-4 py-3" colSpan={measured ? 5 : 2}>Total</td><td className="num px-4 py-3 text-right">{formatMoney(co.total, c)}</td>{clientSide && <td className="num px-4 py-3 text-right">{formatMoney(co.budget_total, c)}</td>}{co.is_editable && <td />}</tr>
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader title={clientSide ? "Value to client" : "Change to commitment"} />
            <CardBody>
              <p className={cn("num text-2xl font-semibold", co.total.startsWith("-") && "text-danger")}>{formatMoney(co.total, c)}</p>
              {clientSide && <p className="num mt-1 text-xs text-subtle">Budget adjustment {formatMoney(co.budget_total, c)}</p>}
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Details" />
            <CardBody>
              <DescriptionList columns={1} items={[
                { label: "Reason", value: ref?.reasons[co.reason] ?? co.reason },
                { label: "Reference", value: co.reference ?? "—" },
                { label: "Notified", value: formatDate(co.notified_date) },
                { label: "Response due", value: <span className={cn(co.overdue && "font-medium text-warning")}>{formatDate(co.response_due_date)}{co.overdue ? " (overdue)" : ""}</span> },
                { label: "Schedule impact", value: co.schedule_impact_days !== null ? `${co.schedule_impact_days} days` : "—" },
                ...(co.submitted_at ? [{ label: "Submitted", value: formatDateTime(co.submitted_at) }] : []),
                ...(co.description ? [{ label: "Description", value: <span className="whitespace-pre-wrap">{co.description}</span> }] : []),
              ]} />
            </CardBody>
          </Card>
        </div>
      </div>

      <LineDialog co={co} line={editing} open={lineOpen} onOpenChange={setLineOpen} codes={codes.data ?? []} onSaved={(x) => { apply(x); notify(editing ? "Line saved" : "Line added"); }} />
      <DetailsDialog co={co} open={detailsOpen} onOpenChange={setDetailsOpen} onSaved={(x) => { apply(x); notify("Details saved"); }} />
      <Dialog open={decision !== null} onOpenChange={(o) => !o && setDecision(null)} title={decision === "approve" ? `Approve ${co.number}` : `Reject ${co.number}`}
        description={decision === "approve" ? `Approves ${formatMoney(co.total, c)}. This decision is final and recorded in the audit trail.` : "Rejection is final. Raise a new change if it is re-presented."}
        footer={<><Button variant="secondary" onClick={() => setDecision(null)}>Cancel</Button><Button variant={decision === "reject" ? "danger" : "primary"} loading={action.isPending} onClick={() => { setDecisionError(null); if (decision === "reject" && !notes.trim()) return setDecisionError("Give a reason for rejecting"); action.mutate({ name: decision!, body: { notes: notes.trim() || null } }); }}>{decision === "approve" ? "Approve" : "Reject"}</Button></>}>
        <div className="space-y-4">
          {decisionError && <Alert tone="danger">{decisionError}</Alert>}
          <Field label={decision === "reject" ? "Reason for rejection" : "Notes (optional)"} required={decision === "reject"}>{(p) => <Textarea {...p} value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />}</Field>
        </div>
      </Dialog>
    </>
  );
}
