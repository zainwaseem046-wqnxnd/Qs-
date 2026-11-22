"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, CheckCircle2, Lock, Pencil, Plus, Trash2, Archive } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, DescriptionList } from "@/components/ui/card";
import { ConfirmButton, Dialog } from "@/components/ui/dialog";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Checkbox, Field, Input, Options, Select, Textarea } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { clean, decimalError } from "@/lib/decimal";
import { formatDate, formatDecimal } from "@/lib/hooks";
import { formatMoney, formatPercent, parseMoneyInput } from "@/lib/money";
import { terms } from "@/lib/region";
import type { Company, ContractKind, ContractLineItem, ContractRecord, CostCode, Page } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { P } from "@/lib/hooks";
import { ChangeOrdersList } from "./change-orders-list";
import { STATUS_TONES, useContractVocab } from "./contracts-list";

const msg = (err: unknown) => (err instanceof ApiError ? err.message : "Something went wrong");
const today = () => new Date().toISOString().slice(0, 10);

function LineDialog({ kind, record, line, open, onOpenChange, codes, onSaved }: {
  kind: ContractKind; record: ContractRecord; line: ContractLineItem | null; open: boolean; onOpenChange: (o: boolean) => void; codes: CostCode[]; onSaved: (r: ContractRecord) => void;
}) {
  const measuredAllowed = kind === "commitments";
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [measured, setMeasured] = useState(false);
  const [qty, setQty] = useState("");
  const [unit, setUnit] = useState("");
  const [rate, setRate] = useState("");
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) {
      setCode(line?.cost_code?.id ?? "");
      setDescription(line?.description ?? "");
      setMeasured(!!line?.quantity);
      setQty(line?.quantity ? formatDecimal(line.quantity).replace(/,/g, "") : "");
      setUnit(line?.unit ?? "");
      setRate(line?.unit_rate ? formatDecimal(line.unit_rate).replace(/,/g, "") : "");
      setAmount(line && !line.quantity ? line.amount : "");
      setError(null);
    }
  }, [open, line]);
  const save = async () => {
    setError(null);
    if (!description.trim()) return setError("Enter a description");
    const body: Record<string, unknown> = { cost_code_id: code || null, description: description.trim() };
    if (measured) {
      const e = decimalError(qty, 4, { required: true, label: "Quantity" }) ?? decimalError(rate, 6, { required: true, label: "Rate" });
      if (e) return setError(e);
      if (!unit.trim()) return setError("Enter a unit");
      Object.assign(body, { quantity: clean(qty), unit: unit.trim(), unit_rate: clean(rate) });
    } else {
      const a = parseMoneyInput(amount);
      if (a === null) return setError("Enter an amount with up to 2 decimals");
      body.amount = a;
    }
    setBusy(true);
    try {
      const path = line ? `/${kind}/${record.id}/lines/${line.id}` : `/${kind}/${record.id}/lines`;
      onSaved(await api<ContractRecord>(path, { method: line ? "PUT" : "POST", body }));
      onOpenChange(false);
    } catch (err) {
      setError(msg(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={line ? "Edit line" : "Add line"}
      footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={busy} onClick={save}>Save line</Button></>}>
      <div className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <Field label="Cost code">{(p) => <Select {...p} value={code} onChange={(e) => setCode(e.target.value)}><option value="">Unassigned</option>{codes.map((c) => <option key={c.id} value={c.id}>{" ".repeat(c.level - 1)}{c.code} — {c.title}</option>)}</Select>}</Field>
        <Field label="Description" required>{(p) => <Input {...p} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} />}</Field>
        {measuredAllowed && <Checkbox label="Measured (quantity × rate)" hint="The amount is calculated by the server and rounded to the cent/penny" checked={measured} onChange={(e) => setMeasured(e.target.checked)} />}
        {measured ? (
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Quantity" required>{(p) => <Input {...p} value={qty} onChange={(e) => setQty(e.target.value)} inputMode="decimal" className="num" />}</Field>
            <Field label="Unit" required>{(p) => <Input {...p} value={unit} onChange={(e) => setUnit(e.target.value)} maxLength={20} />}</Field>
            <Field label="Unit rate" required>{(p) => <Input {...p} value={rate} onChange={(e) => setRate(e.target.value)} inputMode="decimal" className="num" />}</Field>
          </div>
        ) : (
          <Field label={`Amount (${record.currency})`} required>{(p) => <Input {...p} value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" className="num" />}</Field>
        )}
      </div>
    </Dialog>
  );
}

function TermsDialog({ kind, record, open, onOpenChange, onSaved }: { kind: ContractKind; record: ContractRecord; open: boolean; onOpenChange: (o: boolean) => void; onSaved: (r: ContractRecord) => void }) {
  const vocab = useContractVocab().data;
  const t = terms();
  const isPrime = kind === "contracts";
  const companies = useQuery({ queryKey: ["companies", "all-active"], queryFn: () => api<Page<Company>>("/companies", { query: { limit: 200 } }), enabled: open });
  const [v, setV] = useState<Record<string, string>>({});
  const [bond, setBond] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) {
      setV({
        title: record.title, contract_form: record.contract_form,
        party: (isPrime ? record.client_company?.id : record.vendor?.id) ?? "",
        retention_percent: record.retention_percent ? formatDecimal(record.retention_percent) : "",
        retention_terms: record.retention_terms ?? "", payment_terms_days: record.payment_terms_days?.toString() ?? "",
        start_date: record.start_date ?? "", completion_date: record.completion_date ?? "", scope_summary: record.scope_summary ?? "",
        defects_period_months: record.defects_period_months?.toString() ?? "",
        ld_amount: record.liquidated_damages_amount ?? "", ld_period: record.liquidated_damages_period ?? "",
        bond_percent: record.bond_percent ? formatDecimal(record.bond_percent) : "", insurance_notes: record.insurance_notes ?? "",
        exclusions: record.exclusions ?? "",
      });
      setBond(!!record.bond_required);
      setError(null);
    }
  }, [open, record, isPrime]);
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setV({ ...v, [k]: e.target.value });
  const n = (s: string | undefined) => (s && s.trim() ? s.trim() : null);
  const save = async () => {
    setError(null);
    for (const [k, label] of [["retention_percent", t.retainage], ["bond_percent", "Bond %"]] as const) {
      const e = decimalError(v[k] ?? "", 2, { max: "100", label });
      if (e) return setError(`${label}: ${e}`);
    }
    if (v.start_date && v.completion_date && v.completion_date < v.start_date) return setError("Completion date must be on or after the start date");
    const ld = n(v.ld_amount) ? parseMoneyInput(v.ld_amount!) : null;
    if (n(v.ld_amount) && ld === null) return setError("Liquidated damages: enter an amount with up to 2 decimals");
    if (!!ld !== !!n(v.ld_period)) return setError("Give both the liquidated damages amount and its period");
    const body: Record<string, unknown> = {
      version: record.version, title: v.title?.trim(), contract_form: v.contract_form,
      retention_percent: n(v.retention_percent) ? clean(v.retention_percent!) : null, retention_terms: n(v.retention_terms),
      payment_terms_days: n(v.payment_terms_days) ? Number.parseInt(v.payment_terms_days!, 10) : null,
      start_date: n(v.start_date), completion_date: n(v.completion_date), scope_summary: n(v.scope_summary),
    };
    if (isPrime) Object.assign(body, {
      client_company_id: n(v.party), defects_period_months: n(v.defects_period_months) ? Number.parseInt(v.defects_period_months!, 10) : null,
      liquidated_damages_amount: ld, liquidated_damages_period: n(v.ld_period), bond_required: bond,
      bond_percent: bond && n(v.bond_percent) ? clean(v.bond_percent!) : null, insurance_notes: n(v.insurance_notes),
    });
    else Object.assign(body, { vendor_company_id: v.party, exclusions: n(v.exclusions) });
    setBusy(true);
    try {
      onSaved(await api<ContractRecord>(`/${kind}/${record.id}`, { method: "PATCH", body }));
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof ApiError && err.code === "version_conflict" ? "Someone else changed this record. Close and reload to see their changes." : msg(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange} wide title="Edit terms"
      footer={<><Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={busy} onClick={save}>Save terms</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        {error && <Alert tone="danger" className="sm:col-span-2">{error}</Alert>}
        <Field label="Title" required className="sm:col-span-2">{(p) => <Input {...p} value={v.title ?? ""} onChange={set("title")} maxLength={200} />}</Field>
        <Field label="Contract form" required>{(p) => <Select {...p} value={v.contract_form ?? ""} onChange={set("contract_form")}><Options map={isPrime ? vocab?.prime_forms : vocab?.subcontract_forms} /></Select>}</Field>
        <Field label={isPrime ? "Client / employer" : "Subcontractor / supplier"} required={!isPrime}>{(p) => <Select {...p} value={v.party ?? ""} onChange={set("party")}>{isPrime && <option value="">Not set</option>}{companies.data?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>}</Field>
        <Field label={`${t.retainage} %`}>{(p) => <Input {...p} value={v.retention_percent ?? ""} onChange={set("retention_percent")} inputMode="decimal" className="num" />}</Field>
        <Field label="Payment terms (days)">{(p) => <Input {...p} value={v.payment_terms_days ?? ""} onChange={set("payment_terms_days")} inputMode="numeric" />}</Field>
        <Field label={`${t.retainage} release terms`} className="sm:col-span-2">{(p) => <Input {...p} value={v.retention_terms ?? ""} onChange={set("retention_terms")} placeholder={t.retainage === "Retention" ? "Half at practical completion, half at end of rectification period" : "Reduce to 5% at 50% complete; release at final completion"} />}</Field>
        <Field label="Start date">{(p) => <Input {...p} type="date" value={v.start_date ?? ""} onChange={set("start_date")} />}</Field>
        <Field label="Completion date">{(p) => <Input {...p} type="date" value={v.completion_date ?? ""} onChange={set("completion_date")} />}</Field>
        {isPrime && (
          <>
            <Field label={t.retainage === "Retention" ? "Rectification / defects period (months)" : "Warranty period (months)"}>{(p) => <Input {...p} value={v.defects_period_months ?? ""} onChange={set("defects_period_months")} inputMode="numeric" />}</Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Liquidated damages">{(p) => <Input {...p} value={v.ld_amount ?? ""} onChange={set("ld_amount")} inputMode="decimal" className="num" />}</Field>
              <Field label="Per">{(p) => <Select {...p} value={v.ld_period ?? ""} onChange={set("ld_period")}><option value="">—</option><option value="day">day</option><option value="week">week</option></Select>}</Field>
            </div>
            <Checkbox label="Performance bond required" checked={bond} onChange={(e) => setBond(e.target.checked)} />
            {bond && <Field label="Bond % of contract sum">{(p) => <Input {...p} value={v.bond_percent ?? ""} onChange={set("bond_percent")} inputMode="decimal" className="num" />}</Field>}
            <Field label="Insurance requirements" className="sm:col-span-2">{(p) => <Textarea {...p} value={v.insurance_notes ?? ""} onChange={set("insurance_notes")} rows={2} />}</Field>
          </>
        )}
        <Field label="Scope summary" className="sm:col-span-2">{(p) => <Textarea {...p} value={v.scope_summary ?? ""} onChange={set("scope_summary")} rows={3} />}</Field>
        {!isPrime && <Field label="Exclusions" className="sm:col-span-2">{(p) => <Textarea {...p} value={v.exclusions ?? ""} onChange={set("exclusions")} rows={3} />}</Field>}
      </div>
    </Dialog>
  );
}

export function ContractDetail({ kind, id }: { kind: ContractKind; id: string }) {
  const router = useRouter();
  const qc = useQueryClient();
  const { notify } = useToast();
  const vocab = useContractVocab().data;
  const t = terms();
  const isPrime = kind === "contracts";
  const { can } = useAuth();
  const [lineOpen, setLineOpen] = useState(false);
  const [editingLine, setEditingLine] = useState<ContractLineItem | null>(null);
  const [termsOpen, setTermsOpen] = useState(false);
  const [execOpen, setExecOpen] = useState(false);
  const [execDate, setExecDate] = useState(today());
  const [execError, setExecError] = useState<string | null>(null);
  const q = useQuery({ queryKey: [kind, "detail", id], queryFn: () => api<ContractRecord>(`/${kind}/${id}`) });
  const codes = useQuery({ queryKey: ["cost-codes", q.data?.cost_code_set_id, false], queryFn: () => api<CostCode[]>(`/cost-code-sets/${q.data!.cost_code_set_id}/codes`), enabled: !!q.data?.cost_code_set_id && q.data.is_editable });
  const apply = (r: ContractRecord) => {
    qc.setQueryData([kind, "detail", id], r);
    void qc.invalidateQueries({ queryKey: [kind], exact: false, predicate: (qq) => qq.queryKey[1] !== "detail" });
    void qc.invalidateQueries({ queryKey: ["project", r.project_id, "summary"] });
    void qc.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const lifecycle = useMutation({
    mutationFn: (v: { action: "execute" | "close" | "void"; body: Record<string, unknown> }) => api<ContractRecord>(`/${kind}/${id}/${v.action}`, { method: "POST", body: v.body }),
    onSuccess: (r) => { apply(r); setExecOpen(false); notify(`${r.number} ${r.status}`); },
    onError: (err) => { setExecError(msg(err)); notify(msg(err), "danger"); },
  });
  const removeLine = useMutation({ mutationFn: (lineId: string) => api<ContractRecord>(`/${kind}/${id}/lines/${lineId}`, { method: "DELETE" }), onSuccess: (r) => { apply(r); notify("Line deleted"); }, onError: (err) => notify(msg(err), "danger") });
  const remove = useMutation({ mutationFn: () => api(`/${kind}/${id}`, { method: "DELETE" }), onSuccess: () => { void qc.invalidateQueries({ queryKey: [kind] }); notify("Draft deleted"); router.push(isPrime ? "/contracts" : "/subcontracts"); }, onError: (err) => notify(msg(err), "danger") });

  if (q.isLoading) return <Spinner />;
  if (q.error instanceof ApiError && [403, 404].includes(q.error.status)) return <EmptyState title="Not available" description="It may not exist, or you may not have access to it." action={<Link href={isPrime ? "/contracts" : "/subcontracts"} className="text-accent hover:underline">Back</Link>} />;
  if (q.error || !q.data) return <ErrorState error={q.error} />;
  const r = q.data;
  const c = r.currency;
  const forms = isPrime ? vocab?.prime_forms : vocab?.subcontract_forms;
  const party = isPrime ? r.client_company : r.vendor;
  const measured = r.lines.some((l) => l.quantity);

  return (
    <>
      <PageHeader
        breadcrumb={<><Link href={isPrime ? "/contracts" : "/subcontracts"} className="hover:underline">{isPrime ? "Contracts" : "Subcontracts & POs"}</Link> / <Link href={`/projects/${r.project_id}`} className="hover:underline">{r.project_number} {r.project_name}</Link></>}
        title={<span className="flex flex-wrap items-center gap-3"><span className="num">{r.number}</span> {r.title}<Badge tone={STATUS_TONES[r.status]}>{vocab?.statuses[r.status] ?? r.status}</Badge></span>}
        description={`${forms?.[r.contract_form] ?? r.contract_form}${party ? ` · ${party.name}` : ""}`}
        actions={
          <>
            {r.is_editable && <ConfirmButton size="md" label={<><Trash2 className="size-4" />Delete draft</>} title={`Delete draft ${r.number}?`} description="Only drafts can be deleted." confirmLabel="Delete" onConfirm={() => remove.mutateAsync()} />}
            {r.status === "draft" && r.can_execute && <ConfirmButton size="md" label={<><Ban className="size-4" />Void</>} title={`Void ${r.number}?`} description="A voided draft is kept for the record but can no longer be executed." confirmLabel="Void" onConfirm={() => lifecycle.mutateAsync({ action: "void", body: { version: r.version } })} />}
            {r.is_editable && <Button variant="secondary" onClick={() => setTermsOpen(true)}><Pencil className="size-4" />Edit terms</Button>}
            {r.status === "draft" && r.can_execute && <Button onClick={() => { setExecError(null); setExecDate(today()); setExecOpen(true); }}><CheckCircle2 className="size-4" />Execute</Button>}
            {r.status === "executed" && r.can_execute && <ConfirmButton size="md" buttonVariant="secondary" variant="primary" label={<><Archive className="size-4" />Close</>} title={`Close ${r.number}?`} description="Mark the contract as complete. Its terms stay locked." confirmLabel="Close" onConfirm={() => lifecycle.mutateAsync({ action: "close", body: { version: r.version } })} />}
          </>
        }
      />
      {r.status !== "draft" && r.status !== "void" && <Alert tone="info" className="mb-4" title="Terms and lines are locked">Executed {formatDate(r.executed_date)}. Changes to the contract sum are made through change orders.</Alert>}
      <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
        <Card className="min-w-0">
          <CardHeader title={isPrime ? "Contract sum analysis" : "Committed scope"} actions={r.is_editable && <Button size="sm" onClick={() => { setEditingLine(null); setLineOpen(true); }}><Plus className="size-4" />Add line</Button>} />
          {r.lines.length === 0 ? <EmptyState title="No lines yet" description="Break the sum down by cost code so it can be tracked against the budget." /> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <caption className="sr-only">Lines</caption>
                <thead><tr className="border-b border-border bg-surface-2/60 text-left text-xs font-semibold uppercase tracking-wide text-subtle">
                  <th className="px-4 py-2.5">Code</th><th className="px-4 py-2.5">Description</th>
                  {measured && <><th className="px-4 py-2.5 text-right">Qty</th><th className="px-4 py-2.5">Unit</th><th className="px-4 py-2.5 text-right">Rate</th></>}
                  <th className="px-4 py-2.5 text-right">Amount</th>{r.is_editable && <th><span className="sr-only">Actions</span></th>}
                </tr></thead>
                <tbody>
                  {r.lines.map((l) => (
                    <tr key={l.id} className="border-b border-border">
                      <td className="px-4 py-2.5 font-mono text-xs">{l.cost_code?.code ?? "—"}</td>
                      <td className="px-4 py-2.5">{l.description}</td>
                      {measured && <><td className="num px-4 py-2.5 text-right">{l.quantity ? formatDecimal(l.quantity) : ""}</td><td className="px-4 py-2.5">{l.unit ?? ""}</td><td className="num px-4 py-2.5 text-right">{l.unit_rate ? formatDecimal(l.unit_rate, 2) : ""}</td></>}
                      <td className="num px-4 py-2.5 text-right">{formatMoney(l.amount, c)}</td>
                      {r.is_editable && <td className="whitespace-nowrap px-2 text-right"><Button size="sm" variant="ghost" onClick={() => { setEditingLine(l); setLineOpen(true); }}>Edit</Button><ConfirmButton label={<Trash2 className="size-4" />} buttonVariant="ghost" title="Delete this line?" description={l.description} confirmLabel="Delete" onConfirm={() => removeLine.mutateAsync(l.id)} /></td>}
                    </tr>
                  ))}
                  <tr className="font-semibold"><td className="px-4 py-3" colSpan={measured ? 5 : 2}>Total</td><td className="num px-4 py-3 text-right">{formatMoney(r.current_total, c)}</td>{r.is_editable && <td />}</tr>
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader title="Value" actions={r.status !== "draft" && <Lock className="size-4 text-subtle" aria-label="Locked" />} />
            <CardBody>
              {r.original_sum ? (
                <dl className="num space-y-1.5 text-sm">
                  <div className="flex justify-between text-muted"><dt>Original {isPrime ? "contract sum" : "value"}</dt><dd>{formatMoney(r.original_sum, c)}</dd></div>
                  <div className="flex justify-between text-muted"><dt>Approved changes</dt><dd>{formatMoney(r.approved_changes, c)}</dd></div>
                  <div className="flex justify-between border-t border-border pt-2 text-lg font-semibold"><dt>Revised</dt><dd>{formatMoney(r.revised_sum, c)}</dd></div>
                  {r.pending_changes !== "0.00" && <div className="flex justify-between text-xs text-subtle"><dt>Pending changes</dt><dd>{formatMoney(r.pending_changes, c)}</dd></div>}
                  <p className="pt-1 text-xs font-sans text-subtle">Original fixed at execution; revised = original + approved changes.</p>
                </dl>
              ) : (
                <>
                  <p className="num text-2xl font-semibold">{formatMoney(r.current_total, c)}</p>
                  <p className="mt-1 text-xs text-subtle">Draft total — fixed when executed</p>
                </>
              )}
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Terms" />
            <CardBody>
              <DescriptionList columns={1} items={[
                ...(isPrime ? [] : [{ label: "Type", value: vocab?.commitment_types[r.commitment_type ?? ""] ?? "—" }]),
                { label: t.retainage, value: r.retention_percent ? `${formatPercent(r.retention_percent)}${r.retention_terms ? ` — ${r.retention_terms}` : ""}` : "None" },
                { label: "Payment terms", value: r.payment_terms_days !== null ? `${r.payment_terms_days} days` : "—" },
                { label: "Dates", value: r.start_date || r.completion_date ? `${formatDate(r.start_date)} – ${formatDate(r.completion_date)}` : "—" },
                ...(isPrime ? [
                  { label: t.retainage === "Retention" ? "Rectification period" : "Warranty period", value: r.defects_period_months ? `${r.defects_period_months} months` : "—" },
                  { label: "Liquidated damages", value: r.liquidated_damages_amount ? `${formatMoney(r.liquidated_damages_amount, c)} per ${r.liquidated_damages_period}` : "—" },
                  { label: "Bond", value: r.bond_required ? `Required${r.bond_percent ? ` (${formatPercent(r.bond_percent)})` : ""}` : "Not required" },
                  ...(r.insurance_notes ? [{ label: "Insurance", value: r.insurance_notes }] : []),
                ] : []),
                ...(r.scope_summary ? [{ label: "Scope", value: <span className="whitespace-pre-wrap">{r.scope_summary}</span> }] : []),
                ...(!isPrime && r.exclusions ? [{ label: "Exclusions", value: <span className="whitespace-pre-wrap">{r.exclusions}</span> }] : []),
              ]} />
            </CardBody>
          </Card>
        </div>
      </div>
      {(r.status === "executed" || r.status === "closed") && can(P.CHANGES_VIEW) && (
        <Card className="mt-6">
          <CardHeader title={terms().retainage === "Retention" ? "Variations" : "Change orders"} description="Approved changes revise the value above" />
          <ChangeOrdersList
            contractId={isPrime ? r.id : undefined}
            commitmentId={isPrime ? undefined : r.id}
            canCreate={r.status === "executed"}
            target={{ type: isPrime ? "contract" : "commitment", id: r.id, label: `${r.number} ${r.title}` }}
          />
        </Card>
      )}
      <LineDialog kind={kind} record={r} line={editingLine} open={lineOpen} onOpenChange={setLineOpen} codes={codes.data ?? []} onSaved={(x) => { apply(x); notify(editingLine ? "Line saved" : "Line added"); }} />
      <TermsDialog kind={kind} record={r} open={termsOpen} onOpenChange={setTermsOpen} onSaved={(x) => { apply(x); notify("Terms saved"); }} />
      <Dialog open={execOpen} onOpenChange={setExecOpen} title={`Execute ${r.number}`} description={`Records the signed ${isPrime ? "contract sum" : "commitment value"} of ${formatMoney(r.current_total, c)} and locks terms and lines.`}
        footer={<><Button variant="secondary" onClick={() => setExecOpen(false)}>Cancel</Button><Button loading={lifecycle.isPending} onClick={() => { setExecError(null); if (!execDate) return setExecError("Enter the date it was signed"); lifecycle.mutate({ action: "execute", body: { executed_date: execDate, version: r.version } }); }}>Execute</Button></>}>
        <div className="space-y-4">
          {execError && <Alert tone="danger">{execError}</Alert>}
          <Field label="Date signed" required>{(p) => <Input {...p} type="date" max={today()} value={execDate} onChange={(e) => setExecDate(e.target.value)} />}</Field>
        </div>
      </Dialog>
    </>
  );
}
