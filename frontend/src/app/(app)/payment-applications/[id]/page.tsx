"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Banknote, Send, Trash2, Undo2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PayStatus } from "@/components/domain/payment-applications";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, DescriptionList } from "@/components/ui/card";
import { ConfirmButton, Dialog } from "@/components/ui/dialog";
import { Alert, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input, Textarea } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { decimalError } from "@/lib/decimal";
import { formatDate, formatDateTime, P } from "@/lib/hooks";
import { formatMoney, formatPercent } from "@/lib/money";
import { region, terms } from "@/lib/region";
import type { PaymentApplicationDetail, PaymentLine, Project } from "@/lib/types";

const msg = (err: unknown) => (err instanceof ApiError ? err.message : "Something went wrong");
const SIGNED = /^-?\d+(\.\d{1,2})?$/;
const strip = (v: string) => v.trim().replace(/,/g, "");
const today = () => new Date().toISOString().slice(0, 10);

function LineDialog({ a, line, onSaved, onClose }: { a: PaymentApplicationDetail; line: PaymentLine | null; onSaved: (x: PaymentApplicationDetail) => void; onClose: () => void }) {
  const [mode, setMode] = useState<"amount" | "percent">("amount");
  const [amount, setAmount] = useState("");
  const [percent, setPercent] = useState("");
  const [stored, setStored] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (line) { setMode("amount"); setAmount(line.this_period); setPercent(line.percent_complete ?? ""); setStored(line.materials_stored); setError(null); }
  }, [line]);
  const c = a.currency;
  const save = async () => {
    setError(null);
    const body: Record<string, string> = {};
    if (mode === "amount") {
      if (!SIGNED.test(strip(amount))) return setError("Enter the amount for this period (up to 2 decimals; negative to correct an earlier claim)");
      body.this_period = strip(amount);
    } else {
      const e = decimalError(percent, 2, { required: true, max: "100", label: "Percent complete" });
      if (e) return setError(e);
      body.percent_to_date = strip(percent);
    }
    if (strip(stored) !== "") {
      if (!SIGNED.test(strip(stored))) return setError("Materials stored: up to 2 decimals");
      body.materials_stored = strip(stored);
    }
    setBusy(true);
    try {
      onSaved(await api<PaymentApplicationDetail>(`/payment-applications/${a.id}/lines/${line!.id}`, { method: "PUT", body }));
      onClose();
    } catch (err) {
      setError(msg(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={!!line} onOpenChange={(o) => !o && onClose()} title={line ? `${line.item} — ${line.description}` : ""}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={save}>Save</Button></>}>
      {line && (
        <div className="space-y-4">
          {error && <Alert tone="danger">{error}</Alert>}
          <dl className="num grid grid-cols-3 gap-3 rounded-md bg-surface-2 p-3 text-sm">
            <div><dt className="text-xs text-subtle">Scheduled value</dt><dd>{formatMoney(line.scheduled_value, c)}</dd></div>
            <div><dt className="text-xs text-subtle">Previous work</dt><dd>{formatMoney(line.previous_work, c)}</dd></div>
            <div><dt className="text-xs text-subtle">Balance to finish</dt><dd>{formatMoney(line.balance_to_finish, c)}</dd></div>
          </dl>
          <div role="radiogroup" aria-label="Claim by" className="flex gap-2">
            {(["amount", "percent"] as const).map((m) => (
              <button key={m} type="button" role="radio" aria-checked={mode === m} onClick={() => setMode(m)}
                className={cn("rounded-md border px-3 py-1.5 text-sm", mode === m ? "border-accent bg-accent-soft text-accent" : "border-border text-muted hover:bg-surface-2")}>
                {m === "amount" ? "Amount this period" : "Percent complete to date"}
              </button>
            ))}
          </div>
          {mode === "amount"
            ? <Field label={`Work this period (${c})`} hint="Negative corrects an earlier over-claim" required>{(p) => <Input {...p} value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" className="num" />}</Field>
            : <Field label="Percent complete to date" hint="Includes materials stored. The server works out this period's amount." required>{(p) => <Input {...p} value={percent} onChange={(e) => setPercent(e.target.value)} inputMode="decimal" className="num" placeholder="e.g. 45" />}</Field>}
          <Field label={`Materials presently stored (${c})`} hint="On site or off site, not yet installed. A balance — reduce it as materials are built in.">{(p) => <Input {...p} value={stored} onChange={(e) => setStored(e.target.value)} inputMode="decimal" className="num" />}</Field>
        </div>
      )}
    </Dialog>
  );
}

function HeaderForm({ a, onSaved }: { a: PaymentApplicationDetail; onSaved: (x: PaymentApplicationDetail) => void }) {
  const { notify } = useToast();
  const uk = region() === "GB";
  const [f, setF] = useState({ period_to: "", application_date: "", due_date: "", final_payment_date: "", pay_less_notice_date: "", retention_percent: "", notes: "" });
  useEffect(() => {
    setF({ period_to: a.period_to, application_date: a.application_date, due_date: a.due_date ?? "", final_payment_date: a.final_payment_date ?? "", pay_less_notice_date: a.pay_less_notice_date ?? "", retention_percent: a.retention_percent, notes: a.notes ?? "" });
  }, [a.id, a.version]); // eslint-disable-line react-hooks/exhaustive-deps
  const save = useMutation({
    mutationFn: () => api<PaymentApplicationDetail>(`/payment-applications/${a.id}`, { method: "PATCH", body: {
      version: a.version, period_to: f.period_to, application_date: f.application_date, due_date: f.due_date || null,
      final_payment_date: f.final_payment_date || null, pay_less_notice_date: f.pay_less_notice_date || null,
      retention_percent: strip(f.retention_percent), notes: f.notes.trim() || null,
    } }),
    onSuccess: (x) => { onSaved(x); notify("Details saved"); },
    onError: (err) => notify(msg(err), "danger"),
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const retErr = decimalError(f.retention_percent, 2, { required: true, max: "100", label: terms().retainage });
  return (
    <CardBody className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label={uk ? "Valuation date" : "Period to"} required>{(p) => <Input {...p} type="date" value={f.period_to} onChange={set("period_to")} />}</Field>
        <Field label="Application date" required>{(p) => <Input {...p} type="date" value={f.application_date} max={today()} onChange={set("application_date")} />}</Field>
        <Field label={`${terms().retainage} %`} error={f.retention_percent ? retErr : undefined} required>{(p) => <Input {...p} value={f.retention_percent} onChange={set("retention_percent")} inputMode="decimal" className="num" />}</Field>
        <Field label="Due date">{(p) => <Input {...p} type="date" value={f.due_date} onChange={set("due_date")} />}</Field>
        {(uk || f.final_payment_date) && <Field label="Final date for payment">{(p) => <Input {...p} type="date" value={f.final_payment_date} onChange={set("final_payment_date")} />}</Field>}
        {(uk || f.pay_less_notice_date) && <Field label="Pay-less notice by" hint="Defaults to 5 days before the final date (JCT); check your contract">{(p) => <Input {...p} type="date" value={f.pay_less_notice_date} onChange={set("pay_less_notice_date")} />}</Field>}
      </div>
      <Field label="Notes">{(p) => <Textarea {...p} rows={2} value={f.notes} onChange={set("notes")} maxLength={5000} />}</Field>
      <div className="flex justify-end"><Button variant="secondary" loading={save.isPending} disabled={!!retErr} onClick={() => save.mutate()}>Save details</Button></div>
    </CardBody>
  );
}

function CertifyDialog({ a, open, onClose, onSaved }: { a: PaymentApplicationDetail; open: boolean; onClose: () => void; onSaved: (x: PaymentApplicationDetail) => void }) {
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today());
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (open) { setAmount(a.amount_due ?? ""); setDate(today()); setNote(""); setError(null); } }, [open, a.amount_due]);
  const m = useMutation({
    mutationFn: () => api<PaymentApplicationDetail>(`/payment-applications/${a.id}/certify`, { method: "POST", body: { version: a.version, certified_amount: strip(amount), certified_date: date, certification_note: note.trim() || null } }),
    onSuccess: (x) => { onSaved(x); onClose(); },
    onError: (err) => setError(msg(err)),
  });
  const differs = strip(amount) !== a.amount_due;
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()} title="Record certificate" description="Enter what the architect / contract administrator certified for payment."
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={m.isPending} onClick={() => {
        setError(null);
        if (!SIGNED.test(strip(amount))) return setError("Enter the certified amount (up to 2 decimals)");
        if (differs && !note.trim()) return setError("Explain why the certified amount differs from the amount applied for");
        m.mutate();
      }}>Record certificate</Button></>}>
      <div className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <p className="text-sm text-muted">Applied for <span className="num font-medium text-fg">{formatMoney(a.amount_due, a.currency)}</span>. Anything not certified is claimed again automatically on the next application.</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={`Certified amount (${a.currency})`} required>{(p) => <Input {...p} value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" className="num" />}</Field>
          <Field label="Certificate date" required>{(p) => <Input {...p} type="date" value={date} max={today()} onChange={(e) => setDate(e.target.value)} />}</Field>
        </div>
        <Field label="Reason for any difference" required={differs}>{(p) => <Textarea {...p} rows={2} value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} placeholder="e.g. stored materials not verified" />}</Field>
      </div>
    </Dialog>
  );
}

function PaymentDialog({ a, open, onClose, onSaved }: { a: PaymentApplicationDetail; open: boolean; onClose: () => void; onSaved: (x: PaymentApplicationDetail) => void }) {
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today());
  const [ref, setRef] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (open) { setAmount(a.certified_amount ?? ""); setDate(today()); setRef(""); setError(null); } }, [open, a.certified_amount]);
  const m = useMutation({
    mutationFn: () => api<PaymentApplicationDetail>(`/payment-applications/${a.id}/payment`, { method: "POST", body: { version: a.version, paid_amount: strip(amount), paid_date: date, payment_reference: ref.trim() || null } }),
    onSuccess: (x) => { onSaved(x); onClose(); },
    onError: (err) => setError(msg(err)),
  });
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()} title="Record payment received" description="After this the application is final."
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={m.isPending} onClick={() => {
        setError(null);
        const e = decimalError(amount, 2, { required: true, label: "Amount received" });
        if (e) return setError(e);
        m.mutate();
      }}>Record payment</Button></>}>
      <div className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <p className="text-sm text-muted">Certified <span className="num font-medium text-fg">{formatMoney(a.certified_amount, a.currency)}</span>. A short payment stays as outstanding.</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={`Amount received (${a.currency})`} required>{(p) => <Input {...p} value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" className="num" />}</Field>
          <Field label="Date received" required>{(p) => <Input {...p} type="date" value={date} max={today()} onChange={(e) => setDate(e.target.value)} />}</Field>
        </div>
        <Field label="Payment reference">{(p) => <Input {...p} value={ref} onChange={(e) => setRef(e.target.value)} maxLength={80} placeholder="e.g. BACS 7781 / check 10432" />}</Field>
      </div>
    </Dialog>
  );
}

function SummaryTable({ a }: { a: PaymentApplicationDetail }) {
  const t = a.totals;
  const c = a.currency;
  const ret = terms().retainage;
  const rows: [string, string, string, boolean?][] = [
    ["1", "Original contract sum", t.original_sum],
    ["2", "Net change by approved changes", t.net_changes],
    ["3", "Contract sum to date (1 + 2)", t.contract_sum_to_date, true],
    ["4", `Total completed and stored to date${t.percent_complete ? ` (${formatPercent(t.percent_complete)})` : ""}`, t.completed_to_date],
    ["5", `${ret} (${formatPercent(a.retention_percent)})`, t.retention],
    ["6", `Total earned less ${ret.toLowerCase()} (4 − 5)`, t.earned_less_retention],
    ["7", "Less previous certificates for payment", t.previous_certified],
    ["8", "Current payment due (6 − 7)", t.amount_due, true],
    ["9", `Balance to finish, including ${ret.toLowerCase()} (3 − 6)`, t.balance_to_finish],
  ];
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">Application summary</caption>
      <tbody className="num">
        {rows.map(([n, l, v, strong]) => (
          <tr key={n} className={cn("border-b border-border last:border-0", strong && "font-semibold")}>
            <td className="w-10 px-5 py-2.5 font-mono text-xs text-subtle">{n}</td>
            <td className="px-2 py-2.5 font-sans">{l}</td>
            <td className={cn("px-5 py-2.5 text-right", n === "8" && "text-base")}>{formatMoney(v, c)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function PaymentApplicationPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const { can } = useAuth();
  const { notify } = useToast();
  const [editing, setEditing] = useState<PaymentLine | null>(null);
  const [certifying, setCertifying] = useState(false);
  const [paying, setPaying] = useState(false);
  const q = useQuery({ queryKey: ["payment-application", id], queryFn: () => api<PaymentApplicationDetail>(`/payment-applications/${id}`) });
  const project = useQuery({ queryKey: ["project", q.data?.project_id], queryFn: () => api<Project>(`/projects/${q.data!.project_id}`), enabled: !!q.data });
  const apply = (x: PaymentApplicationDetail) => {
    qc.setQueryData(["payment-application", id], x);
    void qc.invalidateQueries({ queryKey: ["payment-applications", x.project_id] });
    void qc.invalidateQueries({ queryKey: ["billing-summary", x.project_id] });
    void qc.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const action = (path: string, done: string) => async () => {
    try {
      apply(await api<PaymentApplicationDetail>(`/payment-applications/${id}/${path}`, { method: "POST", body: { version: q.data!.version } }));
      notify(done);
    } catch (err) {
      notify(msg(err), "danger");
      if (err instanceof ApiError && err.code === "schedule_changed") void q.refetch();
    }
  };
  const remove = async () => {
    try {
      await api(`/payment-applications/${id}`, { method: "DELETE" });
      notify("Draft deleted");
      router.push(`/projects/${q.data!.project_id}?tab=payments`);
    } catch (err) {
      notify(msg(err), "danger");
    }
  };
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorState error={q.error} />;
  const a = q.data;
  const c = a.currency;
  const uk = region() === "GB";
  return (
    <>
      <PageHeader
        breadcrumb={<Link href={`/projects/${a.project_id}?tab=payments`} className="hover:underline">{project.data ? `${project.data.number} ${project.data.name}` : "Project"}</Link>}
        title={<span className="flex flex-wrap items-center gap-3">{a.label}<PayStatus a={a} /></span>}
        description={`${a.contract_number} ${a.contract_title} · ${uk ? "valuation date" : "period to"} ${formatDate(a.period_to)}`}
        actions={
          <div className="flex flex-wrap gap-2">
            {a.is_editable && <ConfirmButton size="md" label={<><Trash2 className="size-4" />Delete draft</>} title="Delete this draft?" description="Submitted applications cannot be deleted." confirmLabel="Delete" onConfirm={remove} />}
            {a.status === "submitted" && can(P.PAYMENTS_EDIT) && <ConfirmButton size="md" buttonVariant="secondary" variant="primary" label={<><Undo2 className="size-4" />Return to draft</>} title="Return to draft?" description="Use this to correct the application before it is certified." confirmLabel="Return to draft" onConfirm={action("return-to-draft", "Returned to draft")} />}
            {a.is_editable && <ConfirmButton size="md" buttonVariant="primary" variant="primary" label={<><Send className="size-4" />Submit</>} title={`Submit ${a.label}?`} description={`Applying for ${formatMoney(a.totals.amount_due, c)}. The claim is locked once submitted.`} confirmLabel="Submit" onConfirm={action("submit", "Submitted")} />}
            {a.status === "submitted" && a.can_certify && <Button onClick={() => setCertifying(true)}><BadgeCheck className="size-4" />Record certificate</Button>}
            {a.status === "certified" && a.can_certify && <Button onClick={() => setPaying(true)}><Banknote className="size-4" />Record payment</Button>}
          </div>
        }
      />
      <div className="space-y-6">
        {a.is_overdue && <Alert tone="danger" title="Payment is overdue">The final date for payment was {formatDate(a.final_payment_date ?? a.due_date)}.</Alert>}
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <Card>
            <CardHeader title="Summary" description={a.status === "draft" ? "Live figures — locked when submitted" : `Submitted ${formatDateTime(a.submitted_at)}`} />
            <SummaryTable a={a} />
          </Card>
          <Card>
            <CardHeader title="Dates and terms" />
            {a.is_editable ? <HeaderForm a={a} onSaved={apply} /> : (
              <CardBody>
                <DescriptionList columns={2} items={[
                  { label: "Application date", value: formatDate(a.application_date) },
                  { label: "Due date", value: formatDate(a.due_date) },
                  ...(a.final_payment_date || uk ? [{ label: "Final date for payment", value: formatDate(a.final_payment_date) }] : []),
                  ...(a.pay_less_notice_date || uk ? [{ label: "Pay-less notice by", value: formatDate(a.pay_less_notice_date) }] : []),
                  { label: `${terms().retainage} %`, value: formatPercent(a.retention_percent) },
                  ...(a.certified_amount ? [{ label: "Certified", value: <span className="num">{formatMoney(a.certified_amount, c)} on {formatDate(a.certified_date)}</span> }] : []),
                  ...(a.certification_note ? [{ label: "Certifier's note", value: a.certification_note }] : []),
                  ...(a.paid_amount ? [{ label: "Paid", value: <span className="num">{formatMoney(a.paid_amount, c)} on {formatDate(a.paid_date)}{a.payment_reference ? ` · ${a.payment_reference}` : ""}</span> }] : []),
                  ...(a.outstanding !== "0.00" ? [{ label: "Outstanding", value: <span className="num text-danger">{formatMoney(a.outstanding, c)}</span> }] : []),
                  ...(a.notes ? [{ label: "Notes", value: a.notes }] : []),
                ]} />
              </CardBody>
            )}
          </Card>
        </div>
        <Card>
          <CardHeader title="Schedule of values" description={a.is_editable ? "Select a line to claim work done this period. Approved changes are added automatically." : "Locked"} />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Schedule of values</caption>
              <thead><tr className="border-b border-border bg-surface-2/60 text-left text-xs font-semibold uppercase tracking-wide text-subtle">
                <th className="px-4 py-2.5">Item</th><th className="px-4 py-2.5">Description</th><th className="px-4 py-2.5 text-right">Scheduled value</th><th className="px-4 py-2.5 text-right">Previous</th><th className="px-4 py-2.5 text-right">This period</th><th className="px-4 py-2.5 text-right">Stored</th><th className="px-4 py-2.5 text-right">Completed &amp; stored</th><th className="px-4 py-2.5 text-right">%</th><th className="px-4 py-2.5 text-right">Balance</th><th className="px-4 py-2.5 text-right">{terms().retainage}</th>
              </tr></thead>
              <tbody className="num">
                {a.lines.map((l) => (
                  <tr key={l.id} className={cn("border-b border-border", a.is_editable && "cursor-pointer hover:bg-surface-2/70")} onClick={a.is_editable ? () => setEditing(l) : undefined}
                    tabIndex={a.is_editable ? 0 : undefined} onKeyDown={a.is_editable ? (e) => { if (e.key === "Enter") setEditing(l); } : undefined} aria-label={a.is_editable ? `Edit ${l.item} ${l.description}` : undefined}>
                    <td className="px-4 py-2.5 font-mono text-xs">{l.item}</td>
                    <td className="px-4 py-2.5 font-sans">{l.description}{l.source === "change_order" && <span className="ml-2 text-xs text-subtle">approved change</span>}</td>
                    <td className="px-4 py-2.5 text-right">{formatMoney(l.scheduled_value, c)}</td>
                    <td className="px-4 py-2.5 text-right">{formatMoney(l.previous_work, c)}</td>
                    <td className={cn("px-4 py-2.5 text-right", l.this_period !== "0.00" && "font-medium text-fg")}>{formatMoney(l.this_period, c)}</td>
                    <td className="px-4 py-2.5 text-right">{formatMoney(l.materials_stored, c)}</td>
                    <td className="px-4 py-2.5 text-right">{formatMoney(l.completed_to_date, c)}</td>
                    <td className="px-4 py-2.5 text-right">{l.percent_complete ? formatPercent(l.percent_complete) : "—"}</td>
                    <td className="px-4 py-2.5 text-right">{formatMoney(l.balance_to_finish, c)}</td>
                    <td className="px-4 py-2.5 text-right">{formatMoney(l.retention, c)}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-border-strong font-semibold">
                  <td className="px-4 py-3 font-sans" colSpan={2}>Total</td>
                  <td className="px-4 py-3 text-right">{formatMoney(a.totals.contract_sum_to_date, c)}</td>
                  <td className="px-4 py-3" colSpan={3} />
                  <td className="px-4 py-3 text-right">{formatMoney(a.totals.completed_to_date, c)}</td>
                  <td className="px-4 py-3 text-right">{a.totals.percent_complete ? formatPercent(a.totals.percent_complete) : "—"}</td>
                  <td className="px-4 py-3" />
                  <td className="px-4 py-3 text-right">{formatMoney(a.totals.retention, c)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Card>
        <p className="text-xs text-subtle">Figures follow the familiar G702/G703 layout for reference; this is not an AIA document. {terms().retainage} is calculated per line and rounded once, so the lines add up to the total.</p>
      </div>
      <LineDialog a={a} line={editing} onSaved={(x) => { apply(x); notify("Line updated"); }} onClose={() => setEditing(null)} />
      <CertifyDialog a={a} open={certifying} onClose={() => setCertifying(false)} onSaved={(x) => { apply(x); notify("Certificate recorded"); }} />
      <PaymentDialog a={a} open={paying} onClose={() => setPaying(false)} onSaved={(x) => { apply(x); notify("Payment recorded"); }} />
    </>
  );
}
